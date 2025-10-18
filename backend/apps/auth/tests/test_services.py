import unittest
from unittest.mock import patch

from apps.auth.services import RegistrationService


class FakeUser:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class FakeUserRepository:
    def __init__(self):
        self._existing_usernames = set()
        self._existing_emails = set()
        self._created_payloads = []

    def username_exists(self, username: str) -> bool:
        return username in self._existing_usernames

    def email_exists(self, email: str) -> bool:
        return email in self._existing_emails

    def create_user(self, **data):
        payload = dict(data)
        payload.setdefault("id", len(self._created_payloads) + 1)
        user = FakeUser(**payload)
        self._created_payloads.append(payload)
        self._existing_usernames.add(user.username)
        self._existing_emails.add(user.email)
        return user


class RegistrationServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeUserRepository()
        self.service = RegistrationService(users=self.repo)
        self.cart_patcher = patch("apps.auth.services.ensure_user_cart")
        self.mock_ensure_cart = self.cart_patcher.start()
        self.mock_ensure_cart.reset_mock()

    def test_register_success(self):
        result = self.service.register(
            {
                "username": "user",
                "email": "user@example.com",
                "password": "Secret123",
                "first_name": "Alice",
                "last_name": "Example",
            }
        )
        self.assertEqual(result["username"], "user")
        self.assertEqual(result["email"], "user@example.com")
        self.assertEqual(result["id"], 1)
        self.mock_ensure_cart.assert_called_once()

    def test_register_duplicate_username(self):
        self.repo._existing_usernames.add("dup")
        result = self.service.register(
            {
                "username": "dup",
                "email": "dup@example.com",
                "password": "Secret123",
                "first_name": "A",
                "last_name": "B",
            }
        )
        self.assertEqual(result[0], "VALIDATION_ERROR")
        self.mock_ensure_cart.assert_not_called()

    def test_is_username_available_checks_repository(self):
        self.repo._existing_usernames.add("taken")
        self.assertFalse(self.service.is_username_available("taken"))
        self.assertFalse(self.service.is_username_available(" taken "))
        self.assertTrue(self.service.is_username_available("free"))

    def tearDown(self):
        self.cart_patcher.stop()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
