from typing import Optional, Dict, Any
from .repositories import ProductRepository, CategoryRepository
from .dtos import product_to_dto, category_to_dto
from .models import Product, Category

class ProductService:
    def __init__(self):
        self.products = ProductRepository()

    def list_products(self, category: Optional[str] = None):
        qs = self.products.list_by_category(category) if category else self.products.list()
        return [product_to_dto(p) for p in qs]

    def list_products_by_category_ids(self, category_ids):
        qs = self.products.list_by_category_ids(category_ids)
        return [product_to_dto(p) for p in qs]

    def get_product(self, product_id: int):
        p = self.products.get(id=product_id)
        return product_to_dto(p) if p else None

    def create_product(self, data: Dict[str, Any]):
        categories = data.pop('categories', []) or []
        product: Product = self.products.create(**data)
        if categories:
            product.categories.set(Category.objects.filter(id__in=categories))
        return product_to_dto(product)

    def update_product(self, product_id: int, data: Dict[str, Any], partial: bool = False):
        product: Optional[Product] = self.products.get(id=product_id)
        if not product:
            return None
        categories = data.pop('categories', None)
        if not partial:
            # Full replace semantics: unspecified fields should be set explicitly by caller.
            pass
        for k, v in data.items():
            setattr(product, k, v)
        product.save()
        if categories is not None:
            product.categories.set(Category.objects.filter(id__in=categories))
        return product_to_dto(product)

    def delete_product(self, product_id: int) -> bool:
        product = self.products.get(id=product_id)
        if not product:
            return False
        self.products.delete(product)
        return True

class CategoryService:
    def __init__(self):
        self.categories = CategoryRepository()

    def list_categories(self):
        return [category_to_dto(c) for c in self.categories.list()]

    def get_category(self, category_id: int):
        c = self.categories.get(id=category_id)
        return category_to_dto(c) if c else None

    def create_category(self, data: Dict[str, Any]):
        category: Category = self.categories.create(**data)
        return category_to_dto(category)

    def update_category(self, category_id: int, data: Dict[str, Any]):
        category: Optional[Category] = self.categories.get(id=category_id)
        if not category:
            return None
        for k, v in data.items():
            setattr(category, k, v)
        category.save()
        return category_to_dto(category)

    def delete_category(self, category_id: int) -> bool:
        category = self.categories.get(id=category_id)
        if not category:
            return False
        self.categories.delete(category)
        return True
