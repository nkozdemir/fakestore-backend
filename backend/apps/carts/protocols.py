from __future__ import annotations

from typing import Iterable, List, Optional, Protocol, TYPE_CHECKING

from .models import Cart, CartProduct

if TYPE_CHECKING:
    from apps.carts.dtos import CartDTO
    from apps.catalog.models import Product


class CartRepositoryProtocol(Protocol):
    def list(self, **filters) -> Iterable[Cart]:
        ...

    def get(self, **filters) -> Optional[Cart]:
        ...

    def create(self, **data) -> Cart:
        ...

    def update_scalar(self, cart: Cart, **fields) -> Cart:
        ...

    def delete(self, cart: Cart) -> None:
        ...


class CartProductRepositoryProtocol(Protocol):
    def create(self, **data) -> CartProduct:
        ...

    def list_for_cart(self, cart_id: int) -> Iterable[CartProduct]:
        ...

    def delete(self, item: CartProduct) -> None:
        ...

    def delete_for_cart(self, cart: Cart) -> None:
        ...

    def get_for_cart_product(self, cart_id: int, product_id: int) -> Optional[CartProduct]:
        ...

    def delete_product(self, cart: Cart, product_id: int) -> None:
        ...


class ProductRepositoryProtocol(Protocol):
    def get(self, **filters) -> Optional["Product"]:
        ...


class CartMapperProtocol(Protocol):
    def to_dto(self, cart: Cart) -> "CartDTO":
        ...

    def many_to_dto(self, carts: Iterable[Cart]) -> List["CartDTO"]:
        ...
