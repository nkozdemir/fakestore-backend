from django.test import TestCase
from apps.carts.services import CartService
from apps.carts.models import Cart, CartProduct
from apps.catalog.models import Product, Category
from apps.users.models import User

class CartServiceIntegrationTests(TestCase):
    def setUp(self):
        self.service = CartService()
        self.category = Category.objects.create(name='General')
        self.product1 = Product.objects.create(title='P1', price='1.00', description='d', image='i', rate='0', count=0)
        self.product2 = Product.objects.create(title='P2', price='2.00', description='d2', image='i2', rate='0', count=0)
        self.product1.categories.add(self.category)
        self.product2.categories.add(self.category)

    def test_create_and_get_cart(self):
        user = User.objects.create_user(username='svc1', password='x', email='svc1@example.com', firstname='F', lastname='L')
        dto = self.service.create_cart({'userId': user.id, 'products': [
            {'productId': self.product1.id, 'quantity': 2},
            {'productId': self.product2.id, 'quantity': 1},
        ]})
        fetched = self.service.get_cart(dto.id)
        self.assertEqual(len(fetched.items), 2)

    def test_update_cart_replace_items(self):
        user = User.objects.create_user(username='svc2', password='x', email='svc2@example.com', firstname='F', lastname='L')
        cart_dto = self.service.create_cart({'userId': user.id, 'products': [
            {'productId': self.product1.id, 'quantity': 1},
        ]})
        updated = self.service.update_cart(cart_dto.id, {
            'items': [
                {'productId': self.product2.id, 'quantity': 3}
            ]
        })
        self.assertEqual(len(updated.items), 1)
        self.assertEqual(updated.items[0].product.id, self.product2.id)

    def test_patch_operations(self):
        user = User.objects.create_user(username='svc3', password='x', email='svc3@example.com', firstname='F', lastname='L')
        cart_dto = self.service.create_cart({'userId': user.id, 'products': [
            {'productId': self.product1.id, 'quantity': 1},
        ]})
        patched = self.service.patch_operations(cart_dto.id, {
            'add': [{'productId': self.product2.id, 'quantity': 2}],
            'update': [{'productId': self.product1.id, 'quantity': 5}],
            'remove': [999]  # removing non-existent product id should be harmless
        })
        # After add & update, we expect P1 quantity=5, P2 quantity=2
        qmap = {i.product.id: i.quantity for i in patched.items}
        self.assertEqual(qmap[self.product1.id], 5)
        self.assertEqual(qmap[self.product2.id], 2)

    def test_delete_cart(self):
        user = User.objects.create_user(username='svc4', password='x', email='svc4@example.com', firstname='F', lastname='L')
        cart_dto = self.service.create_cart({'userId': user.id, 'products': [
            {'productId': self.product1.id, 'quantity': 1},
        ]})
        ok = self.service.delete_cart(cart_dto.id)
        self.assertTrue(ok)
        self.assertIsNone(self.service.get_cart(cart_dto.id))
