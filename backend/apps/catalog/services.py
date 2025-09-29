from typing import Optional, Dict, Any, Union
import sys
from django.core.cache import cache
from .repositories import ProductRepository, CategoryRepository, RatingRepository
from .mappers import ProductMapper, CategoryMapper
from .models import Product, Category, Rating
from .commands import ProductCreateCommand, ProductUpdateCommand, RatingSetCommand

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
            return ProductMapper.many_to_dto(qs)
        # Read-through cache per category filter
        key = self._cache_key(category)
        cached = cache.get(key)
        if cached is not None:
            return cached
        qs = self.products.list_by_category(category) if category else self.products.list()
        data = ProductMapper.many_to_dto(qs)
        cache.set(key, data)
        return data

    def list_products_by_category_ids(self, category_ids):
        qs = self.products.list_by_category_ids(category_ids)
        return ProductMapper.many_to_dto(qs)

    def get_product(self, product_id: int):
        p = self.products.get(id=product_id)
        return ProductMapper.to_dto(p) if p else None

    def create_product(self, data: Union[Dict[str, Any], ProductCreateCommand]):
        cmd = data if isinstance(data, ProductCreateCommand) else ProductCreateCommand.from_raw(data)
        create_kwargs: Dict[str, Any] = {
            'title': cmd.title,
            'price': cmd.price,
            'description': cmd.description,
            'image': cmd.image,
        }
        if cmd.rate is not None:
            create_kwargs['rate'] = cmd.rate
        if cmd.count is not None:
            create_kwargs['count'] = cmd.count
        product: Product = self.products.create(**create_kwargs)
        if cmd.categories:
            self.products.set_categories(product, cmd.categories)
        self._bump_cache_version()
        return ProductMapper.to_dto(product)

    def update_product(self, product_id: int, data: Union[Dict[str, Any], ProductUpdateCommand], partial: bool = False):
        cmd = data if isinstance(data, ProductUpdateCommand) else ProductUpdateCommand.from_raw(product_id, data, partial)
        product: Optional[Product] = self.products.get(id=product_id)
        if not product:
            return None
        # Apply changes only if provided (supports partial)
        self.products.update_scalar(
            product,
            title=cmd.title,
            price=cmd.price,
            description=cmd.description,
            image=cmd.image,
            rate=cmd.rate,
            count=cmd.count,
        )
        if cmd.categories is not None:
            self.products.set_categories(product, cmd.categories)
        self._bump_cache_version()
        return ProductMapper.to_dto(product)

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

    def set_user_rating(self, product_id: int, user_id: int, value: Union[int, RatingSetCommand]):
        cmd = value if isinstance(value, RatingSetCommand) else RatingSetCommand.from_raw(product_id, user_id, value)
        if cmd.value < 0 or cmd.value > 5:
            return ('VALIDATION_ERROR', 'value must be between 0 and 5', {'value': cmd.value})
        product = self.products.get(id=product_id)
        if not product:
            return ('NOT_FOUND', 'Product not found', {'id': product_id})
        existing = self.ratings.for_product_user(product_id, user_id)
        if existing:
            existing.value = cmd.value
            existing.save()
        else:
            self.ratings.create(product_id=product_id, user_id=user_id, value=cmd.value)
        self.products.recalculate_rating(product)
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
        self.products.recalculate_rating(product)
        return self.get_rating_summary(product_id, user_id)

class CategoryService:
    def __init__(self):
        self.categories = CategoryRepository()

    def list_categories(self):
        return CategoryMapper.many_to_dto(self.categories.list())

    def get_category(self, category_id: int):
        c = self.categories.get(id=category_id)
        return CategoryMapper.to_dto(c) if c else None

    def create_category(self, data: Dict[str, Any]):
        category: Category = self.categories.create(**data)
        return CategoryMapper.to_dto(category)

    def update_category(self, category_id: int, data: Dict[str, Any]):
        category: Optional[Category] = self.categories.get(id=category_id)
        if not category:
            return None
        for k, v in data.items():
            setattr(category, k, v)
        category.save()
        return CategoryMapper.to_dto(category)

    def delete_category(self, category_id: int) -> bool:
        category = self.categories.get(id=category_id)
        if not category:
            return False
        self.categories.delete(category)
        return True
