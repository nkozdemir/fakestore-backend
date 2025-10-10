from apps.common.repository import GenericRepository
from .models import User, Address


class UserRepository(GenericRepository[User]):
    def __init__(self):
        super().__init__(User)

    def create_user(self, **data) -> User:
        return User.objects.create_user(**data)


class AddressRepository(GenericRepository[Address]):
    def __init__(self):
        super().__init__(Address)
