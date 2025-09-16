from typing import Optional, Dict, Any
from .repositories import ProductRepository, CategoryRepository, RatingRepository
from .dtos import product_to_dto, category_to_dto
from .models import Product, Category, Rating

class ProductService:
    def __init__(self):
        self.products = ProductRepository()
        self.ratings = RatingRepository()

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

    # Rating related methods
    def get_rating_summary(self, product_id: int, user_id: Optional[int] = None):
        product = self.products.get(id=product_id)
        if not product:
            return None
        user_rating = None
        if user_id:
            r = self.ratings.for_product_user(product_id, user_id)
            if r:
                user_rating = r.value
        return {
            'productId': product_id,
            'rating': {
                'rate': float(product.rate),
                'count': product.count
            },
            'userRating': user_rating
        }

    def set_user_rating(self, product_id: int, user_id: int, value: int):
        if value < 0 or value > 5:
            return ('VALIDATION_ERROR', 'value must be between 0 and 5', {'value': value})
        product = self.products.get(id=product_id)
        if not product:
            return ('NOT_FOUND', 'Product not found', {'id': product_id})
        existing = self.ratings.for_product_user(product_id, user_id)
        if existing:
            existing.value = value
            existing.save()
        else:
            self.ratings.create(product_id=product_id, user_id=user_id, value=value)
        self._recalculate_product_rating(product)
        return self.get_rating_summary(product_id, user_id)

    def delete_user_rating(self, product_id: int, user_id: int):
        product = self.products.get(id=product_id)
        if not product:
            return ('NOT_FOUND', 'Product not found', {'id': product_id})
        existing = self.ratings.for_product_user(product_id, user_id)
        if not existing:
            # Idempotent delete - still return summary
            return self.get_rating_summary(product_id, user_id)
        existing.delete()
        self._recalculate_product_rating(product)
        return self.get_rating_summary(product_id, user_id)

    def _recalculate_product_rating(self, product: Product):
        qs = product.ratings.all()
        count = qs.count()
        if count == 0:
            product.rate = 0
            product.count = 0
        else:
            total = sum(r.value for r in qs)
            avg = total / count
            # one decimal place rounding
            product.rate = round(avg + 1e-8, 1)
            product.count = count
        product.save(update_fields=['rate', 'count'])

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
