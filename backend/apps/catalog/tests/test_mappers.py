from django.test import TestCase
from apps.catalog.models import Category, Product
from apps.catalog.mappers import CategoryMapper, ProductMapper

class CategoryMapperTests(TestCase):
    def test_category_mapper_basic(self):
        c = Category.objects.create(name="Electronics")
        dto = CategoryMapper.to_dto(c)
        self.assertEqual(dto.id, c.id)
        self.assertEqual(dto.name, c.name)

    def test_category_many(self):
        Category.objects.create(name="A")
        Category.objects.create(name="B")
        dtos = CategoryMapper.many_to_dto(Category.objects.all())
        self.assertEqual(len(dtos), 2)
        self.assertSetEqual({d.name for d in dtos}, {"A", "B"})

class ProductMapperTests(TestCase):
    def test_product_mapper_with_categories(self):
        c1 = Category.objects.create(name="Cat1")
        c2 = Category.objects.create(name="Cat2")
        p = Product.objects.create(title="Phone", price="10.00", description="desc", image="img", rate="4.5", count=7)
        p.categories.add(c1, c2)
        dto = ProductMapper.to_dto(p)
        self.assertEqual(dto.id, p.id)
        self.assertEqual(dto.title, p.title)
        self.assertEqual(dto.price, str(p.price))
        self.assertEqual(len(dto.categories), 2)
        self.assertSetEqual({c.name for c in dto.categories}, {"Cat1", "Cat2"})

    def test_product_mapper_no_categories(self):
        p = Product.objects.create(title="Solo", price="3.99", description="d", image="i", rate="3.0", count=1)
        dto = ProductMapper.to_dto(p)
        self.assertEqual(dto.id, p.id)
        self.assertEqual(dto.categories, [])
