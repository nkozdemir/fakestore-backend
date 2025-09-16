from dataclasses import dataclass
from typing import List
from .models import Cart, CartProduct
from apps.catalog.dtos import ProductDTO, product_to_dto

@dataclass
class CartProductDTO:
    product: ProductDTO
    quantity: int

@dataclass
class CartDTO:
    id: int
    user_id: int
    date: str
    items: List[CartProductDTO]

def cart_product_to_dto(cp: CartProduct) -> CartProductDTO:
    return CartProductDTO(product=product_to_dto(cp.product), quantity=cp.quantity)

def cart_to_dto(c: Cart) -> CartDTO:
    items = [cart_product_to_dto(cp) for cp in c.cart_products.all()]
    return CartDTO(id=c.id, user_id=c.user_id, date=str(c.date), items=items)
