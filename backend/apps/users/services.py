from __future__ import annotations

from typing import Dict, Any, Optional

from apps.common import get_logger
from .dtos import address_to_dto, user_to_dto
from .models import User
from .protocols import AddressRepositoryProtocol, UserRepositoryProtocol

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

    def create_user(self, data: Dict[str, Any]):
        username = data.get("username")
        email = data.get("email")
        self.logger.info("Creating user", username=username, email=email)
        password = data.pop("password", None)
        address_payload = data.pop("address", None)
        user: User = self.users.create_user(**data)
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
        return user_to_dto(refreshed) if refreshed else user_to_dto(user)

    def update_user(self, user_id: int, data: Dict[str, Any]):
        self.logger.info("Updating user", user_id=user_id)
        user: Optional[User] = self.users.get(id=user_id)
        if not user:
            self.logger.warning("User update failed: not found", user_id=user_id)
            return None
        password = data.pop("password", None)
        address_payload = data.pop("address", None)
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
        self.logger.info("User updated", user_id=user.id)
        refreshed = self.users.get(id=user_id)
        return user_to_dto(refreshed) if refreshed else user_to_dto(user)

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

    def create_user_address(self, user_id: int, data: Dict[str, Any]):
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
