from apps.common.repository import GenericRepository
from .models import Category, Product

class CategoryRepository(GenericRepository[Category]):
    def __init__(self):
        super().__init__(Category)

class ProductRepository(GenericRepository[Product]):
    def __init__(self):
        super().__init__(Product)

    def list_by_category(self, category_name: str):
        return self.model.objects.filter(categories__name=category_name)

    def list_by_category_ids(self, category_ids):
        return self.model.objects.filter(categories__id__in=category_ids).distinct()
