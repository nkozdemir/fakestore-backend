from __future__ import annotations

from typing import Optional, Dict, Any, Union

from django.db import transaction

from apps.common import get_logger
from .mappers import ProductMapper, CategoryMapper
from .models import Product, Category, Rating
from .commands import ProductCreateCommand, ProductUpdateCommand, RatingSetCommand
from .protocols import (
    CacheBackendProtocol,
    CategoryRepositoryProtocol,
    ProductRepositoryProtocol,
    RatingRepositoryProtocol,
)
from apps.users.models import User

logger = get_logger(__name__).bind(component="catalog", layer="service")


class ProductService:
    def __init__(
        self,
        products: ProductRepositoryProtocol,
        ratings: RatingRepositoryProtocol,
        cache_backend: CacheBackendProtocol,
        disable_cache: bool = False,
    ):
        self.products = products
        self.ratings = ratings
        self.cache = cache_backend
        self.disable_cache = disable_cache
        self.logger = logger.bind(service="ProductService")
        # Caching keys
        self._cache_prefix = "products:list"
        self._cache_version_key = f"{self._cache_prefix}:version"
        self._default_version = 1

    def _get_cache_version(self) -> int:
        v = self.cache.get(self._cache_version_key)
        return v or self._default_version

    def _bump_cache_version(self) -> None:
        v = self._get_cache_version()
        # Version key should not expire
        self.cache.set(self._cache_version_key, v + 1, timeout=None)
        self.logger.debug("Bumped product cache version", new_version=v + 1)

    def _cache_key(self, category: Optional[str]) -> str:
        version = self._get_cache_version()
        cat = category or "all"
        return f"{self._cache_prefix}:v{version}:{cat}"

    def list_products(self, category: Optional[str] = None):
        self.logger.debug(
            "Listing products", category=category, cache_enabled=not self.disable_cache
        )
        if self.disable_cache:
            qs = (
                self.products.list_by_category(category)
                if category
                else self.products.list()
            )
            return ProductMapper.many_to_dto(qs)
        # Read-through cache per category filter
        key = self._cache_key(category)
        cached = self.cache.get(key)
        if cached is not None:
            self.logger.debug("Product list cache hit", cache_key=key)
            return cached
        self.logger.debug("Product list cache miss", cache_key=key)
        qs = (
            self.products.list_by_category(category)
            if category
            else self.products.list()
        )
        data = ProductMapper.many_to_dto(qs)
        self.cache.set(key, data)
        return data

    def products_queryset(self, category: Optional[str] = None):
        """Return a queryset for products with categories prefetched."""
        self.logger.debug(
            "Building product queryset for pagination", category=category
        )
        return (
            self.products.list_by_category(category)
            if category
            else self.products.list()
        )

    def get_product(self, product_id: int):
        self.logger.debug("Fetching product", product_id=product_id)
        p = self.products.get(id=product_id)
        if not p:
            self.logger.info("Product not found", product_id=product_id)
        return ProductMapper.to_dto(p) if p else None

    def create_product(self, data: Union[Dict[str, Any], ProductCreateCommand]):
        cmd = (
            data
            if isinstance(data, ProductCreateCommand)
            else ProductCreateCommand.from_raw(data)
        )
        self.logger.info("Creating product", title=cmd.title)
        create_kwargs: Dict[str, Any] = {
            "title": cmd.title,
            "price": cmd.price,
            "description": cmd.description,
            "image": cmd.image,
        }
        if cmd.rate is not None:
            create_kwargs["rate"] = cmd.rate
        if cmd.count is not None:
            create_kwargs["count"] = cmd.count
        product: Product = self.products.create(**create_kwargs)
        if cmd.categories:
            self.products.set_categories(product, cmd.categories)
        self._bump_cache_version()
        self.logger.info("Product created", product_id=product.id)
        return ProductMapper.to_dto(product)

    def update_product(
        self,
        product_id: int,
        data: Union[Dict[str, Any], ProductUpdateCommand],
        partial: bool = False,
    ):
        cmd = (
            data
            if isinstance(data, ProductUpdateCommand)
            else ProductUpdateCommand.from_raw(product_id, data, partial)
        )
        self.logger.info("Updating product", product_id=product_id, partial=partial)
        product: Optional[Product] = self.products.get(id=product_id)
        if not product:
            self.logger.warning(
                "Product update failed: not found", product_id=product_id
            )
            return None
        update_kwargs: Dict[str, Any] = {
            "title": cmd.title,
            "price": cmd.price,
            "description": cmd.description,
            "image": cmd.image,
            "rate": cmd.rate,
            "count": cmd.count,
        }
        original_fields = {
            field: getattr(product, field)
            for field, value in update_kwargs.items()
            if value is not None
        }
        original_categories = None
        if cmd.categories is not None:
            try:
                original_categories = list(product.categories.all())
            except Exception:
                original_categories = None
        try:
            with transaction.atomic():
                self.products.update_scalar(product, **update_kwargs)
                if cmd.categories is not None:
                    self.products.set_categories(product, cmd.categories)
        except Exception:
            for field, value in original_fields.items():
                setattr(product, field, value)
            if (
                cmd.categories is not None
                and original_categories is not None
                and hasattr(product, "categories")
            ):
                try:
                    product.categories.set(original_categories)
                except Exception:
                    # Best effort restore, do not mask original error.
                    pass
            raise
        self._bump_cache_version()
        self.logger.info("Product updated", product_id=product_id)
        return ProductMapper.to_dto(product)

    def delete_product(self, product_id: int) -> bool:
        self.logger.info("Deleting product", product_id=product_id)
        product = self.products.get(id=product_id)
        if not product:
            self.logger.warning(
                "Product deletion failed: not found", product_id=product_id
            )
            return False
        self.products.delete(product)
        # Invalidate cache after deletion
        self._bump_cache_version()
        self.logger.info("Product deleted", product_id=product_id)
        return True

    # Rating related methods
    def get_rating_summary(self, product_id: int, user_id: Optional[int] = None):
        product = self.products.get(id=product_id)
        if not product:
            self.logger.info(
                "Rating summary requested for missing product",
                product_id=product_id,
                user_id=user_id,
            )
            return None
        user_rating = None
        if user_id:
            r = self.ratings.for_product_user(product_id, user_id)
            if r:
                user_rating = r.value
        self.logger.debug(
            "Returning rating summary", product_id=product_id, user_id=user_id
        )
        return {
            "productId": product_id,
            "rating": {"rate": float(product.rate), "count": product.count},
            "userRating": user_rating,
        }

    def list_product_ratings(self, product_id: int):
        product = self.products.get(id=product_id)
        if not product:
            self.logger.info(
                "Product ratings requested for missing product",
                product_id=product_id,
            )
            return ("NOT_FOUND", "Product not found", {"id": product_id})
        ratings = list(self.ratings.list_for_product(product_id))
        user_ids = {
            getattr(rating, "user_id", None)
            for rating in ratings
            if getattr(rating, "user_id", None) is not None
        }
        user_map = {}
        if user_ids:
            users = User.objects.filter(id__in=user_ids).values(
                "id", "first_name", "last_name"
            )
            user_map = {user["id"]: user for user in users}
        entries: List[Dict[str, Any]] = []
        for rating in ratings:
            rating_user_id = getattr(rating, "user_id", None)
            user_payload = user_map.get(rating_user_id)
            if not user_payload and hasattr(rating, "user"):
                user_obj = getattr(rating, "user", None)
                if user_obj is not None:
                    user_payload = {
                        "first_name": getattr(user_obj, "first_name", None),
                        "last_name": getattr(user_obj, "last_name", None),
                    }
            created_at = getattr(rating, "created_at", None)
            updated_at = getattr(rating, "updated_at", None)
            entry: Dict[str, Any] = {
                "id": getattr(rating, "id", None),
                "value": getattr(rating, "value", None),
                "createdAt": created_at.isoformat() if created_at else None,
                "updatedAt": updated_at.isoformat() if updated_at else None,
            }
            if user_payload:
                entry.update(
                    {
                        "firstName": user_payload.get("first_name"),
                        "lastName": user_payload.get("last_name"),
                    }
                )
            entries.append(entry)
        self.logger.debug(
            "Returning product ratings",
            product_id=product_id,
            count=len(entries),
        )
        return {
            "productId": product_id,
            "count": len(entries),
            "ratings": entries,
        }

    def set_user_rating(
        self, product_id: int, user_id: int, value: Union[int, RatingSetCommand]
    ):
        cmd = (
            value
            if isinstance(value, RatingSetCommand)
            else RatingSetCommand.from_raw(product_id, user_id, value)
        )
        if cmd.value < 0 or cmd.value > 5:
            self.logger.warning(
                "Rejecting rating outside bounds",
                product_id=product_id,
                user_id=user_id,
                value=cmd.value,
            )
            return (
                "VALIDATION_ERROR",
                "value must be between 0 and 5",
                {"value": cmd.value},
            )
        product = self.products.get(id=product_id)
        if not product:
            self.logger.warning(
                "Rating failed: product not found",
                product_id=product_id,
                user_id=user_id,
            )
            return ("NOT_FOUND", "Product not found", {"id": product_id})
        if not User.objects.filter(id=user_id).exists():
            self.logger.warning(
                "Rating failed: user not found",
                product_id=product_id,
                user_id=user_id,
            )
            return ("NOT_FOUND", "User not found", {"userId": user_id})
        existing = self.ratings.for_product_user(product_id, user_id)
        if existing:
            existing.value = cmd.value
            existing.save()
            self.logger.info(
                "Updated product rating",
                product_id=product_id,
                user_id=user_id,
                value=cmd.value,
            )
        else:
            self.ratings.create(product_id=product_id, user_id=user_id, value=cmd.value)
            self.logger.info(
                "Created product rating",
                product_id=product_id,
                user_id=user_id,
                value=cmd.value,
            )
        self.products.recalculate_rating(product)
        return self.get_rating_summary(product_id, user_id)

    def delete_rating(
        self,
        product_id: int,
        rating_id: int,
        actor_user_id: Optional[int],
        is_privileged: bool,
    ):
        self.logger.info(
            "Deleting rating",
            product_id=product_id,
            rating_id=rating_id,
            actor_user_id=actor_user_id,
            privileged=is_privileged,
        )
        rating = self.ratings.get(id=rating_id, product_id=product_id)
        if not rating:
            self.logger.warning(
                "Rating delete failed: not found",
                product_id=product_id,
                rating_id=rating_id,
            )
            return ("NOT_FOUND", "Rating not found", {"ratingId": rating_id})
        owner_user_id = getattr(rating, "user_id", None)
        if not is_privileged:
            if actor_user_id is None or owner_user_id != actor_user_id:
                self.logger.warning(
                    "Rating delete forbidden",
                    product_id=product_id,
                    rating_id=rating_id,
                    actor_user_id=actor_user_id,
                    owner_user_id=owner_user_id,
                )
                return (
                    "FORBIDDEN",
                    "You do not have permission to delete this rating",
                    {"ratingId": rating_id},
                )
        product = getattr(rating, "product", None)
        if product is None:
            product = self.products.get(id=product_id)
            if not product:
                self.logger.warning(
                    "Rating delete failed: product not found",
                    product_id=product_id,
                    rating_id=rating_id,
                )
                return ("NOT_FOUND", "Product not found", {"id": product_id})
        self.ratings.delete(rating)
        self.products.recalculate_rating(product)
        summary_user_id = actor_user_id if not is_privileged else actor_user_id
        summary = self.get_rating_summary(product_id, summary_user_id)
        if summary is None:
            summary = {
                "productId": product_id,
                "rating": {"rate": float(product.rate), "count": product.count},
                "userRating": None,
            }
        self.logger.info(
            "Deleted rating",
            product_id=product_id,
            rating_id=rating_id,
            actor_user_id=actor_user_id,
        )
        return summary


class CategoryService:
    def __init__(self, categories: CategoryRepositoryProtocol):
        self.categories = categories
        self.logger = logger.bind(service="CategoryService")

    def list_categories(self):
        self.logger.debug("Listing categories")
        return CategoryMapper.many_to_dto(self.categories.list())

    def get_category(self, category_id: int):
        self.logger.debug("Fetching category", category_id=category_id)
        c = self.categories.get(id=category_id)
        if not c:
            self.logger.info("Category not found", category_id=category_id)
        return CategoryMapper.to_dto(c) if c else None

    def create_category(self, data: Dict[str, Any]):
        self.logger.info("Creating category", name=data.get("name"))
        category: Category = self.categories.create(**data)
        self.logger.info("Category created", category_id=category.id)
        return CategoryMapper.to_dto(category)

    def update_category(self, category_id: int, data: Dict[str, Any]):
        self.logger.info("Updating category", category_id=category_id)
        category: Optional[Category] = self.categories.get(id=category_id)
        if not category:
            self.logger.warning(
                "Category update failed: not found", category_id=category_id
            )
            return None
        for k, v in data.items():
            setattr(category, k, v)
        category.save()
        self.logger.info("Category updated", category_id=category_id)
        return CategoryMapper.to_dto(category)

    def delete_category(self, category_id: int) -> bool:
        self.logger.info("Deleting category", category_id=category_id)
        category = self.categories.get(id=category_id)
        if not category:
            self.logger.warning(
                "Category deletion failed: not found", category_id=category_id
            )
            return False
        self.logger.debug(
            "Detaching category from products before delete", category_id=category_id
        )
        self.categories.detach_from_products(category)
        self.categories.delete(category)
        self.logger.info("Category deleted", category_id=category_id)
        return True
