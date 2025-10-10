import unittest
from unittest.mock import patch

from apps.carts.services import CartService
from apps.carts.mappers import CartMapper, CartProductMapper
from apps.catalog.mappers import ProductMapper


class DummyAtomic:
    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class StubCategoryManager:
    def __init__(self, categories=None):
        self._categories = list(categories or [])

    def all(self):
        return list(self._categories)

    def set(self, categories):
        self._categories = list(categories)


class StubProduct:
    def __init__(self, product_id: int, title: str, price: str):
        self.id = product_id
        self.title = title
        self.price = price
        self.description = ''
        self.image = ''
        self.rate = '0'
        self.count = 0
        self.categories = StubCategoryManager()


class StubCartProduct:
    def __init__(self, cart, product: StubProduct, quantity: int):
        self.cart = cart
        self.cart_id = cart.id
        self.product = product
        self.product_id = product.id
        self.quantity = quantity

    def save(self):
        return self


class StubCartProductsManager:
    def __init__(self, cart):
        self._cart = cart

    def all(self):
        return list(self._cart._items)


class StubCart:
    def __init__(self, cart_id: int, user_id: int, cart_date=None):
        self.id = cart_id
        self.user_id = user_id
        self.date = cart_date
        self._items = []
        self.cart_products = StubCartProductsManager(self)

    def save(self):
        return self


class FakeCartRepository:
    def __init__(self):
        self._storage = {}
        self._pk = 1

    def create(self, **data):
        cart = StubCart(self._pk, data.get('user_id'), data.get('date'))
        self._storage[self._pk] = cart
        self._pk += 1
        return cart

    def get(self, **filters):
        cart_id = filters.get('id')
        user_id = filters.get('user_id')
        cart = self._storage.get(cart_id)
        if cart and user_id is not None and cart.user_id != user_id:
            return None
        return cart

    def list(self, **filters):
        user_id = filters.get('user_id')
        carts = list(self._storage.values())
        if user_id is not None:
            return [c for c in carts if c.user_id == user_id]
        return carts

    def update_scalar(self, cart: StubCart, **fields):
        for key, value in fields.items():
            if value is not None:
                setattr(cart, key, value)
        return cart

    def delete(self, cart: StubCart):
        self._storage.pop(cart.id, None)


class FakeCartProductRepository:
    def __init__(self, cart_repository: FakeCartRepository):
        self.cart_repository = cart_repository

    def create(self, **data):
        cart: StubCart = data['cart']
        product: StubProduct = data['product']
        quantity: int = data['quantity']
        item = StubCartProduct(cart, product, quantity)
        cart._items.append(item)
        return item

    def list_for_cart(self, cart_id: int):
        cart = self.cart_repository.get(id=cart_id)
        return list(cart._items) if cart else []

    def delete(self, item: StubCartProduct):
        cart = self.cart_repository.get(id=item.cart_id)
        if cart and item in cart._items:
            cart._items.remove(item)

    def delete_for_cart(self, cart: StubCart):
        cart._items.clear()

    def get_for_cart_product(self, cart_id: int, product_id: int):
        cart = self.cart_repository.get(id=cart_id)
        if not cart:
            return None
        for item in cart._items:
            if item.product_id == product_id:
                return item
        return None

    def delete_product(self, cart: StubCart, product_id: int):
        cart._items = [item for item in cart._items if item.product_id != product_id]


class FakeProductRepository:
    def __init__(self, products):
        self._products = {p.id: p for p in products}

    def get(self, **filters):
        product_id = filters.get('id')
        return self._products.get(product_id)


class CartServiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.products_repo = FakeProductRepository([
            StubProduct(1, 'Widget', '1.00'),
            StubProduct(2, 'Gadget', '2.00'),
        ])
        self.cart_repo = FakeCartRepository()
        self.cart_products_repo = FakeCartProductRepository(self.cart_repo)
        self.cart_mapper = CartMapper(CartProductMapper(ProductMapper()))
        self.atomic_patcher = patch('apps.carts.services.transaction.atomic', DummyAtomic())
        self.atomic_patcher.start()
        self.service = CartService(
            carts=self.cart_repo,
            cart_products=self.cart_products_repo,
            products=self.products_repo,
            cart_mapper=self.cart_mapper,
        )

    def tearDown(self):
        self.atomic_patcher.stop()

    def test_create_and_get_cart(self):
        dto = self.service.create_cart(5, {'products': [
            {'productId': 1, 'quantity': 2},
            {'productId': 2, 'quantity': 1},
        ]})
        fetched = self.service.get_cart(dto.id)
        self.assertEqual(len(fetched.items), 2)

    def test_update_cart_replace_items(self):
        dto = self.service.create_cart(6, {'products': [
            {'productId': 1, 'quantity': 1},
        ]})
        updated = self.service.update_cart(dto.id, {
            'items': [{'productId': 2, 'quantity': 3}]
        })
        self.assertEqual(len(updated.items), 1)
        self.assertEqual(updated.items[0].product.id, 2)
        self.assertEqual(updated.items[0].quantity, 3)

    def test_patch_operations(self):
        dto = self.service.create_cart(7, {'products': [
            {'productId': 1, 'quantity': 1},
        ]})
        patched = self.service.patch_operations(dto.id, {
            'add': [{'productId': 2, 'quantity': 2}],
            'update': [{'productId': 1, 'quantity': 5}],
            'remove': [999],
        })
        quantities = {item.product.id: item.quantity for item in patched.items}
        self.assertEqual(quantities[1], 5)
        self.assertEqual(quantities[2], 2)

    def test_delete_cart(self):
        dto = self.service.create_cart(8, {'products': [
            {'productId': 1, 'quantity': 1},
        ]})
        result = self.service.delete_cart(dto.id)
        self.assertTrue(result)
        self.assertIsNone(self.service.get_cart(dto.id))


if __name__ == '__main__':
    unittest.main()
