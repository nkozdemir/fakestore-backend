from typing import Dict, Any, Optional
from .repositories import UserRepository, AddressRepository
from .dtos import user_to_dto
from .models import User
from .dtos import address_to_dto

class UserService:
    def __init__(self):
        self.users = UserRepository()
        self.addresses = AddressRepository()

    def list_users(self):
        return [user_to_dto(u) for u in self.users.list()]

    def get_user(self, user_id: int):
        u = self.users.get(id=user_id)
        return user_to_dto(u) if u else None

    def create_user(self, data: Dict[str, Any]):
        # Ensure password is hashed and proper user creation is used
        password = data.pop('password', None)
        address_payload = data.pop('address', None)
        # Map optional first/last name if provided under alternative keys
        user: User = User.objects.create_user(**data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        # Create address if provided
        if address_payload:
            geo = address_payload.get('geolocation') or {}
            self.addresses.create(
                user=user,
                street=address_payload['street'],
                number=address_payload['number'],
                city=address_payload['city'],
                zipcode=address_payload['zipcode'],
                latitude=geo.get('lat'),
                longitude=geo.get('long'),
            )
        return user_to_dto(user)

    def update_user(self, user_id: int, data: Dict[str, Any]):
        user: Optional[User] = self.users.get(id=user_id)
        if not user:
            return None
        password = data.pop('password', None)
        address_payload = data.pop('address', None)
        for k, v in data.items():
            setattr(user, k, v)
        if password:
            user.set_password(password)
        user.save()
        if address_payload:
            geo = address_payload.get('geolocation') or {}
            self.addresses.create(
                user=user,
                street=address_payload['street'],
                number=address_payload['number'],
                city=address_payload['city'],
                zipcode=address_payload['zipcode'],
                latitude=geo.get('lat'),
                longitude=geo.get('long'),
            )
        return user_to_dto(user)

    def delete_user(self, user_id: int) -> bool:
        user = self.users.get(id=user_id)
        if not user:
            return False
        self.users.delete(user)
        return True

    # Address operations (nested under user)
    def list_user_addresses(self, user_id: int):
        user = self.users.get(id=user_id)
        if not user:
            return None
        return [address_to_dto(a) for a in user.addresses.all()]

    def get_user_address(self, user_id: int, address_id: int):
        user = self.users.get(id=user_id)
        if not user:
            return None
        addr = self.addresses.get(id=address_id, user=user)
        return address_to_dto(addr) if addr else None

    def create_user_address(self, user_id: int, data: Dict[str, Any]):
        user = self.users.get(id=user_id)
        if not user:
            return None
        geo = (data.get('geolocation') or {})
        addr = self.addresses.create(
            user=user,
            street=data['street'],
            number=data['number'],
            city=data['city'],
            zipcode=data['zipcode'],
            latitude=geo.get('lat'),
            longitude=geo.get('long'),
        )
        return address_to_dto(addr)

    def update_user_address(self, user_id: int, address_id: int, data: Dict[str, Any]):
        user = self.users.get(id=user_id)
        if not user:
            return None
        addr = self.addresses.get(id=address_id, user=user)
        if not addr:
            return None
        # update simple fields if present
        for key in ['street', 'number', 'city', 'zipcode']:
            if key in data:
                setattr(addr, key, data[key])
        # handle geolocation
        if 'geolocation' in data and data['geolocation'] is not None:
            geo = data['geolocation']
            if 'lat' in geo:
                addr.latitude = geo['lat']
            if 'long' in geo:
                addr.longitude = geo['long']
        addr.save()
        return address_to_dto(addr)

    def delete_user_address(self, user_id: int, address_id: int) -> bool:
        user = self.users.get(id=user_id)
        if not user:
            return False
        addr = self.addresses.get(id=address_id, user=user)
        if not addr:
            return False
        self.addresses.delete(addr)
        return True
