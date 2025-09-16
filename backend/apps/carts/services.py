from typing import Optional, Dict, Any
from django.db import transaction
from .repositories import CartRepository, CartProductRepository
from .dtos import cart_to_dto
from .models import Cart, CartProduct
from apps.catalog.models import Product

class CartService:
    def __init__(self):
        self.carts = CartRepository()
        self.cart_products = CartProductRepository()

    def list_carts(self, user_id: Optional[int] = None):
        qs = self.carts.list(user_id=user_id) if user_id else self.carts.list()
        return [cart_to_dto(c) for c in qs]

    def get_cart(self, cart_id: int):
        c = self.carts.get(id=cart_id)
        return cart_to_dto(c) if c else None

    def create_cart(self, data: Dict[str, Any]):
        cart: Cart = self.carts.create(**data)
        return cart_to_dto(cart)

    def update_cart(self, cart_id: int, data: Dict[str, Any]):
        cart: Optional[Cart] = self.carts.get(id=cart_id)
        if not cart:
            return None
        for k, v in data.items():
            setattr(cart, k, v)
        cart.save()
        return cart_to_dto(cart)

    def delete_cart(self, cart_id: int) -> bool:
        cart = self.carts.get(id=cart_id)
        if not cart:
            return False
        self.carts.delete(cart)
        return True

    def patch_operations(self, cart_id: int, ops: Dict[str, Any]):
        """Apply add/update/remove operations on cart line items.
        ops format:
        {
          'add': [{'productId': int, 'quantity': int}],
          'update': [{'productId': int, 'quantity': int}],
          'remove': [productId, ...],
          'date': iso-date-string (optional),
          'userId': int (optional)
        }
        Order: add -> update -> remove
        add: increment quantity (create if missing)
        update: set quantity exactly (create if missing)
        remove: delete line items
        """
        cart: Optional[Cart] = self.carts.get(id=cart_id)
        if not cart:
            return None
        add_ops = ops.get('add') or []
        update_ops = ops.get('update') or []
        remove_ops = ops.get('remove') or []
        new_date = ops.get('date')
        new_user_id = ops.get('userId')

        with transaction.atomic():
            if new_date:
                # Accept either date or datetime string; Cart.date is DateField.
                cart.date = new_date.split('T')[0]
            if new_user_id:
                from apps.users.models import User
                try:
                    cart.user_id = int(new_user_id)
                except (ValueError, TypeError):
                    pass
            cart.save()

            # 1. add -> increment
            for item in add_ops:
                pid = item.get('productId')
                qty = int(item.get('quantity', 0))
                if not pid or qty <= 0:
                    continue
                product = Product.objects.filter(id=pid).first()
                if not product:
                    continue
                cp, created = CartProduct.objects.get_or_create(cart=cart, product=product, defaults={'quantity': qty})
                if not created:
                    cp.quantity += qty
                    cp.save()

            # 2. update -> set
            for item in update_ops:
                pid = item.get('productId')
                qty = int(item.get('quantity', 0))
                if not pid or qty < 0:
                    continue
                product = Product.objects.filter(id=pid).first()
                if not product:
                    continue
                cp, _ = CartProduct.objects.get_or_create(cart=cart, product=product, defaults={'quantity': qty})
                cp.quantity = qty
                cp.save()

            # 3. remove -> delete
            for pid in remove_ops:
                product = Product.objects.filter(id=pid).first()
                if not product:
                    continue
                CartProduct.objects.filter(cart=cart, product=product).delete()

        # Refresh cart for DTO
        cart_refreshed = self.carts.get(id=cart_id)
        return cart_to_dto(cart_refreshed)
