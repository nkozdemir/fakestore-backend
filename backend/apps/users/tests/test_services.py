import unittest
from unittest.mock import patch
from apps.users.services import UserService


class DummyAtomic:
    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeAddress:
    def __init__(self, address_id, user, **data):
        self.id = address_id
        self.user = user
        self.street = data.get("street", "")
        self.number = data.get("number", 0)
        self.city = data.get("city", "")
        self.zipcode = data.get("zipcode", "")
        self.latitude = data.get("latitude")
        self.longitude = data.get("longitude")

    def save(self):
        return self


class FakeAddressManager:
    def __init__(self):
        self._items = []

    def all(self):
        return list(self._items)

    def add(self, address):
        self._items.append(address)

    def remove(self, address):
        self._items = [item for item in self._items if item.id != address.id]


class FakeAddressRepository:
    def __init__(self):
        self.storage = {}
        self._next_id = 1

    def create(self, **data):
        user = data.pop("user")
        addr = FakeAddress(self._next_id, user=user, **data)
        self._next_id += 1
        self.storage[addr.id] = addr
        user.addresses.add(addr)
        return addr

    def get(self, **filters):
        results = list(self.storage.values())
        for key, value in filters.items():
            if key == "user":
                results = [addr for addr in results if addr.user is value]
            else:
                results = [addr for addr in results if getattr(addr, key) == value]
        return results[0] if results else None

    def delete(self, address):
        self.storage.pop(address.id, None)
        address.user.addresses.remove(address)


class FakeUserRepository:
    def __init__(self):
        self.storage = {}
        self._next_id = 1

    def _allocate_id(self):
        next_id = self._next_id
        self._next_id += 1
        return next_id

    def list(self, **filters):
        users = list(self.storage.values())
        if not filters:
            return users
        filtered = []
        for user in users:
            if all(getattr(user, key) == value for key, value in filters.items()):
                filtered.append(user)
        return filtered

    def get(self, **filters):
        for user in self.storage.values():
            matches = all(getattr(user, key) == value for key, value in filters.items())
            if matches:
                return user
        return None

    def delete(self, user):
        self.storage.pop(user.id, None)

    def add(self, user):
        if getattr(user, "id", None) is None:
            user.id = self._allocate_id()
        self.storage[user.id] = user
        return user

    def create_user(self, **data):
        user = FakeUser(self, **data)
        return self.add(user)


class FakeUser:
    def __init__(self, repo, **attrs):
        self._repo = repo
        self.id = attrs.pop("id", None)
        self.username = attrs.get("username", "")
        self.email = attrs.get("email", "")
        self.first_name = attrs.get("first_name", "")
        self.last_name = attrs.get("last_name", "")
        self.phone = attrs.get("phone", "")
        self.password = attrs.get("password", "")
        self.addresses = FakeAddressManager()

    def set_password(self, password):
        self.password = f"hashed:{password}"

    def save(self, update_fields=None):
        self._repo.add(self)
        return self


class UserServiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.user_repo = FakeUserRepository()
        self.address_repo = FakeAddressRepository()
        self.atomic_patcher = patch(
            "apps.users.services.transaction.atomic", DummyAtomic()
        )
        self.atomic_patcher.start()
        self.service = UserService(
            users=self.user_repo,
            addresses=self.address_repo,
        )

    def tearDown(self):
        self.atomic_patcher.stop()

    def _user_to_dict(self, user):
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "addresses": [addr.id for addr in user.addresses.all()],
        }

    def _address_to_dict(self, address):
        return {
            "id": address.id,
            "street": address.street,
            "city": address.city,
        }

    @patch("apps.users.services.address_to_dto")
    @patch("apps.users.services.user_to_dto")
    def test_create_user_creates_address_and_hashes_password(
        self, mock_user_to_dto, mock_address_to_dto
    ):
        mock_user_to_dto.side_effect = self._user_to_dict
        mock_address_to_dto.side_effect = self._address_to_dict
        payload = {
            "username": "alice",
            "email": "alice@example.com",
            "first_name": "Alice",
            "last_name": "Example",
            "phone": "123",
            "password": "Secret123",
            "address": {
                "street": "Main",
                "number": 10,
                "city": "Town",
                "zipcode": "00000",
                "geolocation": {"lat": "1.0", "long": "2.0"},
            },
        }
        dto = self.service.create_user(payload.copy())
        self.assertEqual(dto["username"], "alice")
        self.assertEqual(dto["addresses"], [1])
        stored_user = self.user_repo.get(id=dto["id"])
        self.assertEqual(stored_user.password, "hashed:Secret123")

    def test_update_user_returns_none_for_missing_user(self):
        result = self.service.update_user(99, {"username": "ghost"})
        self.assertIsNone(result)

    def test_update_user_reverts_changes_when_address_creation_fails(self):
        user = self.user_repo.create_user(
            username="dave", email="dave@example.com", phone="123"
        )
        original_username = user.username
        original_phone = user.phone

        def boom(**kwargs):
            raise ValueError("boom")

        self.address_repo.create = boom
        with self.assertRaises(ValueError):
            self.service.update_user(
                user.id,
                {
                    "username": "newdave",
                    "phone": "999",
                    "address": {
                        "street": "Main",
                        "number": 1,
                        "city": "Town",
                        "zipcode": "00000",
                        "geolocation": {"lat": "1.0", "long": "2.0"},
                    },
                },
            )
        stored = self.user_repo.get(id=user.id)
        self.assertEqual(stored.username, original_username)
        self.assertEqual(stored.phone, original_phone)
        self.assertEqual(stored.addresses.all(), [])

    @patch("apps.users.services.user_to_dto")
    def test_delete_user_and_list_users(self, mock_user_to_dto):
        user = self.user_repo.create_user(username="bob", email="bob@example.com")
        mock_user_to_dto.side_effect = self._user_to_dict
        self.assertTrue(self.service.delete_user(user.id))
        self.assertEqual(self.service.list_users(), [])

    @patch("apps.users.services.address_to_dto")
    def test_address_crud_roundtrip(self, mock_address_to_dto):
        user = self.user_repo.create_user(username="carol", email="carol@example.com")
        mock_address_to_dto.side_effect = self._address_to_dict

        created = self.service.create_user_address(
            user.id,
            {
                "street": "Oak",
                "number": 5,
                "city": "City",
                "zipcode": "11111",
                "geolocation": {"lat": "5.0", "long": "6.0"},
            },
        )
        self.assertEqual(created["street"], "Oak")

        addresses = self.service.list_user_addresses(user.id)
        self.assertEqual(len(addresses), 1)

        address_id = addresses[0]["id"]
        updated = self.service.update_user_address(
            user.id, address_id, {"city": "New City", "geolocation": {"lat": "7.0"}}
        )
        self.assertEqual(updated["city"], "New City")

        fetched = self.service.get_user_address(user.id, address_id)
        self.assertEqual(fetched["id"], address_id)

        self.assertTrue(self.service.delete_user_address(user.id, address_id))
        self.assertEqual(self.service.list_user_addresses(user.id), [])

    def test_address_methods_return_none_when_user_missing(self):
        self.assertIsNone(self.service.list_user_addresses(1))
        self.assertIsNone(self.service.get_user_address(1, 1))
        self.assertIsNone(
            self.service.create_user_address(
                1, {"street": "X", "number": 1, "city": "C", "zipcode": "Z"}
            )
        )
        self.assertFalse(self.service.delete_user_address(1, 1))
