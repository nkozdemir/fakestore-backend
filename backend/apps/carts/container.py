from __future__ import annotations

from apps.catalog.mappers import ProductMapper
from apps.catalog.repositories import ProductRepository

from .mappers import CartMapper, CartProductMapper
from .repositories import CartProductRepository, CartRepository
from .services import CartService


def build_cart_service() -> CartService:
    product_mapper = ProductMapper()
    cart_product_mapper = CartProductMapper(product_mapper)
    cart_mapper = CartMapper(cart_product_mapper)
    return CartService(
        carts=CartRepository(),
        cart_products=CartProductRepository(),
        products=ProductRepository(),
        cart_mapper=cart_mapper,
    )
