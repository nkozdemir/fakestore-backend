from apps.common.repository import GenericRepository
from .models import User, Address


class UserRepository(GenericRepository[User]):
    def __init__(self):
        super().__init__(User)

    def _base_queryset(self):
        return self.model.objects.prefetch_related("addresses")

    def list(self, **filters):
        return self._base_queryset().filter(**filters)

    def get(self, **filters):
        return self._base_queryset().filter(**filters).first()

    def create_user(self, **data) -> User:
        return User.objects.create_user(**data)


class AddressRepository(GenericRepository[Address]):
    def __init__(self):
        super().__init__(Address)
