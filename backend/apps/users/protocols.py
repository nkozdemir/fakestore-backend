from __future__ import annotations

from typing import Iterable, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.users.models import User, Address


class UserRepositoryProtocol(Protocol):
    def list(self, **filters) -> Iterable["User"]: ...

    def get(self, **filters) -> Optional["User"]: ...

    def create_user(self, **data) -> "User": ...

    def delete(self, user: "User") -> None: ...


class AddressRepositoryProtocol(Protocol):
    def create(self, **data) -> "Address": ...

    def get(self, **filters) -> Optional["Address"]: ...

    def delete(self, address: "Address") -> None: ...
