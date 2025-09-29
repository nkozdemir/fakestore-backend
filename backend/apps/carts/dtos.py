from dataclasses import dataclass
from typing import List
from apps.catalog.dtos import ProductDTO

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
"""DTO dataclasses only. Mapping logic moved to mappers.py."""
