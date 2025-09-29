from typing import Iterable, List
from .models import Cart, CartProduct
from .dtos import CartDTO, CartProductDTO
from apps.catalog.mappers import ProductMapper


class CartProductMapper:
    @staticmethod
    def to_dto(cp: CartProduct) -> CartProductDTO:
        return CartProductDTO(product=ProductMapper.to_dto(cp.product), quantity=cp.quantity)

    @staticmethod
    def many_to_dto(items: Iterable[CartProduct]) -> List[CartProductDTO]:
        return [CartProductMapper.to_dto(i) for i in items]


class CartMapper:
    @staticmethod
    def to_dto(cart: Cart) -> CartDTO:
        items = CartProductMapper.many_to_dto(cart.cart_products.all())
        return CartDTO(id=cart.id, user_id=cart.user_id, date=str(cart.date), items=items)

    @staticmethod
    def many_to_dto(carts: Iterable[Cart]) -> List[CartDTO]:
        return [CartMapper.to_dto(c) for c in carts]
