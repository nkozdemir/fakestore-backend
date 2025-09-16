from dataclasses import dataclass
from typing import List
from .models import Product, Category

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

def category_to_dto(cat: Category) -> CategoryDTO:
    return CategoryDTO(id=cat.id, name=cat.name)

def product_to_dto(p: Product) -> ProductDTO:
    cats = [category_to_dto(c) for c in p.categories.all()]
    return ProductDTO(id=p.id, title=p.title, price=str(p.price), description=p.description, image=p.image, rate=str(p.rate), count=p.count, categories=cats)
