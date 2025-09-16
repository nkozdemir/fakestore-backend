from typing import Type, TypeVar, Generic, Iterable, Optional
from django.db import models

T = TypeVar('T', bound=models.Model)

class GenericRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    def get(self, **filters) -> Optional[T]:
        return self.model.objects.filter(**filters).first()

    def list(self, **filters) -> Iterable[T]:
        return self.model.objects.filter(**filters)

    def create(self, **data) -> T:
        return self.model.objects.create(**data)

    def update(self, obj: T, **data) -> T:
        for k, v in data.items():
            setattr(obj, k, v)
        obj.save()
        return obj

    def delete(self, obj: T):
        obj.delete()
