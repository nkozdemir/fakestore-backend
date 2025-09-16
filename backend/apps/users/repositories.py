from apps.common.repository import GenericRepository
from .models import User, Address

class UserRepository(GenericRepository[User]):
    def __init__(self):
        super().__init__(User)

class AddressRepository(GenericRepository[Address]):
    def __init__(self):
        super().__init__(Address)
