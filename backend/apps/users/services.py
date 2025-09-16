from typing import Dict, Any, Optional
from .repositories import UserRepository, AddressRepository
from .dtos import user_to_dto
from .models import User

class UserService:
    def __init__(self):
        self.users = UserRepository()

    def list_users(self):
        return [user_to_dto(u) for u in self.users.list()]

    def get_user(self, user_id: int):
        u = self.users.get(id=user_id)
        return user_to_dto(u) if u else None

    def create_user(self, data: Dict[str, Any]):
        user: User = self.users.create(**data)
        return user_to_dto(user)

    def update_user(self, user_id: int, data: Dict[str, Any]):
        user: Optional[User] = self.users.get(id=user_id)
        if not user:
            return None
        for k, v in data.items():
            setattr(user, k, v)
        user.save()
        return user_to_dto(user)

    def delete_user(self, user_id: int) -> bool:
        user = self.users.get(id=user_id)
        if not user:
            return False
        self.users.delete(user)
        return True
