from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from django.db import transaction
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.common import get_logger
from apps.common.i18n import (
    get_default_language,
    is_supported_language,
    iter_supported_languages,
    normalize_language_code,
)
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
        self._default_language = get_default_language()
        self._supported_languages = tuple(iter_supported_languages())

    def _normalize_language(self, language: Optional[str]) -> str:
        if language:
            normalized = language.split("-")[0].lower()
            if normalized in self._supported_languages:
                return normalized
        return self._default_language

    def _get_cache_version(self) -> int:
        v = self.cache.get(self._cache_version_key)
        return v or self._default_version

    def _bump_cache_version(self) -> None:
        v = self._get_cache_version()
        # Version key should not expire
        self.cache.set(self._cache_version_key, v + 1, timeout=None)
        self.logger.debug("Bumped product cache version", new_version=v + 1)

    def _cache_key(self, category: Optional[str], language: str) -> str:
        version = self._get_cache_version()
        cat = category or "all"
        return f"{self._cache_prefix}:v{version}:{cat}:lang-{language}"

    def list_products(
        self, category: Optional[str] = None, *, language: Optional[str] = None
    ):
        language = self._normalize_language(language)
        self.logger.debug(
            "Listing products",
            category=category,
            cache_enabled=not self.disable_cache,
            language=language,
        )
        if self.disable_cache:
            qs = (
                self.products.list_by_category(category)
                if category
                else self.products.list()
            )
            return ProductMapper.many_to_dto(qs, language=language)
        # Read-through cache per category filter
        key = self._cache_key(category, language)
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
        data = ProductMapper.many_to_dto(qs, language=language)
        self.cache.set(key, data)
        return data

    def list_products_paginated(
        self,
        request,
        *,
        category: Optional[str] = None,
        paginator_class: Optional[Type[PageNumberPagination]] = None,
        serializer_class=None,
        view=None,
        language: Optional[str] = None,
    ):
        language = self._normalize_language(language)
        paginator_cls = paginator_class or PageNumberPagination
        queryset = self.products_queryset(category=category)
        paginator = paginator_cls()
        page = paginator.paginate_queryset(queryset, request, view=view)
        data_source = page if page is not None else queryset
        dtos = ProductMapper.many_to_dto(data_source, language=language)
        if serializer_class is None:
            from .serializers import ProductReadSerializer  # Avoid circular import

            serializer_class = ProductReadSerializer
        serializer = serializer_class(dtos, many=True)
        if page is None:
            return Response(serializer.data)
        return paginator.get_paginated_response(serializer.data)

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

    def get_product(self, product_id: int, *, language: Optional[str] = None):
        language = self._normalize_language(language)
        self.logger.debug("Fetching product", product_id=product_id, language=language)
        p = self.products.get(id=product_id)
        if not p:
            self.logger.info("Product not found", product_id=product_id)
        return ProductMapper.to_dto(p, language=language) if p else None

    def create_product(
        self,
        data: Union[Dict[str, Any], ProductCreateCommand],
        *,
        language: Optional[str] = None,
    ):
        language = self._normalize_language(language)
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
        self._ensure_product_translation(product)
        self._sync_product_translations(product, cmd.translations)
        self._bump_cache_version()
        self.logger.info("Product created", product_id=product.id)
        return ProductMapper.to_dto(product, language=language)

    def update_product(
        self,
        product_id: int,
        data: Union[Dict[str, Any], ProductUpdateCommand],
        partial: bool = False,
        *,
        language: Optional[str] = None,
    ):
        language = self._normalize_language(language)
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
        self._ensure_product_translation(product)
        self._sync_product_translations(product, cmd.translations)
        self._bump_cache_version()
        self.logger.info("Product updated", product_id=product_id)
        return ProductMapper.to_dto(product, language=language)

    def delete_product_with_auth(
        self, product_id: int
    ) -> Tuple[bool, Optional[Tuple[str, str, Optional[Dict[str, Any]]]]]:
        self.logger.info("Deleting product", product_id=product_id)
        product = self.products.get(id=product_id)
        if not product:
            self.logger.warning(
                "Product deletion failed: not found", product_id=product_id
            )
            return False, ("NOT_FOUND", "Product not found", {"id": str(product_id)})
        self.products.delete(product)
        self._bump_cache_version()
        self.logger.info("Product deleted", product_id=product_id)
        return True, None

    def delete_product(self, product_id: int) -> bool:
        deleted, _ = self.delete_product_with_auth(product_id)
        return deleted

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

    def _get_translation_manager(self, obj):
        manager = getattr(obj, "translations", None)
        if manager is None or not hasattr(manager, "update_or_create"):
            return None
        return manager

    def _ensure_product_translation(self, product: Product):
        manager = self._get_translation_manager(product)
        if manager is None:
            return
        manager.update_or_create(
            language=self._default_language,
            defaults={
                "title": product.title,
                "description": product.description,
            },
        )

    def _sync_product_translations(
        self, product: Product, translations: Optional[List[Dict[str, Any]]]
    ):
        if not translations:
            return
        manager = self._get_translation_manager(product)
        if manager is None:
            return
        for entry in translations:
            language = entry.get("language")
            if not language or not is_supported_language(language):
                continue
            normalized = self._normalize_language(language)
            title = entry.get("title") or product.title
            description = entry.get("description") or product.description
            manager.update_or_create(
                language=normalized,
                defaults={
                    "title": title,
                    "description": description,
                },
            )


class CategoryService:
    def __init__(self, categories: CategoryRepositoryProtocol):
        self.categories = categories
        self.logger = logger.bind(service="CategoryService")
        self._default_language = get_default_language()
        self._supported_languages = tuple(iter_supported_languages())

    def _normalize_language(self, language: Optional[str]) -> str:
        if language:
            normalized = language.split("-")[0].lower()
            if normalized in self._supported_languages:
                return normalized
        return self._default_language

    def list_categories(self, language: Optional[str] = None):
        language = self._normalize_language(language)
        self.logger.debug("Listing categories", language=language)
        return CategoryMapper.many_to_dto(
            self.categories.list(), language=language
        )

    def get_category(self, category_id: int, *, language: Optional[str] = None):
        language = self._normalize_language(language)
        self.logger.debug("Fetching category", category_id=category_id, language=language)
        c = self.categories.get(id=category_id)
        if not c:
            self.logger.info("Category not found", category_id=category_id)
        return CategoryMapper.to_dto(c, language=language) if c else None

    def create_category(
        self, data: Dict[str, Any], *, language: Optional[str] = None
    ):
        language = self._normalize_language(language)
        payload = dict(data)
        translations = payload.pop("translations", None)
        self.logger.info("Creating category", name=payload.get("name"))
        category: Category = self.categories.create(**payload)
        self._ensure_category_translation(category)
        self._sync_category_translations(category, translations)
        self.logger.info("Category created", category_id=category.id)
        return CategoryMapper.to_dto(category, language=language)

    def create_category_with_auth(
        self,
        data: Dict[str, Any],
        *,
        language: Optional[str] = None,
    ) -> Tuple[Any, Optional[Tuple[str, str, Optional[Dict[str, Any]]]]]:
        dto = self.create_category(data, language=language)
        return dto, None

    def update_category(
        self, category_id: int, data: Dict[str, Any], *, language: Optional[str] = None
    ):
        language = self._normalize_language(language)
        self.logger.info("Updating category", category_id=category_id)
        payload = dict(data)
        translations = payload.pop("translations", None)
        category: Optional[Category] = self.categories.get(id=category_id)
        if not category:
            self.logger.warning(
                "Category update failed: not found", category_id=category_id
            )
            return None
        for k, v in payload.items():
            setattr(category, k, v)
        category.save()
        self._ensure_category_translation(category)
        self._sync_category_translations(category, translations)
        self.logger.info("Category updated", category_id=category_id)
        return CategoryMapper.to_dto(category, language=language)

    def update_category_with_auth(
        self,
        category_id: int,
        data: Dict[str, Any],
        *,
        language: Optional[str] = None,
    ) -> Tuple[Optional[Any], Optional[Tuple[str, str, Optional[Dict[str, Any]]]]]:
        dto = self.update_category(category_id, data, language=language)
        if not dto:
            return (
                None,
                (
                    "NOT_FOUND",
                    "Category not found",
                    {"id": str(category_id)},
                ),
            )
        return dto, None

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

    def delete_category_with_auth(
        self, category_id: int
    ) -> Tuple[bool, Optional[Tuple[str, str, Optional[Dict[str, Any]]]]]:
        deleted = self.delete_category(category_id)
        if not deleted:
            return False, ("NOT_FOUND", "Category not found", {"id": str(category_id)})
        return True, None

    def _get_translation_manager(self, category: Category):
        manager = getattr(category, "translations", None)
        if manager is None or not hasattr(manager, "update_or_create"):
            return None
        return manager

    def _ensure_category_translation(self, category: Category):
        manager = self._get_translation_manager(category)
        if manager is None:
            return
        manager.update_or_create(
            language=self._default_language,
            defaults={"name": category.name},
        )

    def _sync_category_translations(
        self, category: Category, translations: Optional[List[Dict[str, Any]]]
    ):
        if not translations:
            return
        manager = self._get_translation_manager(category)
        if manager is None:
            return
        for entry in translations:
            language = entry.get("language")
            if not language or not is_supported_language(language):
                continue
            normalized = self._normalize_language(language)
            name = entry.get("name") or category.name
            manager.update_or_create(
                language=normalized,
                defaults={"name": name},
            )
