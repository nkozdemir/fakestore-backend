from __future__ import annotations

from typing import Dict, Any, Optional, Tuple

from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.common import get_logger
from .dtos import address_to_dto, user_to_dto
from .models import User
from .protocols import AddressRepositoryProtocol, UserRepositoryProtocol
from .serializers import UserSerializer, AddressWriteSerializer

logger = get_logger(__name__).bind(component="users", layer="service")


class UserService:
    def __init__(
        self, users: UserRepositoryProtocol, addresses: AddressRepositoryProtocol
    ):
        self.users = users
        self.addresses = addresses
        self.logger = logger.bind(service="UserService")

    def list_users(self):
        self.logger.debug("Listing users")
        return [user_to_dto(u) for u in self.users.list()]

    def get_user(self, user_id: int):
        self.logger.debug("Fetching user", user_id=user_id)
        u = self.users.get(id=user_id)
        if not u:
            self.logger.info("User not found", user_id=user_id)
        return user_to_dto(u) if u else None

    def create_user(
        self, data: Dict[str, Any]
    ) -> Tuple[Optional[Any], Optional[Tuple[str, str, Optional[Any]]]]:
        username = data.get("username")
        email = data.get("email")
        self.logger.info("Creating user", username=username, email=email)
        password = data.pop("password", None)
        address_payload = data.pop("address", None)
        try:
            user: User = self.users.create_user(**data)
        except IntegrityError as exc:
            self.logger.warning(
                "User creation failed due to integrity error",
                username=username,
                email=email,
                error=str(exc),
            )
            return (
                None,
                (
                    "VALIDATION_ERROR",
                    "Unique constraint violated",
                    {"detail": str(exc)},
                ),
            )
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        # Create address if provided
        if address_payload:
            geo = address_payload.get("geolocation") or {}
            self.addresses.create(
                user=user,
                street=address_payload["street"],
                number=address_payload["number"],
                city=address_payload["city"],
                zipcode=address_payload["zipcode"],
                latitude=geo.get("lat"),
                longitude=geo.get("long"),
            )
        self.logger.info("User created", user_id=user.id, username=user.username)
        refreshed = self.users.get(id=user.id)
        target = refreshed if refreshed else user
        return user_to_dto(target), None

    def update_user(self, user_id: int, data: Dict[str, Any]):
        self.logger.info("Updating user", user_id=user_id)
        user: Optional[User] = self.users.get(id=user_id)
        if not user:
            self.logger.warning("User update failed: not found", user_id=user_id)
            return None
        password = data.pop("password", None)
        address_payload = data.pop("address", None)
        original_fields = {field: getattr(user, field) for field in data.keys()}
        original_password = user.password
        try:
            with transaction.atomic():
                for k, v in data.items():
                    setattr(user, k, v)
                if password:
                    user.set_password(password)
                user.save()
                if address_payload:
                    geo = address_payload.get("geolocation") or {}
                    self.addresses.create(
                        user=user,
                        street=address_payload["street"],
                        number=address_payload["number"],
                        city=address_payload["city"],
                        zipcode=address_payload["zipcode"],
                        latitude=geo.get("lat"),
                        longitude=geo.get("long"),
                    )
        except Exception:
            for field, value in original_fields.items():
                setattr(user, field, value)
            if password:
                user.password = original_password
                if hasattr(user, "_password"):
                    user._password = None
            raise
        self.logger.info("User updated", user_id=user.id)
        refreshed = self.users.get(id=user_id)
        return user_to_dto(refreshed) if refreshed else user_to_dto(user)

    def process_user_update(
        self, user_id: int, data: Dict[str, Any], *, partial: bool
    ) -> Tuple[Optional[Any], Optional[Tuple[str, str, Optional[Any]]]]:
        self.logger.debug(
            "Preparing user update",
            user_id=user_id,
            partial=partial,
        )
        user_instance = self.users.get(id=user_id)
        if not user_instance:
            self.logger.warning("User update failed: not found", user_id=user_id)
            return None, ("NOT_FOUND", "User not found", {"id": str(user_id)})

        serializer = UserSerializer(
            instance=user_instance, data=data, partial=partial
        )
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.logger.warning(
                "User update validation failed",
                user_id=user_id,
                partial=partial,
                errors=exc.detail,
            )
            return (
                None,
                ("VALIDATION_ERROR", "Invalid input", exc.detail),
            )

        try:
            dto = self.update_user(user_id, serializer.validated_data)
        except IntegrityError as exc:
            self.logger.warning(
                "User update failed due to integrity error",
                user_id=user_id,
                error=str(exc),
            )
            return (
                None,
                (
                    "VALIDATION_ERROR",
                    "Unique constraint violated",
                    {"detail": str(exc)},
                ),
            )

        if not dto:
            self.logger.warning("User update returned empty result", user_id=user_id)
            return None, ("NOT_FOUND", "User not found", {"id": str(user_id)})

        return dto, None

    def delete_user(self, user_id: int) -> bool:
        self.logger.info("Deleting user", user_id=user_id)
        user = self.users.get(id=user_id)
        if not user:
            self.logger.warning("User deletion failed: not found", user_id=user_id)
            return False
        self.users.delete(user)
        self.logger.info("User deleted", user_id=user_id)
        return True

    # Address operations (nested under user)
    def list_user_addresses(self, user_id: int):
        self.logger.debug("Listing user addresses", user_id=user_id)
        user = self.users.get(id=user_id)
        if not user:
            self.logger.info("Address list requested for missing user", user_id=user_id)
            return None
        return [address_to_dto(a) for a in user.addresses.all()]

    def list_user_addresses_with_auth(
        self,
        user_id: int,
        *,
        actor_id: Optional[int],
        is_superuser: bool,
    ) -> Tuple[Optional[Any], Optional[Tuple[str, str, Optional[Any]]]]:
        error = self.authorize_address_access(
            actor_id=actor_id,
            target_user_id=user_id,
            is_superuser=is_superuser,
            action="list",
        )
        if error:
            return None, error
        addresses = self.list_user_addresses(user_id)
        if addresses is None:
            self.logger.warning(
                "Address list failed: user missing",
                user_id=user_id,
                actor_id=actor_id,
            )
            return (
                None,
                (
                    "NOT_FOUND",
                    "User not found",
                    {"userId": str(user_id)},
                ),
            )
        return addresses, None

    def get_address_with_owner(self, address_id: int):
        self.logger.debug("Fetching address with owner", address_id=address_id)
        addr = self.addresses.get(id=address_id)
        if not addr:
            self.logger.info("Address not found", address_id=address_id)
            return None, None
        owner_id = getattr(addr.user, "id", None)
        self.logger.debug(
            "Resolved address owner",
            address_id=address_id,
            owner_id=owner_id,
        )
        return address_to_dto(addr), owner_id

    def get_user_address(self, user_id: int, address_id: int):
        self.logger.debug(
            "Fetching user address", user_id=user_id, address_id=address_id
        )
        user = self.users.get(id=user_id)
        if not user:
            self.logger.info("Address lookup failed: user not found", user_id=user_id)
            return None
        addr = self.addresses.get(id=address_id, user=user)
        if not addr:
            self.logger.info(
                "Address not found", user_id=user_id, address_id=address_id
            )
        return address_to_dto(addr) if addr else None

    def _create_user_address(self, user_id: int, data: Dict[str, Any]):
        self.logger.info("Creating address", user_id=user_id)
        user = self.users.get(id=user_id)
        if not user:
            self.logger.warning(
                "Address creation failed: user not found", user_id=user_id
            )
            return None
        geo = data.get("geolocation") or {}
        addr = self.addresses.create(
            user=user,
            street=data["street"],
            number=data["number"],
            city=data["city"],
            zipcode=data["zipcode"],
            latitude=geo.get("lat"),
            longitude=geo.get("long"),
        )
        self.logger.info("Address created", user_id=user_id, address_id=addr.id)
        return address_to_dto(addr)

    def create_user_address(self, user_id: int, data: Dict[str, Any]):
        return self._create_user_address(user_id, data)

    def update_user_address(self, user_id: int, address_id: int, data: Dict[str, Any]):
        self.logger.info("Updating address", user_id=user_id, address_id=address_id)
        user = self.users.get(id=user_id)
        if not user:
            self.logger.warning(
                "Address update failed: user not found",
                user_id=user_id,
                address_id=address_id,
            )
            return None
        addr = self.addresses.get(id=address_id, user=user)
        if not addr:
            self.logger.warning(
                "Address update failed: address not found",
                user_id=user_id,
                address_id=address_id,
            )
            return None
        # update simple fields if present
        for key in ["street", "number", "city", "zipcode"]:
            if key in data:
                setattr(addr, key, data[key])
        # handle geolocation
        if "geolocation" in data and data["geolocation"] is not None:
            geo = data["geolocation"]
            if "lat" in geo:
                addr.latitude = geo["lat"]
            if "long" in geo:
                addr.longitude = geo["long"]
        addr.save()
        self.logger.info("Address updated", user_id=user_id, address_id=address_id)
        return address_to_dto(addr)

    def authorize_address_access(
        self,
        *,
        actor_id: Optional[int],
        target_user_id: Optional[int],
        is_superuser: bool,
        action: str,
    ) -> Optional[Tuple[str, str, Optional[Any]]]:
        if actor_id is None:
            self.logger.warning(
                "Address action unauthorized",
                action=action,
                target_user_id=target_user_id,
            )
            return ("UNAUTHORIZED", "Authentication required", None)
        if target_user_id is not None and actor_id != target_user_id and not is_superuser:
            self.logger.warning(
                "Address action forbidden",
                action=action,
                actor_id=actor_id,
                target_user_id=target_user_id,
            )
            return (
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
                None,
            )
        return None

    def create_user_address_with_auth(
        self,
        user_id: int,
        data: Dict[str, Any],
        *,
        actor_id: Optional[int],
        is_superuser: bool,
    ) -> Tuple[Optional[Any], Optional[Tuple[str, str, Optional[Any]]]]:
        error = self.authorize_address_access(
            actor_id=actor_id,
            target_user_id=user_id,
            is_superuser=is_superuser,
            action="create",
        )
        if error:
            return None, error
        serializer = AddressWriteSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.logger.warning(
                "Address create validation failed",
                actor_id=actor_id,
                user_id=user_id,
                errors=exc.detail,
            )
            return None, ("VALIDATION_ERROR", "Invalid input", exc.detail)
        dto = self._create_user_address(user_id, serializer.validated_data)
        if dto is None:
            self.logger.warning(
                "Address creation failed: user missing",
                actor_id=actor_id,
                user_id=user_id,
            )
            details: Dict[str, Any] = {"userId": str(user_id)}
            if actor_id is not None and actor_id == user_id:
                details["hint"] = "Log in again"
            return (
                None,
                (
                    "NOT_FOUND",
                    "User not found",
                    details,
                ),
            )
        return dto, None

    def get_address_with_auth(
        self,
        address_id: int,
        *,
        actor_id: Optional[int],
        is_superuser: bool,
        action: str = "retrieve",
    ) -> Tuple[Optional[Any], Optional[int], Optional[Tuple[str, str, Optional[Any]]]]:
        error = self.authorize_address_access(
            actor_id=actor_id,
            target_user_id=None,
            is_superuser=is_superuser,
            action=action,
        )
        if error:
            return None, None, error
        dto, owner_id = self.get_address_with_owner(address_id)
        if not dto or owner_id is None:
            self.logger.info(
                "Address not found",
                actor_id=actor_id,
                address_id=address_id,
            )
            return (
                None,
                None,
                (
                    "NOT_FOUND",
                    "Address not found",
                    {"address_id": str(address_id)},
                ),
            )
        if actor_id != owner_id and not is_superuser:
            self.logger.warning(
                "Address access forbidden",
                actor_id=actor_id,
                address_id=address_id,
                owner_id=owner_id,
            )
            return (
                None,
                owner_id,
                (
                    "FORBIDDEN",
                    "You do not have permission to manage this user's addresses",
                    None,
                ),
            )
        return dto, owner_id, None

    def update_user_address_with_auth(
        self,
        address_id: int,
        data: Dict[str, Any],
        *,
        actor_id: Optional[int],
        is_superuser: bool,
        partial: bool,
    ) -> Tuple[Optional[Any], Optional[Tuple[str, str, Optional[Any]]]]:
        _, owner_id, error = self.get_address_with_auth(
            address_id,
            actor_id=actor_id,
            is_superuser=is_superuser,
            action="update",
        )
        if error:
            return None, error
        serializer = AddressWriteSerializer(data=data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.logger.warning(
                "Address update validation failed",
                actor_id=actor_id,
                address_id=address_id,
                errors=exc.detail,
            )
            return None, ("VALIDATION_ERROR", "Invalid input", exc.detail)
        result = self.update_user_address(
            owner_id, address_id, serializer.validated_data
        )
        if not result:
            self.logger.warning(
                "Address update failed during update",
                actor_id=actor_id,
                address_id=address_id,
            )
            return (
                None,
                (
                    "NOT_FOUND",
                    "Address not found",
                    {"address_id": str(address_id)},
                ),
            )
        return result, None

    def delete_user_address_with_auth(
        self,
        address_id: int,
        *,
        actor_id: Optional[int],
        is_superuser: bool,
    ) -> Tuple[bool, Optional[Tuple[str, str, Optional[Any]]]]:
        _, owner_id, error = self.get_address_with_auth(
            address_id,
            actor_id=actor_id,
            is_superuser=is_superuser,
            action="delete",
        )
        if error:
            return False, error
        deleted = self.delete_user_address(owner_id, address_id)
        if not deleted:
            self.logger.warning(
                "Address delete failed during delete",
                actor_id=actor_id,
                address_id=address_id,
            )
            return (
                False,
                (
                    "NOT_FOUND",
                    "Address not found",
                    {"address_id": str(address_id)},
                ),
            )
        return True, None

    def delete_user_address(self, user_id: int, address_id: int) -> bool:
        self.logger.info("Deleting address", user_id=user_id, address_id=address_id)
        user = self.users.get(id=user_id)
        if not user:
            self.logger.warning(
                "Address deletion failed: user not found",
                user_id=user_id,
                address_id=address_id,
            )
            return False
        addr = self.addresses.get(id=address_id, user=user)
        if not addr:
            self.logger.warning(
                "Address deletion failed: address not found",
                user_id=user_id,
                address_id=address_id,
            )
            return False
        self.addresses.delete(addr)
        self.logger.info("Address deleted", user_id=user_id, address_id=address_id)
        return True
