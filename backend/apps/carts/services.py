from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import transaction

from apps.common import get_logger
from .commands import (
    CartCreateCommand,
    CartItemCommand,
    CartPatchCommand,
    CartUpdateCommand,
)
from .models import Cart, CartProduct
from .protocols import (
    CartMapperProtocol,
    CartProductRepositoryProtocol,
    CartRepositoryProtocol,
    ProductRepositoryProtocol,
)

logger = get_logger(__name__).bind(component="carts", layer="service")


class CartService:
    def __init__(
        self,
        carts: CartRepositoryProtocol,
        cart_products: CartProductRepositoryProtocol,
        products: ProductRepositoryProtocol,
        cart_mapper: CartMapperProtocol,
    ):
        self.carts = carts
        self.cart_products = cart_products
        self.products = products
        self.cart_mapper = cart_mapper
        self.logger = logger.bind(service="CartService")

    def list_carts(self, user_id: Optional[int] = None):
        self.logger.debug("Listing carts", user_id=user_id)
        qs = self.carts.list(user_id=user_id) if user_id else self.carts.list()
        return self.cart_mapper.many_to_dto(qs)

    def get_cart(self, cart_id: int):
        self.logger.debug("Fetching cart", cart_id=cart_id)
        cart = self.carts.get(id=cart_id)
        if not cart:
            self.logger.info("Cart not found", cart_id=cart_id)
        return self.cart_mapper.to_dto(cart) if cart else None

    def create_cart(self, user_id: int, data: Dict[str, Any]):
        self.logger.info("Creating cart", user_id=user_id)
        payload = dict(data)
        payload["userId"] = user_id
        command = (
            payload
            if isinstance(payload, CartCreateCommand)
            else CartCreateCommand.from_raw(payload)
        )
        create_kwargs: Dict[str, Any] = {
            "date": command.date,
        }
        if command.user_id is not None:
            create_kwargs["user_id"] = command.user_id
        with transaction.atomic():
            cart: Cart = self.carts.create(**create_kwargs)
            for item in command.items:
                product = self.products.get(id=item.product_id)
                if not product:
                    self.logger.warning(
                        "Skipping missing product during cart creation",
                        product_id=item.product_id,
                    )
                    continue
                self.cart_products.create(
                    cart=cart, product=product, quantity=item.quantity
                )
        self.logger.info("Cart created", cart_id=cart.id, user_id=user_id)
        return self.cart_mapper.to_dto(cart)

    def update_cart(
        self, cart_id: int, data: Dict[str, Any], user_id: Optional[int] = None
    ):
        self.logger.info("Updating cart", cart_id=cart_id, user_id=user_id)
        filters: Dict[str, Any] = {"id": cart_id}
        if user_id is not None:
            filters["user_id"] = user_id
        cart: Optional[Cart] = self.carts.get(**filters)
        if not cart:
            self.logger.warning(
                "Cart update failed: not found", cart_id=cart_id, user_id=user_id
            )
            return None
        command = CartUpdateCommand.from_raw(cart_id, data)
        update_kwargs: Dict[str, Any] = {
            "user_id": command.user_id,
            "date": command.date,
        }
        original_fields = {
            field: getattr(cart, field)
            for field, value in update_kwargs.items()
            if value is not None
        }
        original_items_snapshot = None
        if command.items is not None:
            if hasattr(cart, "_items"):
                original_items_snapshot = list(cart._items)
            else:
                try:
                    original_items_snapshot = list(
                        self.cart_products.list_for_cart(cart.id)
                    )
                except Exception:
                    original_items_snapshot = None
        try:
            with transaction.atomic():
                self.carts.update_scalar(cart, **update_kwargs)
                if command.items is not None:
                    self._rebuild_items(cart, command.items)
        except Exception:
            for field, value in original_fields.items():
                setattr(cart, field, value)
            if command.items is not None:
                if hasattr(cart, "_items"):
                    cart._items = list(original_items_snapshot or [])
                elif hasattr(cart, "refresh_from_db"):
                    try:
                        cart.refresh_from_db()
                    except Exception:
                        pass
            raise
        refreshed = self.carts.get(id=cart_id)
        self.logger.info("Cart updated", cart_id=cart_id, user_id=user_id)
        return self.cart_mapper.to_dto(refreshed) if refreshed else None

    def delete_cart(self, cart_id: int, user_id: Optional[int] = None) -> bool:
        """Remove a cart and its line items. Respects user scoping when provided."""
        self.logger.info("Deleting cart", cart_id=cart_id, user_id=user_id)
        filters: Dict[str, Any] = {"id": cart_id}
        if user_id is not None:
            filters["user_id"] = user_id
        cart = self.carts.get(**filters)
        if not cart:
            self.logger.warning(
                "Cart deletion failed: not found", cart_id=cart_id, user_id=user_id
            )
            return False
        with transaction.atomic():
            for cart_product in self.cart_products.list_for_cart(cart.id):
                self.cart_products.delete(cart_product)
            self.carts.delete(cart)
        self.logger.info("Cart deleted", cart_id=cart_id, user_id=user_id)
        return True

    def patch_operations(
        self, cart_id: int, ops: Dict[str, Any], user_id: Optional[int] = None
    ):
        """Apply add/update/remove operations to cart contents in a single transaction."""
        self.logger.info("Patching cart operations", cart_id=cart_id, user_id=user_id)
        filters: Dict[str, Any] = {"id": cart_id}
        if user_id is not None:
            filters["user_id"] = user_id
        cart: Optional[Cart] = self.carts.get(**filters)
        if not cart:
            self.logger.warning(
                "Cart patch failed: not found", cart_id=cart_id, user_id=user_id
            )
            return None
        command = CartPatchCommand.from_raw(cart_id, ops)
        with transaction.atomic():
            self._update_cart_metadata(cart, command.new_date, command.new_user_id)
            existing_map = {
                cp.product_id: cp for cp in self.cart_products.list_for_cart(cart.id)
            }
            self._apply_add_ops(cart, existing_map, command.add)
            self._apply_update_ops(cart, command.update)
            self._apply_remove_ops(cart, command.remove)
        refreshed = self.carts.get(id=cart_id)
        self.logger.info("Cart patch applied", cart_id=cart_id, user_id=user_id)
        return self.cart_mapper.to_dto(refreshed) if refreshed else None

    def _rebuild_items(self, cart: Cart, items: List[CartItemCommand]):
        self.cart_products.delete_for_cart(cart)
        for item in items:
            product = self.products.get(id=item.product_id)
            if not product:
                self.logger.warning(
                    "Skipping missing product during cart rebuild",
                    cart_id=cart.id,
                    product_id=item.product_id,
                )
                continue
            self.cart_products.create(
                cart=cart, product=product, quantity=item.quantity
            )

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

    def _apply_add_ops(
        self,
        cart: Cart,
        existing_map: Dict[int, CartProduct],
        add_ops: List[CartItemCommand],
    ):
        for item in add_ops:
            product = self.products.get(id=item.product_id)
            if not product:
                self.logger.warning(
                    "Skipping missing product in add op",
                    cart_id=cart.id,
                    product_id=item.product_id,
                )
                continue
            current = existing_map.get(item.product_id)
            if current:
                current.quantity += item.quantity
                current.save()
            else:
                created = self.cart_products.create(
                    cart=cart, product=product, quantity=item.quantity
                )
                existing_map[item.product_id] = created

    def _apply_update_ops(self, cart: Cart, update_ops: List[CartItemCommand]):
        for item in update_ops:
            product = self.products.get(id=item.product_id)
            if not product:
                self.logger.warning(
                    "Skipping missing product in update op",
                    cart_id=cart.id,
                    product_id=item.product_id,
                )
                continue
            current = self.cart_products.get_for_cart_product(cart.id, item.product_id)
            if not current:
                self.cart_products.create(
                    cart=cart, product=product, quantity=item.quantity
                )
            else:
                current.quantity = item.quantity
                current.save()

    def _apply_remove_ops(self, cart: Cart, remove_ops: List[int]):
        for product_id in remove_ops:
            self.cart_products.delete_product(cart, product_id)
