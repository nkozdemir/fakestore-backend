import unittest
from unittest.mock import patch
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.db import IntegrityError
from apps.users.views import (
    UserListView,
    UserDetailView,
    UserAddressListView,
    UserAddressDetailView,
)


class DummyRequest:
    def __init__(self, data=None, user=None, is_privileged_user=False):
        self.data = data or {}
        self.user = user
        self.is_privileged_user = is_privileged_user


class FakeUserSerializer:
    def __init__(self, data=None, many=False, instance=None, partial=False):
        if instance is not None and data is None:
            data = instance
        self._data = data
        self.many = many
        self.partial = partial
        self.errors = {}
        if isinstance(data, dict) and data.get("__invalid"):
            self._is_valid = False
            self.errors = {"invalid": True}
        else:
            self._is_valid = True
        if isinstance(data, dict):
            self.validated_data = {
                k: v for k, v in data.items() if not k.startswith("__")
            }
        else:
            self.validated_data = data

    def is_valid(self, raise_exception=False):
        if not self._is_valid and raise_exception:
            raise DRFValidationError(self.errors)
        return self._is_valid

    @property
    def data(self):
        return self._data


class FakeAddressWriteSerializer:
    def __init__(self, data=None, partial=False):
        self._data = data or {}
        self.partial = partial
        self.errors = {}
        if self._data.get("__invalid"):
            self._is_valid = False
            self.errors = {"invalid": True}
        else:
            self._is_valid = True
        self.validated_data = {
            k: v for k, v in self._data.items() if not k.startswith("__")
        }

    def is_valid(self, raise_exception=False):
        if not self._is_valid and raise_exception:
            raise DRFValidationError(self.errors)
        return self._is_valid


class FakeAddressSerializer:
    def __init__(self, data=None, many=False):
        self._data = data
        self.many = many

    @property
    def data(self):
        return self._data


class StubUserService:
    def __init__(self):
        self.list_result = []
        self.create_result = {"id": 1}
        self.get_result = {"id": 1}
        self.update_result = {"id": 1}
        self.delete_result = True
        self.address_list_result = []
        self.address_create_result = {"id": 1}
        self.address_get_result = {"id": 1}
        self.address_update_result = {"id": 1}
        self.address_delete_result = True
        self.address_with_owner_result = ({"id": 1}, 1)
        self.last_create_payload = None
        self.last_update_payload = None
        self.last_delete_id = None
        self.last_address_create = None
        self.last_address_update = None
        self.last_address_delete = None

    def list_users(self):
        return self.list_result

    def create_user(self, data):
        if isinstance(self.create_result, Exception):
            raise self.create_result
        self.last_create_payload = data
        return self.create_result

    def get_user(self, user_id):
        return self.get_result

    def update_user(self, user_id, data):
        if isinstance(self.update_result, Exception):
            raise self.update_result
        self.last_update_payload = (user_id, data)
        return self.update_result

    def delete_user(self, user_id):
        self.last_delete_id = user_id
        return self.delete_result

    def list_user_addresses(self, user_id):
        return self.address_list_result

    def create_user_address(self, user_id, data):
        self.last_address_create = (user_id, data)
        return self.address_create_result

    def get_user_address(self, user_id, address_id):
        return self.address_get_result

    def update_user_address(self, user_id, address_id, data):
        self.last_address_update = (user_id, address_id, data)
        return self.address_update_result

    def delete_user_address(self, user_id, address_id):
        self.last_address_delete = (user_id, address_id)
        return self.address_delete_result

    def get_address_with_owner(self, address_id):
        return self.address_with_owner_result


class UserViewsUnitTests(unittest.TestCase):
    def setUp(self):
        self.service = StubUserService()
        self.user_serializer_patch = patch(
            "apps.users.views.UserSerializer", FakeUserSerializer
        )
        self.address_write_patch = patch(
            "apps.users.views.AddressWriteSerializer", FakeAddressWriteSerializer
        )
        self.address_serializer_patch = patch(
            "apps.users.views.AddressSerializer", FakeAddressSerializer
        )
        self.user_serializer_patch.start()
        self.address_write_patch.start()
        self.address_serializer_patch.start()

    def tearDown(self):
        self.user_serializer_patch.stop()
        self.address_write_patch.stop()
        self.address_serializer_patch.stop()

    @staticmethod
    def _make_user(user_id=1, *, staff=False, superuser=False):
        return type(
            "User",
            (),
            {
                "id": user_id,
                "is_authenticated": True,
                "is_staff": staff,
                "is_superuser": superuser,
            },
        )()

    def test_user_list_get_returns_service_data(self):
        self.service.list_result = [{"id": 1}]
        view = UserListView()
        view.service = self.service
        request = DummyRequest(
            user=self._make_user(user_id=5, staff=True),
            is_privileged_user=True,
        )
        response = view.get(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{"id": 1}])

    def test_user_list_get_requires_authentication(self):
        view = UserListView()
        view.service = self.service
        response = view.get(DummyRequest())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")

    def test_user_list_get_forbidden_for_non_privileged_user(self):
        view = UserListView()
        view.service = self.service
        request = DummyRequest(user=self._make_user(user_id=6))
        response = view.get(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")

    def test_user_list_post_success_and_validation_error(self):
        view = UserListView()
        view.service = self.service
        success_request = DummyRequest({"username": "new"})
        response_ok = view.post(success_request)
        self.assertEqual(response_ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.service.last_create_payload["username"], "new")

        invalid_request = DummyRequest({"__invalid": True})
        response_invalid = view.post(invalid_request)
        self.assertEqual(response_invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_list_post_service_validation_error(self):
        view = UserListView()
        view.service = self.service
        self.service.create_result = IntegrityError("duplicate")
        request = DummyRequest({"username": "duplicate"})
        response = view.post(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_user_list_post_forbidden_when_authenticated_non_admin(self):
        view = UserListView()
        view.service = self.service
        request = DummyRequest(
            {"username": "dup"},
            user=self._make_user(5, staff=False, superuser=False),
        )
        response = view.post(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_detail_get_and_delete_paths(self):
        view = UserDetailView()
        view.service = self.service

        # Not found case
        self.service.get_result = None
        response_missing = view.get(DummyRequest(), user_id=99)
        self.assertEqual(response_missing.status_code, status.HTTP_404_NOT_FOUND)

        # Delete success
        self.service.delete_result = True
        delete_req = DummyRequest(user=self._make_user(1))
        delete_resp = view.delete(delete_req, user_id=1)
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Delete not found
        self.service.delete_result = False
        delete_missing = view.delete(DummyRequest(user=self._make_user(2)), user_id=2)
        self.assertEqual(delete_missing.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_detail_put_success(self):
        view = UserDetailView()
        view.service = self.service
        self.service.update_result = {"id": 1, "username": "updated"}
        with patch("apps.users.views.User") as mock_user_cls:
            mock_user_cls.objects.filter.return_value.first.return_value = object()
            response = view.put(
                DummyRequest({"username": "updated"}, user=self._make_user(1)),
                user_id=1,
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_id, payload = self.service.last_update_payload
        self.assertEqual(user_id, 1)
        self.assertEqual(payload["username"], "updated")

    def test_user_detail_patch_invalid_serializer(self):
        view = UserDetailView()
        view.service = self.service
        with patch("apps.users.views.User") as mock_user_cls:
            mock_user_cls.objects.filter.return_value.first.return_value = object()
            response = view.patch(
                DummyRequest({"__invalid": True}, user=self._make_user(1)), user_id=1
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_address_list_post_requires_auth(self):
        view = UserAddressListView()
        view.service = self.service
        unauthorized = view.post(DummyRequest({"street": "Main"}), user_id=1)
        self.assertEqual(unauthorized.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_address_list_post_success(self):
        view = UserAddressListView()
        view.service = self.service
        self.service.address_create_result = {"id": 1, "street": "Main"}
        request = DummyRequest({"street": "Main"}, user=self._make_user(5))
        request.validated_user_id = 5
        response = view.post(request, user_id=5)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.service.last_address_create[0], 5)

    def test_user_address_list_post_forbidden_for_other_user(self):
        view = UserAddressListView()
        view.service = self.service
        request = DummyRequest({"street": "Main"}, user=self._make_user(3))
        request.validated_user_id = 3
        response = view.post(request, user_id=9)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_address_detail_get_and_delete(self):
        view = UserAddressDetailView()
        view.service = self.service
        response_unauth = view.get(DummyRequest(), address_id=1)
        self.assertEqual(response_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        user = self._make_user(7)
        self.service.address_with_owner_result = (None, None)
        req_missing = DummyRequest(user=user)
        req_missing.validated_user_id = user.id
        response_missing = view.get(req_missing, address_id=1)
        self.assertEqual(response_missing.status_code, status.HTTP_404_NOT_FOUND)

        self.service.address_delete_result = True
        self.service.address_with_owner_result = ({"id": 1}, user.id)
        req_delete = DummyRequest(user=user)
        req_delete.validated_user_id = user.id
        delete_resp = view.delete(req_delete, address_id=1)
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.service.last_address_delete, (user.id, 1))

    def test_user_address_detail_forbidden_for_other_user(self):
        view = UserAddressDetailView()
        view.service = self.service
        self.service.address_with_owner_result = ({"id": 1}, 9)
        actor = self._make_user(3)
        request = DummyRequest(user=actor)
        request.validated_user_id = actor.id
        response = view.get(request, address_id=1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIsNone(self.service.last_address_update)

    def test_user_address_detail_superuser_access(self):
        view = UserAddressDetailView()
        view.service = self.service
        user = self._make_user(1, superuser=True)
        request = DummyRequest(user=user)
        request.validated_user_id = user.id
        self.service.address_with_owner_result = ({"id": 2}, 9)
        response = view.get(request, address_id=2)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
