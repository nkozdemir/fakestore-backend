from __future__ import annotations

from django.core.cache import cache

from .repositories import ProductRepository, CategoryRepository, RatingRepository
from .services import ProductService, CategoryService


def build_product_service(*, disable_cache: bool = False) -> ProductService:
    return ProductService(
        products=ProductRepository(),
        ratings=RatingRepository(),
        cache_backend=cache,
        disable_cache=disable_cache,
    )


def build_category_service() -> CategoryService:
    return CategoryService(categories=CategoryRepository())
