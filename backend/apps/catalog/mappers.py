from typing import Iterable, List, Optional

from apps.common.i18n import get_default_language, normalize_language_code

from .dtos import ProductDTO, CategoryDTO
from .models import Product, Category


def _select_translation(translations, language: Optional[str]):
    if not translations:
        return None
    normalized_target = normalize_language_code(language)
    default_language = get_default_language()
    fallback = None
    for translation in translations:
        lang = normalize_language_code(getattr(translation, "language", None))
        if lang == normalized_target:
            return translation
        if fallback is None and lang == default_language:
            fallback = translation
    return fallback


class CategoryMapper:
    @staticmethod
    def to_dto(cat: Category, *, language: Optional[str] = None) -> CategoryDTO:
        name = cat.name
        translations = getattr(cat, "translations", None)
        if translations is not None:
            translation = _select_translation(
                getattr(translations, "all", lambda: translations)(), language
            )
            if translation is not None:
                name = getattr(translation, "name", name)
        return CategoryDTO(id=cat.id, name=name)

    @staticmethod
    def many_to_dto(
        categories: Iterable[Category], *, language: Optional[str] = None
    ) -> List[CategoryDTO]:
        return [CategoryMapper.to_dto(c, language=language) for c in categories]


class ProductMapper:
    @staticmethod
    def to_dto(product: Product, *, language: Optional[str] = None) -> ProductDTO:
        categories = product.categories.all()
        title = product.title
        description = product.description
        translations = getattr(product, "translations", None)
        if translations is not None:
            translation = _select_translation(
                getattr(translations, "all", lambda: translations)(), language
            )
            if translation is not None:
                title = getattr(translation, "title", title)
                description = getattr(translation, "description", description)
        return ProductDTO(
            id=product.id,
            title=title,
            price=str(product.price),
            description=description,
            image=product.image,
            rate=str(product.rate),
            count=product.count,
            categories=CategoryMapper.many_to_dto(categories, language=language),
        )

    @staticmethod
    def many_to_dto(
        products: Iterable[Product], *, language: Optional[str] = None
    ) -> List[ProductDTO]:
        return [ProductMapper.to_dto(p, language=language) for p in products]
