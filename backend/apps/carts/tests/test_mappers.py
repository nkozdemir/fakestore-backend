from django.test import TestCase
from apps.catalog.models import Product, Category
from apps.carts.models import Cart, CartProduct
from apps.users.models import User
from apps.carts.mappers import CartMapper, CartProductMapper

class CartMapperTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Misc")
        self.product = Product.objects.create(title="Widget", price="5.00", description="d", image="i", rate="4.0", count=2)
        self.product.categories.add(self.category)
        self.user = User.objects.create_user(username="u_mapper", password="x", email="u_mapper@example.com", firstname="First", lastname="Last")
        self.cart = Cart.objects.create(user=self.user, date="2025-09-29")
        CartProduct.objects.create(cart=self.cart, product=self.product, quantity=3)

    def test_cart_product_mapper(self):
        cp = self.cart.cart_products.first()
        dto = CartProductMapper.to_dto(cp)
        self.assertEqual(dto.product.id, self.product.id)
        self.assertEqual(dto.quantity, 3)

    def test_cart_mapper(self):
        dto = CartMapper.to_dto(self.cart)
        self.assertEqual(dto.id, self.cart.id)
        self.assertEqual(dto.user_id, self.cart.user_id)
        self.assertEqual(len(dto.items), 1)
        self.assertEqual(dto.items[0].quantity, 3)

    def test_many_mapper(self):
        dtos = CartMapper.many_to_dto([self.cart])
        self.assertEqual(len(dtos), 1)
        self.assertEqual(dtos[0].id, self.cart.id)
