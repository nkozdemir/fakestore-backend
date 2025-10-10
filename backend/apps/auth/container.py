from __future__ import annotations

from .repositories import DjangoUserRegistrationRepository
from .services import RegistrationService


def build_registration_service() -> RegistrationService:
    return RegistrationService(users=DjangoUserRegistrationRepository())
