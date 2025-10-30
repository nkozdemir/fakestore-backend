import types
import unittest
from unittest.mock import Mock, patch
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from apps.auth.views import (
    RegisterView,
    UsernameAvailabilityView,
    MeView,
    LogoutView,
    LogoutAllView,
)
from apps.auth.serializers import (
    CustomerTokenObtainPairSerializer,
    StaffTokenObtainPairSerializer,
)
from rest_framework.exceptions import ValidationError


class DummyRequest:
    def __init__(self, data=None, query_params=None, user=None):
        self.data = data or {}
        self.query_params = (
            query_params if query_params is not None else dict(self.data)
        )
        self.user = user


class FakeAuthUser:
    def __init__(self, **attrs):
        self.id = attrs.get("id")
        self.username = attrs.get("username", "")
        self.email = attrs.get("email", "")
        self.first_name = attrs.get("first_name", "")
        self.last_name = attrs.get("last_name", "")
        self.is_staff = attrs.get("is_staff", False)
        self.is_superuser = attrs.get("is_superuser", False)


class FakeQuerySet:
    def __init__(self, records):
        self.records = list(records)

    def exists(self):
        return bool(self.records)

    def exclude(self, **filters):
        filtered = [
            record
            for record in self.records
            if any(getattr(record, key) != value for key, value in filters.items())
        ]
        return FakeQuerySet(filtered)


class FakeAuthUserManager:
    def __init__(self):
        self.storage = {}
        self._next_id = 1

    def _allocate(self, user):
        if user.id is None:
            user.id = self._next_id
            self._next_id += 1
        self.storage[user.id] = user
        return user

    def filter(self, **filters):
        matches = [
            user
            for user in self.storage.values()
            if all(getattr(user, key) == value for key, value in filters.items())
        ]
        return FakeQuerySet(matches)

    def create(self, **data):
        user = FakeAuthUser(**data)
        return self._allocate(user)


class AuthViewsUnitTests(unittest.TestCase):
    def setUp(self):
        self.user_manager = FakeAuthUserManager()
        self.user_patch = patch("apps.auth.views.User")
        self.mock_user_cls = self.user_patch.start()
        self.mock_user_cls.objects = self.user_manager

    def tearDown(self):
        self.user_patch.stop()


class TokenSerializerTests(unittest.TestCase):
    def test_customer_serializer_rejects_staff(self):
        serializer = CustomerTokenObtainPairSerializer()

        def fake_validate(self, attrs):
            self.user = types.SimpleNamespace(is_staff=True, is_superuser=False)
            return {"access": "a", "refresh": "b"}

        with patch("apps.auth.serializers.TokenObtainPairSerializer.validate", fake_validate):
            with self.assertRaises(ValidationError):
                serializer.validate({})

    def test_staff_serializer_accepts_staff(self):
        serializer = StaffTokenObtainPairSerializer()

        def fake_validate(self, attrs):
            self.user = types.SimpleNamespace(is_staff=True, is_superuser=False)
            return {"access": "a", "refresh": "b"}

        with patch("apps.auth.serializers.TokenObtainPairSerializer.validate", fake_validate):
            data = serializer.validate({})
        self.assertIn("access", data)

    def test_staff_serializer_rejects_non_staff(self):
        serializer = StaffTokenObtainPairSerializer()

        def fake_validate(self, attrs):
            self.user = types.SimpleNamespace(is_staff=False, is_superuser=False)
            return {"access": "a", "refresh": "b"}

        with patch("apps.auth.serializers.TokenObtainPairSerializer.validate", fake_validate):
            with self.assertRaises(ValidationError):
                serializer.validate({})

    def test_register_success(self):
        service = Mock()
        service.register.return_value = {
            "id": 1,
            "username": "newuser",
            "email": "new@example.com",
        }
        request = DummyRequest(
            {
                "username": "newuser",
                "email": "new@example.com",
                "password": "Secret123!",
                "first_name": "First",
                "last_name": "Last",
                "phone": "1234567890",
            }
        )
        view = RegisterView()
        view.service = service
        response = view.post(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "newuser")
        self.assertEqual(response.data["email"], "new@example.com")

    def test_register_detects_duplicates_and_missing_fields(self):
        service = Mock()
        service.register.return_value = (
            "VALIDATION_ERROR",
            "Username already exists",
            {"username": "taken"},
        )
        duplicate = DummyRequest(
            {
                "username": "taken",
                "email": "other@example.com",
                "password": "Secret123!",
                "first_name": "A",
                "last_name": "B",
            }
        )
        view = RegisterView()
        view.service = service
        resp_dup = view.post(duplicate)
        self.assertEqual(resp_dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp_dup.data["error"]["code"], "VALIDATION_ERROR")

        missing = DummyRequest({"username": "x", "email": "x@example.com"})
        with self.assertRaises(DRFValidationError):
            view.post(missing)
        service.register.assert_called_once()

    def test_register_rejects_invalid_username(self):
        service = Mock()
        request = DummyRequest(
            {
                "username": "bad!",
                "email": "test@example.com",
                "password": "Valid1!",
                "first_name": "First",
                "last_name": "Last",
            }
        )
        view = RegisterView()
        view.service = service
        with self.assertRaises(DRFValidationError):
            view.post(request)
        service.register.assert_not_called()

    def test_register_rejects_weak_password(self):
        service = Mock()
        request = DummyRequest(
            {
                "username": "goodname",
                "email": "test@example.com",
                "password": "weakpw",
                "first_name": "First",
                "last_name": "Last",
            }
        )
        view = RegisterView()
        view.service = service
        with self.assertRaises(DRFValidationError):
            view.post(request)
        service.register.assert_not_called()

    def test_me_view_returns_profile(self):
        user = types.SimpleNamespace(
            id=1,
            username="me",
            email="me@example.com",
            first_name="Me",
            last_name="User",
            is_staff=True,
            is_superuser=False,
            date_joined=None,
        )
        response = MeView().get(DummyRequest(user=user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "me")
        self.assertTrue(response.data["is_staff"])

    def test_username_availability_view_reports_status(self):
        service = Mock()
        service.is_username_available.return_value = True
        request = DummyRequest(query_params={"username": "fresh"})
        view = UsernameAvailabilityView()
        view.service = service
        response = view.get(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "fresh")
        self.assertTrue(response.data["available"])
        service.is_username_available.assert_called_once_with("fresh")

    def test_username_availability_view_handles_taken_usernames(self):
        service = Mock()
        service.is_username_available.return_value = False
        request = DummyRequest(query_params={"username": "taken"})
        view = UsernameAvailabilityView()
        view.service = service
        response = view.get(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["available"])
        self.assertEqual(response.data["username"], "taken")
        service.is_username_available.assert_called_once_with("taken")

    def test_logout_view_success_and_failure(self):
        request = DummyRequest({"refresh": "abc"}, user=types.SimpleNamespace(id=5))
        view = LogoutView()
        view.service = Mock()
        view.service.logout.return_value = None
        response_ok = view.post(request)
        self.assertEqual(response_ok.status_code, status.HTTP_200_OK)
        view.service.logout.assert_called_once_with("abc", 5)

        view.service.logout.reset_mock()
        view.service.logout.return_value = (
            "VALIDATION_ERROR",
            "Invalid token",
            {"error": "boom"},
        )
        response_fail = view.post(request)
        self.assertEqual(response_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_fail.data["error"]["code"], "VALIDATION_ERROR")

    def test_logout_all_blacklists_every_token(self):
        view = LogoutAllView()
        view.service = Mock()
        view.service.logout_all.return_value = {
            "detail": "Logged out from all devices",
            "tokens_invalidated": 2,
        }
        actor = types.SimpleNamespace(id=10)
        response = view.post(DummyRequest(user=actor))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        view.service.logout_all.assert_called_once_with(actor)
