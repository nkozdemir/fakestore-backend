from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any


@dataclass
class CartItemCommand:
    product_id: int
    quantity: int

    @staticmethod
    def from_raw(raw: Dict[str, Any]):
        if not isinstance(raw, dict):
            return None
        pid = raw.get("productId") or raw.get("product_id")
        if pid is None:
            # nested product object fallback
            product = raw.get("product")
            if isinstance(product, dict):
                pid = product.get("id")
        try:
            pid = int(pid) if pid is not None else None
        except (ValueError, TypeError):
            pid = None
        try:
            qty = int(raw.get("quantity", 0))
        except (ValueError, TypeError):
            qty = 0
        if not pid or qty <= 0:
            return None
        return CartItemCommand(product_id=pid, quantity=qty)


@dataclass
class CartCreateCommand:
    user_id: Optional[int]
    date: date
    items: List[CartItemCommand] = field(default_factory=list)

    @staticmethod
    def _normalize_date(raw_date):
        if isinstance(raw_date, date):
            return raw_date
        if isinstance(raw_date, str):
            # accept ISO date or datetime; split at 'T'
            parts = raw_date.split("T")
            try:
                return datetime.strptime(parts[0], "%Y-%m-%d").date()
            except ValueError:
                pass
        return date.today()

    @staticmethod
    def from_raw(payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dict")
        user_id = payload.get("userId") or payload.get("user_id")
        try:
            user_id = int(user_id) if user_id is not None else None
        except (ValueError, TypeError):
            user_id = None
        raw_items = payload.get("products") or payload.get("items") or []
        items: List[CartItemCommand] = []
        for r in raw_items:
            cmd = CartItemCommand.from_raw(r)
            if cmd:
                items.append(cmd)
        d = CartCreateCommand._normalize_date(payload.get("date"))
        return CartCreateCommand(user_id=user_id, date=d, items=items)


@dataclass
class CartPatchCommand:
    cart_id: int
    add: List[CartItemCommand] = field(default_factory=list)
    update: List[CartItemCommand] = field(default_factory=list)
    remove: List[int] = field(default_factory=list)
    new_date: Optional[date] = None
    new_user_id: Optional[int] = None

    @staticmethod
    def from_raw(cart_id: int, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dict")

        def build_list(key):
            out: List[CartItemCommand] = []
            for r in payload.get(key, []) or []:
                cmd = CartItemCommand.from_raw(r)
                if cmd:
                    out.append(cmd)
            return out

        add = build_list("add")
        update = build_list("update")
        remove_raw = payload.get("remove") or []
        remove: List[int] = []
        for r in remove_raw:
            try:
                rid = int(r)
                remove.append(rid)
            except (ValueError, TypeError):
                continue
        new_date = payload.get("date")
        if new_date:
            new_date = CartCreateCommand._normalize_date(new_date)
        new_user_id = payload.get("userId") or payload.get("user_id")
        try:
            new_user_id = int(new_user_id) if new_user_id is not None else None
        except (ValueError, TypeError):
            new_user_id = None
        return CartPatchCommand(
            cart_id=cart_id,
            add=add,
            update=update,
            remove=remove,
            new_date=new_date,
            new_user_id=new_user_id,
        )


@dataclass
class CartUpdateCommand:
    cart_id: int
    user_id: Optional[int]
    date: Optional[date]
    items: List[CartItemCommand]

    @staticmethod
    def from_raw(cart_id: int, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dict")
        user_id = payload.get("userId") or payload.get("user_id")
        try:
            user_id = int(user_id) if user_id is not None else None
        except (ValueError, TypeError):
            user_id = None
        items_raw = payload.get("items") or []
        items: List[CartItemCommand] = []
        for r in items_raw:
            cmd = CartItemCommand.from_raw(r)
            if cmd:
                items.append(cmd)
        raw_date = payload.get("date")
        d = CartCreateCommand._normalize_date(raw_date) if raw_date else None
        return CartUpdateCommand(cart_id=cart_id, user_id=user_id, date=d, items=items)
