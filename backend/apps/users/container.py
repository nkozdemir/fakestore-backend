from __future__ import annotations

from .repositories import UserRepository, AddressRepository
from .services import UserService


def build_user_service() -> UserService:
    return UserService(
        users=UserRepository(),
        addresses=AddressRepository(),
    )
