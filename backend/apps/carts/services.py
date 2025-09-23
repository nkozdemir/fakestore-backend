from typing import Optional, Dict, Any, List
from django.db import transaction
from .repositories import CartRepository, CartProductRepository
from .dtos import cart_to_dto
from .models import Cart, CartProduct
from apps.catalog.models import Product
from django.utils import timezone

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
        payload = dict(data)
        # Map camelCase to model fields
        user_id = payload.get('userId') or payload.get('user_id')
        date = payload.get('date')
        products: Optional[List[Dict[str, Any]]] = payload.get('products')

        create_kwargs: Dict[str, Any] = {}
        if user_id is not None:
            create_kwargs['user_id'] = int(user_id)
        # Default date to today if not provided
        if isinstance(date, str):
            create_kwargs['date'] = date.split('T')[0]
        else:
            create_kwargs['date'] = timezone.now().date()

        # ID will be auto-assigned by database sequence; do not pass it
        with transaction.atomic():
            cart: Cart = self.carts.create(**create_kwargs)
            # If initial products provided, create line items
            if products:
                for item in products:
                    pid = item.get('productId')
                    qty = int(item.get('quantity', 0))
                    if not pid or qty <= 0:
                        continue
                    product = Product.objects.filter(id=pid).first()
                    if not product:
                        continue
                    CartProduct.objects.create(cart=cart, product=product, quantity=qty)
        return cart_to_dto(cart)

    def update_cart(self, cart_id: int, data: Dict[str, Any], user_id: Optional[int] = None):
        # Enforce owner scoping if user_id provided
        filters: Dict[str, Any] = {'id': cart_id}
        if user_id is not None:
            filters['user_id'] = user_id
        cart: Optional[Cart] = self.carts.get(**filters)
        if not cart:
            return None
        payload = dict(data)
        # Extract items for full replacement if provided (including empty list to clear)
        items = payload.pop('items', None)
        # Normalize date (accept ISO string with time)
        if isinstance(payload.get('date'), str) and 'T' in payload['date']:
            payload['date'] = payload['date'].split('T')[0]

        # Only allow known fields on cart
        updates: Dict[str, Any] = {}
        if 'user_id' in payload and payload['user_id'] is not None:
            try:
                updates['user_id'] = int(payload['user_id'])
            except (ValueError, TypeError):
                pass
        if 'date' in payload and payload['date']:
            updates['date'] = payload['date']

        with transaction.atomic():
            # Update scalar fields first
            for k, v in updates.items():
                setattr(cart, k, v)
            cart.save()

            # If 'items' key was supplied, perform full replacement
            if items is not None:
                # Clear existing items
                CartProduct.objects.filter(cart=cart).delete()
                # Recreate items from payload
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    pid = item.get('productId') or item.get('product_id')
                    if not pid and isinstance(item.get('product'), dict):
                        pid = item['product'].get('id')
                    try:
                        qty = int(item.get('quantity', 0))
                    except (ValueError, TypeError):
                        qty = 0
                    if not pid or qty <= 0:
                        continue
                    product = Product.objects.filter(id=pid).first()
                    if not product:
                        continue
                    CartProduct.objects.create(cart=cart, product=product, quantity=qty)

        # Refresh for DTO after transactional updates
        refreshed = self.carts.get(id=cart_id)
        return cart_to_dto(refreshed)

    def delete_cart(self, cart_id: int, user_id: Optional[int] = None) -> bool:
        """Hard-delete a cart in an explicit order: first its products, then the cart.
        If user_id is provided, the operation is scoped to the owner's cart.
        Returns True iff the cart row was deleted.
        """
        cart_qs = Cart.objects.filter(id=cart_id)
        if user_id is not None:
            cart_qs = cart_qs.filter(user_id=user_id)
        if not cart_qs.exists():
            return False
        with transaction.atomic():
            # 1) Delete cart products first
            CartProduct.objects.filter(cart_id=cart_id).delete()
            # 2) Delete the cart itself
            deleted_count, _ = cart_qs.delete()
        return deleted_count > 0

    def patch_operations(self, cart_id: int, ops: Dict[str, Any], user_id: Optional[int] = None):
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
        filters: Dict[str, Any] = {'id': cart_id}
        if user_id is not None:
            filters['user_id'] = user_id
        cart: Optional[Cart] = self.carts.get(**filters)
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
