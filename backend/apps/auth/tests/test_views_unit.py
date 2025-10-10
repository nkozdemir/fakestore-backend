import types
import unittest
from unittest.mock import Mock, patch
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from apps.auth.views import RegisterView, MeView, LogoutView, LogoutAllView


class DummyRequest:
    def __init__(self, data=None, user=None):
        self.data = data or {}
        self.user = user


class FakeAuthUser:
    def __init__(self, **attrs):
        self.id = attrs.get("id")
        self.username = attrs.get("username", "")
        self.email = attrs.get("email", "")
        self.firstname = attrs.get("firstname", "")
        self.lastname = attrs.get("lastname", "")
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
        setattr(self.mock_user_cls, "firstname", None)
        setattr(self.mock_user_cls, "lastname", None)

    def tearDown(self):
        self.user_patch.stop()

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
                "password": "Secret123",
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
                "password": "Secret123",
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

    def test_me_view_returns_profile(self):
        user = types.SimpleNamespace(
            id=1,
            username="me",
            email="me@example.com",
            firstname="Me",
            lastname="User",
            is_staff=True,
            is_superuser=False,
        )
        response = MeView().get(DummyRequest(user=user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "me")
        self.assertTrue(response.data["is_staff"])

    def test_logout_view_success_and_failure(self):
        blacklisted_tokens = []

        class FakeRefreshToken:
            def __init__(self, token):
                self.token = token

            def blacklist(self):
                blacklisted_tokens.append(self.token)

        request = DummyRequest({"refresh": "abc"}, user=object())
        with patch("apps.auth.views.RefreshToken", FakeRefreshToken):
            response_ok = LogoutView().post(request)
        self.assertEqual(response_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(blacklisted_tokens, ["abc"])

        with patch("apps.auth.views.RefreshToken", side_effect=Exception("boom")):
            response_fail = LogoutView().post(request)
        self.assertEqual(response_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_fail.data["error"]["code"], "VALIDATION_ERROR")

    def test_logout_all_blacklists_every_token(self):
        class FakeOutstandingManager:
            def __init__(self, tokens):
                self._tokens = tokens

            def filter(self, **kwargs):
                return self._tokens

        class FakeBlacklistedManager:
            def __init__(self):
                self.called_with = []

            def get_or_create(self, token):
                self.called_with.append(token)
                return (token, True)

        tokens = [types.SimpleNamespace(token="t1"), types.SimpleNamespace(token="t2")]
        outstanding_manager = FakeOutstandingManager(tokens)
        blacklisted_manager = FakeBlacklistedManager()
        with patch("apps.auth.views.OutstandingToken") as mock_outstanding, patch(
            "apps.auth.views.BlacklistedToken"
        ) as mock_blacklisted:
            mock_outstanding.objects = outstanding_manager
            mock_blacklisted.objects = blacklisted_manager
            response = LogoutAllView().post(DummyRequest(user=object()))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(blacklisted_manager.called_with, tokens)
