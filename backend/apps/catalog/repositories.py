from apps.common.repository import GenericRepository
from .models import Category, Product, Rating

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

class RatingRepository(GenericRepository[Rating]):
    def __init__(self):
        super().__init__(Rating)

    def for_product_user(self, product_id: int, user_id: int):
        return self.model.objects.filter(product_id=product_id, user_id=user_id).first()

    def list_for_product(self, product_id: int):
        return self.model.objects.filter(product_id=product_id)
