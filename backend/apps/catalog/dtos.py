from dataclasses import dataclass
from typing import List


@dataclass
class CategoryDTO:
    id: int
    name: str


@dataclass
class ProductDTO:
    id: int
    title: str
    price: str
    description: str
    image: str
    rate: str
    count: int
    categories: List[CategoryDTO]


"""DTO dataclasses only. Mapping logic lives in mappers.py now."""
