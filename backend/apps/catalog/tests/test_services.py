from django.test import TestCase
from apps.catalog.services import ProductService, CategoryService
from apps.catalog.models import Category, Product, Rating

class ProductServiceIntegrationTests(TestCase):
    def setUp(self):
        self.product_service = ProductService()
        self.category_service = CategoryService()

    def test_create_and_get_product(self):
        cat = Category.objects.create(name="Books")
        dto = self.product_service.create_product({
            'title': 'Novel',
            'price': '12.50',
            'description': 'A book',
            'image': 'img',
            'rate': 0,
            'count': 0,
            'categories': [cat.id]
        })
        fetched = self.product_service.get_product(dto.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, 'Novel')
        self.assertEqual(len(fetched.categories), 1)

    def test_update_product(self):
        p = Product.objects.create(title='Item', price='1.00', description='d', image='i', rate='0', count=0)
        updated = self.product_service.update_product(p.id, {'title': 'Item2', 'price': '2.00', 'description': 'd2', 'image': 'i2'}, partial=False)
        self.assertEqual(updated.title, 'Item2')

    def test_rating_cycle(self):
        p = Product.objects.create(title='Rated', price='5.00', description='d', image='i', rate='0', count=0)
        summary = self.product_service.set_user_rating(p.id, user_id=10, value=4)
        self.assertEqual(summary['rating']['count'], 1)
        summary = self.product_service.set_user_rating(p.id, user_id=10, value=5)
        self.assertEqual(summary['rating']['rate'], 5.0)
        summary = self.product_service.delete_user_rating(p.id, user_id=10)
        self.assertEqual(summary['rating']['count'], 0)

class CategoryServiceIntegrationTests(TestCase):
    def setUp(self):
        self.category_service = CategoryService()

    def test_create_list_delete_category(self):
        dto = self.category_service.create_category({'name': 'Toys'})
        self.assertEqual(dto.name, 'Toys')
        categories = self.category_service.list_categories()
        self.assertTrue(any(c.name == 'Toys' for c in categories))
        deleted = self.category_service.delete_category(dto.id)
        self.assertTrue(deleted)
