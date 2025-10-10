import unittest
from decimal import Decimal
from apps.catalog.mappers import CategoryMapper, ProductMapper


class StubCategory:
    def __init__(self, category_id: int, name: str):
        self.id = category_id
        self.name = name


class StubCategoryManager:
    def __init__(self, categories=None):
        self._categories = list(categories or [])

    def all(self):
        return list(self._categories)


class StubProduct:
    def __init__(
        self,
        product_id: int,
        title: str,
        price,
        description: str = "",
        image: str = "",
        rate: str = "0",
        count: int = 0,
        categories=None,
    ):
        self.id = product_id
        self.title = title
        self.price = price
        self.description = description
        self.image = image
        self.rate = rate
        self.count = count
        self.categories = StubCategoryManager(categories)


class CategoryMapperTests(unittest.TestCase):
    def test_category_mapper_basic(self):
        category = StubCategory(1, "Electronics")
        dto = CategoryMapper.to_dto(category)
        self.assertEqual(dto.id, 1)
        self.assertEqual(dto.name, "Electronics")

    def test_category_many(self):
        categories = [StubCategory(1, "A"), StubCategory(2, "B")]
        dtos = CategoryMapper.many_to_dto(categories)
        self.assertEqual(len(dtos), 2)
        self.assertSetEqual({d.name for d in dtos}, {"A", "B"})


class ProductMapperTests(unittest.TestCase):
    def test_product_mapper_with_categories(self):
        c1 = StubCategory(1, "Cat1")
        c2 = StubCategory(2, "Cat2")
        product = StubProduct(
            product_id=3,
            title="Phone",
            price=Decimal("10.00"),
            description="desc",
            image="img",
            rate=Decimal("4.5"),
            count=7,
            categories=[c1, c2],
        )
        dto = ProductMapper.to_dto(product)
        self.assertEqual(dto.id, 3)
        self.assertEqual(dto.title, "Phone")
        self.assertEqual(dto.price, "10.00")
        self.assertEqual(dto.count, 7)
        self.assertEqual(len(dto.categories), 2)
        self.assertSetEqual({c.name for c in dto.categories}, {"Cat1", "Cat2"})

    def test_product_mapper_no_categories(self):
        product = StubProduct(
            product_id=4,
            title="Solo",
            price="3.99",
            description="d",
            image="i",
            rate="3.0",
            count=1,
        )
        dto = ProductMapper.to_dto(product)
        self.assertEqual(dto.id, 4)
        self.assertEqual(dto.categories, [])
