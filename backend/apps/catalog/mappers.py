from typing import Iterable, List
from .models import Product, Category
from .dtos import ProductDTO, CategoryDTO


class CategoryMapper:
    @staticmethod
    def to_dto(cat: Category) -> CategoryDTO:
        return CategoryDTO(id=cat.id, name=cat.name)

    @staticmethod
    def many_to_dto(categories: Iterable[Category]) -> List[CategoryDTO]:
        return [CategoryMapper.to_dto(c) for c in categories]


class ProductMapper:
    @staticmethod
    def to_dto(product: Product) -> ProductDTO:
        # categories prefetched by repository
        categories = product.categories.all()
        return ProductDTO(
            id=product.id,
            title=product.title,
            price=str(product.price),
            description=product.description,
            image=product.image,
            rate=str(product.rate),
            count=product.count,
            categories=CategoryMapper.many_to_dto(categories),
        )

    @staticmethod
    def many_to_dto(products: Iterable[Product]) -> List[ProductDTO]:
        return [ProductMapper.to_dto(p) for p in products]
