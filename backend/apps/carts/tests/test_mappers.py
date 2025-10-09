import unittest
from decimal import Decimal
from datetime import date
from apps.carts.mappers import CartMapper, CartProductMapper


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
    def __init__(self, product_id: int, title: str, price):
        self.id = product_id
        self.title = title
        self.price = price
        self.description = 'd'
        self.image = 'img'
        self.rate = '4.0'
        self.count = 2
        self.categories = StubCategoryManager()


class StubCartProduct:
    def __init__(self, product: StubProduct, quantity: int):
        self.product = product
        self.quantity = quantity


class StubCartProductsManager:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)


class StubCart:
    def __init__(self, cart_id: int, user_id: int, cart_date, items):
        self.id = cart_id
        self.user_id = user_id
        self.date = cart_date
        self.cart_products = StubCartProductsManager(items)


class CartMapperTests(unittest.TestCase):
    def setUp(self):
        self.product = StubProduct(1, "Widget", Decimal("5.00"))
        self.product.categories = StubCategoryManager([StubCategory(1, "Misc")])
        self.cart_product = StubCartProduct(self.product, 3)
        self.cart = StubCart(2, 10, date(2025, 9, 29), [self.cart_product])
        self.cart_product_mapper = CartProductMapper()
        self.cart_mapper = CartMapper(self.cart_product_mapper)

    def test_cart_product_mapper(self):
        dto = self.cart_product_mapper.to_dto(self.cart_product)
        self.assertEqual(dto.product.id, 1)
        self.assertEqual(dto.quantity, 3)

    def test_cart_mapper(self):
        dto = self.cart_mapper.to_dto(self.cart)
        self.assertEqual(dto.id, 2)
        self.assertEqual(dto.user_id, 10)
        self.assertEqual(dto.date, "2025-09-29")
        self.assertEqual(len(dto.items), 1)
        self.assertEqual(dto.items[0].quantity, 3)

    def test_many_mapper(self):
        dtos = self.cart_mapper.many_to_dto([self.cart])
        self.assertEqual(len(dtos), 1)
        self.assertEqual(dtos[0].id, 2)
