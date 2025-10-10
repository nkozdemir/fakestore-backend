from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from .protocols import UserRegistrationRepositoryProtocol


class DjangoUserRegistrationRepository(UserRegistrationRepositoryProtocol):
    def __init__(self) -> None:
        self.model = get_user_model()

    def username_exists(self, username: str) -> bool:
        return self.model.objects.filter(username=username).exists()

    def email_exists(self, email: str) -> bool:
        return self.model.objects.filter(email=email).exists()

    def supports_field(self, field_name: str) -> bool:
        return hasattr(self.model, field_name)

    def create_user(self, **data: Any):
        return self.model.objects.create(**data)
