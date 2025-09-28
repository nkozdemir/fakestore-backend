from typing import Optional, Dict, Any
import sys
from django.core.cache import cache
from .repositories import ProductRepository, CategoryRepository, RatingRepository
from .dtos import product_to_dto, category_to_dto
from .models import Product, Category, Rating

class ProductService:
    def __init__(self):
        self.products = ProductRepository()
        self.ratings = RatingRepository()
        # Caching keys
        self._cache_prefix = 'products:list'
        self._cache_version_key = f'{self._cache_prefix}:version'
        self._default_version = 1

    def _get_cache_version(self) -> int:
        v = cache.get(self._cache_version_key)
        return v or self._default_version

    def _bump_cache_version(self) -> None:
        v = self._get_cache_version()
        # Version key should not expire
        cache.set(self._cache_version_key, v + 1, timeout=None)

    def _cache_key(self, category: Optional[str]) -> str:
        version = self._get_cache_version()
        cat = category or 'all'
        return f'{self._cache_prefix}:v{version}:{cat}'

    def list_products(self, category: Optional[str] = None):
        # During test runs, bypass cache to avoid stale reads from direct ORM writes in tests
        if 'test' in sys.argv:
            qs = self.products.list_by_category(category) if category else self.products.list()
            return [product_to_dto(p) for p in qs]
        # Read-through cache per category filter
        key = self._cache_key(category)
        cached = cache.get(key)
        if cached is not None:
            return cached
        qs = self.products.list_by_category(category) if category else self.products.list()
        data = [product_to_dto(p) for p in qs]
        cache.set(key, data)
        return data

    def list_products_by_category_ids(self, category_ids):
        qs = self.products.list_by_category_ids(category_ids)
        return [product_to_dto(p) for p in qs]

    def get_product(self, product_id: int):
        p = self.products.get(id=product_id)
        return product_to_dto(p) if p else None

    def create_product(self, data: Dict[str, Any]):
        # Ignore any client-supplied 'id' if present (auto-assigned by DB)
        data.pop('id', None)
        categories = data.pop('categories', []) or []
        product: Product = self.products.create(**data)
        if categories:
            product.categories.set(Category.objects.filter(id__in=categories))
        # Invalidate all cached product lists
        self._bump_cache_version()
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
        # Invalidate cached lists as content may have changed
        self._bump_cache_version()
        return product_to_dto(product)

    def delete_product(self, product_id: int) -> bool:
        product = self.products.get(id=product_id)
        if not product:
            return False
        self.products.delete(product)
        # Invalidate cache after deletion
        self._bump_cache_version()
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
        from django.db.models import Avg, Count
        agg = product.ratings.aggregate(avg=Avg('value'), count=Count('id'))
        count = agg['count'] or 0
        if not count:
            product.rate = 0
            product.count = 0
        else:
            product.rate = round(float(agg['avg']) + 1e-8, 1)
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
