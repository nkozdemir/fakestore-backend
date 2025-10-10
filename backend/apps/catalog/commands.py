from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any


# Product Commands
@dataclass
class ProductCreateCommand:
    title: str
    price: str
    description: str
    image: str
    categories: List[int] = field(default_factory=list)
    rate: Optional[float] = None
    count: Optional[int] = None

    @staticmethod
    def _parse_categories(raw):
        if not raw:
            return []
        out = []
        for c in raw:
            try:
                out.append(int(c))
            except (ValueError, TypeError):
                continue
        return out

    @staticmethod
    def from_raw(payload: Dict[str, Any]):
        data = dict(payload or {})
        # ignore id if present
        data.pop("id", None)
        return ProductCreateCommand(
            title=str(data.get("title", "")).strip(),
            price=str(data.get("price", "0")).strip(),
            description=str(data.get("description", "")).strip(),
            image=str(data.get("image", "")).strip(),
            categories=ProductCreateCommand._parse_categories(
                data.get("categories") or []
            ),
            rate=data.get("rate"),
            count=data.get("count"),
        )


@dataclass
class ProductUpdateCommand:
    product_id: int
    partial: bool
    title: Optional[str] = None
    price: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    categories: Optional[List[int]] = None
    rate: Optional[float] = None
    count: Optional[int] = None

    @staticmethod
    def from_raw(product_id: int, payload: Dict[str, Any], partial: bool):
        data = dict(payload or {})
        data.pop("id", None)
        cats = None
        if "categories" in data:
            cats = ProductCreateCommand._parse_categories(data.get("categories") or [])
        return ProductUpdateCommand(
            product_id=product_id,
            partial=partial,
            title=data.get("title"),
            price=str(data.get("price")) if "price" in data else None,
            description=data.get("description"),
            image=data.get("image"),
            categories=cats,
            rate=data.get("rate") if "rate" in data else None,
            count=data.get("count") if "count" in data else None,
        )


# Rating Command
@dataclass
class RatingSetCommand:
    product_id: int
    user_id: int
    value: int

    @staticmethod
    def from_raw(product_id: int, user_id: int, value: Any):
        try:
            v = int(value)
        except (ValueError, TypeError):
            v = -1
        return RatingSetCommand(product_id=product_id, user_id=user_id, value=v)
