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
from apps.api.validation import validate_request_context


class DummyRequest:
    def __init__(
        self,
        data=None,
        user=None,
        *,
        method="GET",
        query_params=None,
        headers=None,
        is_privileged_user=False,
    ):
        self.data = data or {}
        self.user = user
        self.method = method
        self.query_params = query_params or {}
        self.GET = self.query_params
        self.headers = headers or {}
        self.META = {}
        self.is_privileged_user = is_privileged_user
        self.validated_user_id = None


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
        self.create_result = ({"id": 1}, None)
        self.get_result = {"id": 1}
        self.update_result = {"id": 1}
        self.process_user_update_result = ({"id": 1}, None)
        self.delete_result = True
        self.list_addresses_with_auth_result = ([], None)
        self.create_address_with_auth_result = ({"id": 1}, None)
        self.get_address_with_auth_result = ({"id": 1}, 1, None)
        self.update_address_with_auth_result = ({"id": 1}, None)
        self.delete_address_with_auth_result = (True, None)
        self.last_create_payload = None
        self.last_update_payload = None
        self.last_process_user_update_args = None
        self.last_delete_id = None
        self.last_list_addresses_with_auth_args = None
        self.last_create_address_with_auth_args = None
        self.last_get_address_with_auth_args = None
        self.last_update_address_with_auth_args = None
        self.last_delete_address_with_auth_args = None

    def list_users(self):
        return self.list_result

    def create_user(self, data):
        if isinstance(self.create_result, Exception):
            raise self.create_result
        self.last_create_payload = data
        if isinstance(self.create_result, tuple):
            return self.create_result
        return self.create_result, None

    def get_user(self, user_id):
        return self.get_result

    def update_user(self, user_id, data):
        if isinstance(self.update_result, Exception):
            raise self.update_result
        self.last_update_payload = (user_id, data)
        return self.update_result

    def process_user_update(self, user_id, data, *, partial):
        self.last_process_user_update_args = (user_id, data, partial)
        result = self.process_user_update_result
        if isinstance(result, Exception):
            raise result
        return result

    def delete_user(self, user_id):
        self.last_delete_id = user_id
        return self.delete_result

    def list_user_addresses(self, user_id):
        return self.list_addresses_with_auth_result[0]

    def list_user_addresses_with_auth(self, user_id, *, actor_id, is_superuser):
        self.last_list_addresses_with_auth_args = (user_id, actor_id, is_superuser)
        return self.list_addresses_with_auth_result

    def create_user_address_with_auth(
        self, user_id, data, *, actor_id, is_superuser
    ):
        self.last_create_address_with_auth_args = (
            user_id,
            data,
            actor_id,
            is_superuser,
        )
        return self.create_address_with_auth_result

    def get_address_with_auth(
        self,
        address_id,
        *,
        actor_id,
        is_superuser,
        action="retrieve",
    ):
        self.last_get_address_with_auth_args = (
            address_id,
            actor_id,
            is_superuser,
            action,
        )
        return self.get_address_with_auth_result

    def update_user_address_with_auth(
        self,
        address_id,
        data,
        *,
        actor_id,
        is_superuser,
        partial,
    ):
        self.last_update_address_with_auth_args = (
            address_id,
            data,
            actor_id,
            is_superuser,
            partial,
        )
        return self.update_address_with_auth_result

    def delete_user_address_with_auth(
        self,
        address_id,
        *,
        actor_id,
        is_superuser,
    ):
        self.last_delete_address_with_auth_args = (
            address_id,
            actor_id,
            is_superuser,
        )
        return self.delete_address_with_auth_result


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
        self.validation_user_patch = patch("apps.api.validation.User")
        self.mock_validation_user = self.validation_user_patch.start()
        manager = self.mock_validation_user.objects
        manager.filter.return_value = manager
        manager.exclude.return_value = manager
        manager.exists.return_value = False

    def tearDown(self):
        self.user_serializer_patch.stop()
        self.address_write_patch.stop()
        self.address_serializer_patch.stop()
        self.validation_user_patch.stop()

    def dispatch(self, request, view_cls, *, method="get", **kwargs):
        request.method = method.upper()
        pre_response = validate_request_context(request, view_cls, kwargs)
        if pre_response is not None:
            return pre_response
        view = view_cls()
        view.service = self.service
        handler = getattr(view, method.lower())
        return handler(request, **kwargs)

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
        request = DummyRequest(
            user=self._make_user(user_id=5, staff=True),
        )
        response = self.dispatch(request, UserListView, method="get")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{"id": 1}])

    def test_user_list_get_requires_authentication(self):
        response = self.dispatch(DummyRequest(), UserListView, method="get")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")

    def test_user_list_get_forbidden_for_non_privileged_user(self):
        request = DummyRequest(user=self._make_user(user_id=6))
        response = self.dispatch(request, UserListView, method="get")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")

    def test_user_list_post_success_and_validation_error(self):
        success_request = DummyRequest(
            {"username": "new"},
            user=self._make_user(user_id=1, staff=True),
            method="POST",
        )
        response_ok = self.dispatch(success_request, UserListView, method="post")
        self.assertEqual(response_ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.service.last_create_payload["username"], "new")

        invalid_request = DummyRequest(
            {"__invalid": True},
            user=self._make_user(user_id=1, staff=True),
            method="POST",
        )
        response_invalid = self.dispatch(invalid_request, UserListView, method="post")
        self.assertEqual(response_invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_list_post_service_validation_error(self):
        self.service.create_result = (
            None,
            (
                "VALIDATION_ERROR",
                "Unique constraint violated",
                {"detail": "duplicate"},
            ),
        )
        request = DummyRequest(
            {"username": "duplicate"},
            user=self._make_user(user_id=1, staff=True),
            method="POST",
        )
        response = self.dispatch(request, UserListView, method="post")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_user_list_post_forbidden_when_authenticated_non_admin(self):
        request = DummyRequest(
            {"username": "dup"},
            user=self._make_user(5, staff=False, superuser=False),
            method="POST",
        )
        response = self.dispatch(request, UserListView, method="post")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_detail_get_and_delete_paths(self):
        # Not found case
        self.service.get_result = None
        response_missing = self.dispatch(
            DummyRequest(user=self._make_user(99)),
            UserDetailView,
            method="get",
            user_id=99,
        )
        self.assertEqual(response_missing.status_code, status.HTTP_404_NOT_FOUND)

        # Delete success
        self.service.delete_result = True
        delete_req = DummyRequest(user=self._make_user(1), method="DELETE")
        delete_resp = self.dispatch(delete_req, UserDetailView, method="delete", user_id=1)
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Delete not found
        self.service.delete_result = False
        delete_missing = self.dispatch(
            DummyRequest(user=self._make_user(2), method="DELETE"),
            UserDetailView,
            method="delete",
            user_id=2,
        )
        self.assertEqual(delete_missing.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_detail_put_success(self):
        self.service.process_user_update_result = (
            {"id": 1, "username": "updated"},
            None,
        )
        response = self.dispatch(
            DummyRequest(
                {"username": "updated"},
                user=self._make_user(1),
                method="PUT",
            ),
            UserDetailView,
            method="put",
            user_id=1,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_id, payload, partial = self.service.last_process_user_update_args
        self.assertEqual(user_id, 1)
        self.assertFalse(partial)
        self.assertEqual(payload["username"], "updated")

    def test_user_detail_patch_invalid_serializer(self):
        self.service.process_user_update_result = (
            None,
            ("VALIDATION_ERROR", "Invalid input", {"invalid": True}),
        )
        response = self.dispatch(
            DummyRequest(
                {"__invalid": True},
                user=self._make_user(1),
                method="PATCH",
            ),
            UserDetailView,
            method="patch",
            user_id=1,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_address_list_post_requires_auth(self):
        unauthorized = self.dispatch(
            DummyRequest({"street": "Main"}, method="POST"),
            UserAddressListView,
            method="post",
            user_id=1,
        )
        self.assertEqual(unauthorized.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_address_list_post_success(self):
        self.service.create_address_with_auth_result = ({"id": 1, "street": "Main"}, None)
        request = DummyRequest(
            {"street": "Main"},
            user=self._make_user(5),
            method="POST",
        )
        response = self.dispatch(
            request,
            UserAddressListView,
            method="post",
            user_id=5,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user_id, data, actor_id, is_superuser = self.service.last_create_address_with_auth_args
        self.assertEqual(user_id, 5)
        self.assertEqual(data["street"], "Main")
        self.assertEqual(actor_id, 5)
        self.assertFalse(is_superuser)

    def test_user_address_list_post_forbidden_for_other_user(self):
        self.service.create_address_with_auth_result = (
            None,
            (
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
                None,
            ),
        )
        response = self.dispatch(
            DummyRequest(
                {"street": "Main"},
                user=self._make_user(3),
                method="POST",
            ),
            UserAddressListView,
            method="post",
            user_id=9,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_address_detail_get_and_delete(self):
        response_unauth = self.dispatch(
            DummyRequest(),
            UserAddressDetailView,
            method="get",
            address_id=1,
        )
        self.assertEqual(response_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        user = self._make_user(7)
        self.service.get_address_with_auth_result = (
            None,
            None,
            ("NOT_FOUND", "Address not found", {"address_id": "1"}),
        )
        response_missing = self.dispatch(
            DummyRequest(user=user),
            UserAddressDetailView,
            method="get",
            address_id=1,
        )
        self.assertEqual(response_missing.status_code, status.HTTP_404_NOT_FOUND)

        self.service.delete_address_with_auth_result = (True, None)
        delete_resp = self.dispatch(
            DummyRequest(user=user, method="DELETE"),
            UserAddressDetailView,
            method="delete",
            address_id=1,
        )
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)
        address_id, actor_id, is_superuser = self.service.last_delete_address_with_auth_args
        self.assertEqual(address_id, 1)
        self.assertEqual(actor_id, 7)
        self.assertFalse(is_superuser)

    def test_user_address_detail_forbidden_for_other_user(self):
        self.service.get_address_with_auth_result = (
            None,
            9,
            (
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
                None,
            ),
        )
        actor = self._make_user(3)
        response = self.dispatch(
            DummyRequest(user=actor),
            UserAddressDetailView,
            method="get",
            address_id=1,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIsNone(self.service.last_update_address_with_auth_args)

    def test_user_address_detail_superuser_access(self):
        user = self._make_user(1, superuser=True)
        self.service.get_address_with_auth_result = (
            {"id": 2},
            9,
            None,
        )
        response = self.dispatch(
            DummyRequest(user=user),
            UserAddressDetailView,
            method="get",
            address_id=2,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
