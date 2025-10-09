from typing import Optional, Dict, Any, List
from django.db import transaction
from .repositories import CartRepository, CartProductRepository
from .mappers import CartMapper, CartProductMapper
from .models import Cart, CartProduct
from .commands import CartCreateCommand, CartPatchCommand, CartItemCommand, CartUpdateCommand
from apps.catalog.repositories import ProductRepository
from django.utils import timezone

class CartService:
    def __init__(
        self,
        carts: Optional[CartRepository] = None,
        cart_products: Optional[CartProductRepository] = None,
        products: Optional[ProductRepository] = None,
        cart_product_mapper: Optional[CartProductMapper] = None,
        cart_mapper: Optional[CartMapper] = None,
    ):
        self.carts = carts or CartRepository()
        self.cart_products = cart_products or CartProductRepository()
        self.products = products or ProductRepository()
        self.cart_product_mapper = cart_product_mapper or CartProductMapper()
        self.cart_mapper = cart_mapper or CartMapper(self.cart_product_mapper)

    def list_carts(self, user_id: Optional[int] = None):
        qs = self.carts.list(user_id=user_id) if user_id else self.carts.list()
        return self.cart_mapper.many_to_dto(qs)

    def get_cart(self, cart_id: int):
        c = self.carts.get(id=cart_id)
        return self.cart_mapper.to_dto(c) if c else None

    def create_cart(self, user_id: int, data: Dict[str, Any]):
        payload = dict(data)
        payload['userId'] = user_id
        cmd = payload if isinstance(payload, CartCreateCommand) else CartCreateCommand.from_raw(payload)
        create_kwargs: Dict[str, Any] = {
            'date': cmd.date,
        }
        if cmd.user_id is not None:
            create_kwargs['user_id'] = cmd.user_id
        with transaction.atomic():
            cart: Cart = self.carts.create(**create_kwargs)
            for item in cmd.items:
                product = self.products.get(id=item.product_id)
                if not product:
                    continue
                self.cart_products.create(cart=cart, product=product, quantity=item.quantity)
        return self.cart_mapper.to_dto(cart)

    def update_cart(self, cart_id: int, data: Dict[str, Any], user_id: Optional[int] = None):
        filters: Dict[str, Any] = {'id': cart_id}
        if user_id is not None:
            filters['user_id'] = user_id
        cart: Optional[Cart] = self.carts.get(**filters)
        if not cart:
            return None
        cmd = CartUpdateCommand.from_raw(cart_id, data)
        with transaction.atomic():
            # scalar updates
            self.carts.update_scalar(cart, user_id=cmd.user_id, date=cmd.date)
            if cmd.items is not None:
                self._rebuild_items(cart, [ {'productId': i.product_id, 'quantity': i.quantity } for i in cmd.items ])
        refreshed = self.carts.get(id=cart_id)
        return self.cart_mapper.to_dto(refreshed)

    def delete_cart(self, cart_id: int, user_id: Optional[int] = None) -> bool:
        """Hard-delete a cart in an explicit order: first its products, then the cart.
        If user_id is provided, the operation is scoped to the owner's cart.
        Returns True iff the cart row was deleted.
        """
        filters: Dict[str, Any] = {'id': cart_id}
        if user_id is not None:
            filters['user_id'] = user_id
        cart = self.carts.get(**filters)
        if not cart:
            return False
        with transaction.atomic():
            # delete line items then cart
            for cp in self.cart_products.list_for_cart(cart.id):
                self.cart_products.delete(cp)
            self.carts.delete(cart)
        return True

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
        cmd = CartPatchCommand.from_raw(cart_id, ops)

        with transaction.atomic():
            self._update_cart_metadata(cart, cmd.new_date, cmd.new_user_id)
            existing_map = {cp.product_id: cp for cp in self.cart_products.list_for_cart(cart.id)}
            self._apply_add_ops(cart, existing_map, cmd.add)
            self._apply_update_ops(cart, cmd.update)
            self._apply_remove_ops(cart, cmd.remove)
        cart_refreshed = self.carts.get(id=cart_id)
        return self.cart_mapper.to_dto(cart_refreshed)

    # Helper methods
    def _rebuild_items(self, cart: Cart, raw_items: List[Dict[str, Any]]):
        self.cart_products.delete_for_cart(cart)
        for raw in raw_items:
            cmd = CartItemCommand.from_raw(raw)
            if not cmd:
                continue
            product = self.products.get(id=cmd.product_id)
            if not product:
                continue
            self.cart_products.create(cart=cart, product=product, quantity=cmd.quantity)

    def _update_cart_metadata(self, cart: Cart, new_date, new_user_id):
        changed = False
        if new_date:
            cart.date = new_date
            changed = True
        if new_user_id:
            try:
                cart.user_id = int(new_user_id)
                changed = True
            except (ValueError, TypeError):
                pass
        if changed:
            cart.save()

    def _apply_add_ops(self, cart: Cart, existing_map: Dict[int, CartProduct], add_ops: List[CartItemCommand]):
        for item in add_ops:
            product = self.products.get(id=item.product_id)
            if not product:
                continue
            cp = existing_map.get(item.product_id)
            if cp:
                cp.quantity += item.quantity
                cp.save()
            else:
                cp = self.cart_products.create(cart=cart, product=product, quantity=item.quantity)
                existing_map[item.product_id] = cp

    def _apply_update_ops(self, cart: Cart, update_ops: List[CartItemCommand]):
        for item in update_ops:
            product = self.products.get(id=item.product_id)
            if not product:
                continue
            cp = self.cart_products.get_for_cart_product(cart.id, item.product_id)
            if not cp:
                self.cart_products.create(cart=cart, product=product, quantity=item.quantity)
            else:
                cp.quantity = item.quantity
                cp.save()

    def _apply_remove_ops(self, cart: Cart, remove_ops: List[int]):
        for pid in remove_ops:
            self.cart_products.delete_product(cart, pid)
