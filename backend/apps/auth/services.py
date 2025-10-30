from __future__ import annotations

from typing import Dict, Any, Optional, Tuple, Union

from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken, OutstandingToken, BlacklistedToken

from apps.common import get_logger
from .protocols import UserRegistrationRepositoryProtocol

logger = get_logger(__name__).bind(component="auth", service="RegistrationService")


class RegistrationService:
    def __init__(self, users: UserRegistrationRepositoryProtocol):
        self.users = users
        self.logger = logger

    def _build_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "username": data["username"].strip(),
            "email": data["email"].strip(),
            "password": make_password(data["password"]),
            "first_name": data.get("first_name", "").strip(),
            "last_name": data.get("last_name", "").strip(),
        }
        return payload

    def _check_uniqueness(self, username: str, email: str) -> Optional[tuple]:
        if self.users.username_exists(username):
            self.logger.info(
                "Registration rejected: username already exists", username=username
            )
            return (
                "VALIDATION_ERROR",
                "Username already exists",
                {"username": username},
            )
        if self.users.email_exists(email):
            self.logger.info("Registration rejected: email already exists", email=email)
            return ("VALIDATION_ERROR", "Email already exists", {"email": email})
        return None

    def register(self, data: Dict[str, Any]):
        username = data["username"].strip()
        email = data["email"].strip()
        self.logger.debug(
            "Received registration request", username=username, email=email
        )
        conflict = self._check_uniqueness(username, email)
        if conflict:
            return conflict
        payload = self._build_payload(data)
        password = payload.pop("password")
        user = self.users.create_user(password=password, **payload)
        self.logger.info(
            "User registered successfully", user_id=user.id, username=user.username
        )
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }

    def is_username_available(self, username: str) -> bool:
        normalized = username.strip()
        self.logger.debug(
            "Checking username availability", username=normalized or username
        )
        return not self.users.username_exists(normalized)


class SessionService:
    def __init__(self):
        self.logger = get_logger(__name__).bind(component="auth", service="SessionService")

    def logout(self, refresh_token: str, actor_id: Optional[int]) -> Optional[Tuple[str, str, Optional[Dict[str, Any]]]]:
        if not refresh_token:
            self.logger.warning("Logout rejected: missing refresh token", actor_id=actor_id)
            return ("VALIDATION_ERROR", "Invalid token", {"refresh": None})
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as exc:  # pragma: no cover - conversion handled in tests via mocks
            self.logger.warning(
                "Logout failed: token error",
                actor_id=actor_id,
                error=str(exc),
            )
            return ("VALIDATION_ERROR", "Invalid token", {"error": str(exc)})
        self.logger.info("User logged out", actor_id=actor_id)
        return None

    def logout_all(self, user) -> Dict[str, Union[int, str]]:
        user_id = getattr(user, "id", None)
        tokens_queryset = OutstandingToken.objects.filter(user=user)
        tokens = list(tokens_queryset)
        invalidated = 0
        for token in tokens:
            try:
                BlacklistedToken.objects.get_or_create(token=token)
                invalidated += 1
            except Exception as exc:  # pragma: no cover - safety logging
                token_id = getattr(token, "id", getattr(token, "token", None))
                self.logger.exception(
                    "Failed to blacklist token during logout-all",
                    actor_id=user_id,
                    token_id=token_id,
                    error=str(exc),
                )
        self.logger.info(
            "User logged out from all devices",
            actor_id=user_id,
            tokens_invalidated=invalidated,
        )
        return {"detail": "Logged out from all devices", "tokens_invalidated": invalidated}
