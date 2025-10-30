from __future__ import annotations

from .repositories import DjangoUserRegistrationRepository
from .services import RegistrationService, SessionService


def build_registration_service() -> RegistrationService:
    return RegistrationService(users=DjangoUserRegistrationRepository())


def build_session_service() -> SessionService:
    return SessionService()
