from typing import Iterable, List, Optional
from .models import Cart, CartProduct
from .dtos import CartDTO, CartProductDTO
from apps.catalog.mappers import ProductMapper


class CartProductMapper:
    def __init__(self, product_mapper: Optional[ProductMapper] = None) -> None:
        self.product_mapper = product_mapper or ProductMapper()

    def to_dto(self, cp: CartProduct) -> CartProductDTO:
        product_dto = self.product_mapper.to_dto(cp.product)
        return CartProductDTO(product=product_dto, quantity=cp.quantity)

    def many_to_dto(self, items: Iterable[CartProduct]) -> List[CartProductDTO]:
        return [self.to_dto(i) for i in items]


class CartMapper:
    def __init__(self, cart_product_mapper: Optional[CartProductMapper] = None) -> None:
        self.cart_product_mapper = cart_product_mapper or CartProductMapper()

    def to_dto(self, cart: Cart) -> CartDTO:
        items = self.cart_product_mapper.many_to_dto(cart.cart_products.all())
        return CartDTO(
            id=cart.id, user_id=cart.user_id, date=str(cart.date), items=items
        )

    def many_to_dto(self, carts: Iterable[Cart]) -> List[CartDTO]:
        return [self.to_dto(c) for c in carts]
