import unittest
from unittest.mock import patch

from apps.carts.services import (
    CartService,
    CartAlreadyExistsError,
    CartNotAllowedError,
)
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
        self.description = ""
        self.image = ""
        self.rate = "0"
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
        user_id = data.get("user_id")
        if user_id is None:
            raise ValueError("user_id is required")
        if any(c.user_id == user_id for c in self._storage.values()):
            raise ValueError("Cart already exists for user")
        cart = StubCart(self._pk, user_id, data.get("date"))
        self._storage[self._pk] = cart
        self._pk += 1
        return cart

    def get(self, **filters):
        cart_id = filters.get("id")
        user_id = filters.get("user_id")
        if cart_id is not None:
            cart = self._storage.get(cart_id)
            if cart and user_id is not None and cart.user_id != user_id:
                return None
            return cart
        if user_id is not None:
            for cart in self._storage.values():
                if cart.user_id == user_id:
                    return cart
        return None

    def list(self, **filters):
        user_id = filters.get("user_id")
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
        cart: StubCart = data["cart"]
        product: StubProduct = data["product"]
        quantity: int = data["quantity"]
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
        product_id = filters.get("id")
        return self._products.get(product_id)


class CartServiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.products_repo = FakeProductRepository(
            [
                StubProduct(1, "Widget", "1.00"),
                StubProduct(2, "Gadget", "2.00"),
            ]
        )
        self.cart_repo = FakeCartRepository()
        self.cart_products_repo = FakeCartProductRepository(self.cart_repo)
        self.cart_mapper = CartMapper(CartProductMapper(ProductMapper()))
        self.atomic_patcher = patch(
            "apps.carts.services.transaction.atomic", DummyAtomic()
        )
        self.atomic_patcher.start()
        self.user_flags = {}

        self.user_model_patcher = patch("apps.carts.services.User")
        self.mock_user_model = self.user_model_patcher.start()

        def filter_side_effect(**filters):
            user_id = filters.get("id")

            class ValuesWrapper:
                def __init__(self, info):
                    self._info = info

                def values(self, *args):
                    info = self._info

                    class FirstWrapper:
                        def __init__(self, info):
                            self._info = info

                        def first(self_inner):
                            return info

                    return FirstWrapper(info)

            if user_id is None:
                return ValuesWrapper(None)
            info = self.user_flags.get(
                user_id, {"id": user_id, "is_staff": False, "is_superuser": False}
            )
            return ValuesWrapper(info)

        self.mock_user_model.objects.filter.side_effect = filter_side_effect

        self.service = CartService(
            carts=self.cart_repo,
            cart_products=self.cart_products_repo,
            products=self.products_repo,
            cart_mapper=self.cart_mapper,
        )

    def tearDown(self):
        self.atomic_patcher.stop()
        self.user_model_patcher.stop()

    def test_create_and_get_cart(self):
        dto = self.service.create_cart(
            5,
            {
                "products": [
                    {"product_id": 1, "quantity": 2},
                    {"product_id": 2, "quantity": 1},
                ]
            },
        )
        fetched = self.service.get_cart(dto.id)
        self.assertEqual(len(fetched.items), 2)

    def test_create_cart_raises_when_cart_exists(self):
        self.service.create_cart(4, {"products": []})
        with self.assertRaises(CartAlreadyExistsError):
            self.service.create_cart(4, {"products": []})

    def test_create_cart_rejects_staff_user(self):
        self.user_flags[20] = {"id": 20, "is_staff": True, "is_superuser": False}
        with self.assertRaises(CartNotAllowedError):
            self.service.create_cart(20, {"products": []})

    def test_update_cart_replace_items(self):
        dto = self.service.create_cart(
            6,
            {
                "products": [
                    {"product_id": 1, "quantity": 1},
                ]
            },
        )
        updated = self.service.update_cart(
            dto.id, {"items": [{"product_id": 2, "quantity": 3}]}
        )
        self.assertEqual(len(updated.items), 1)
        self.assertEqual(updated.items[0].product.id, 2)
        self.assertEqual(updated.items[0].quantity, 3)

    def test_update_cart_metadata_only_preserves_items(self):
        dto = self.service.create_cart(
            12,
            {
                "products": [
                    {"product_id": 1, "quantity": 2},
                ],
                "date": "2024-01-01",
            },
        )
        updated = self.service.update_cart(dto.id, {"date": "2024-02-01"})
        self.assertEqual(len(updated.items), 1)
        self.assertEqual(updated.items[0].product.id, 1)
        self.assertEqual(updated.items[0].quantity, 2)

    def test_update_cart_reassign_to_staff_rejected(self):
        dto = self.service.create_cart(13, {"products": []})
        self.user_flags[14] = {"id": 14, "is_staff": True, "is_superuser": False}
        with self.assertRaises(CartNotAllowedError):
            self.service.update_cart(dto.id, {"user_id": 14})

    def test_update_cart_reverts_on_error(self):
        dto = self.service.create_cart(
            10,
            {
                "products": [
                    {"product_id": 1, "quantity": 2},
                ],
                "date": "2024-01-01",
            },
        )
        cart = self.cart_repo.get(id=dto.id)
        original_date = cart.date
        original_items = list(cart._items)
        original_create = self.cart_products_repo.create

        def boom(**kwargs):
            raise ValueError("boom")

        self.cart_products_repo.create = boom
        try:
            with self.assertRaises(ValueError):
                self.service.update_cart(
                    dto.id,
                    {
                        "date": "2024-03-01",
                        "items": [{"product_id": 2, "quantity": 5}],
                    },
                )
        finally:
            self.cart_products_repo.create = original_create
        cart_after = self.cart_repo.get(id=dto.id)
        self.assertEqual(cart_after.date, original_date)
        self.assertEqual(
            [(item.product.id, item.quantity) for item in cart_after._items],
            [(item.product.id, item.quantity) for item in original_items],
        )

    def test_patch_operations(self):
        dto = self.service.create_cart(
            7,
            {
                "products": [
                    {"product_id": 1, "quantity": 1},
                ]
            },
        )
        patched = self.service.patch_operations(
            dto.id,
            {
                "add": [{"product_id": 2, "quantity": 2}],
                "update": [{"product_id": 1, "quantity": 5}],
                "remove": [999],
            },
        )
        quantities = {item.product.id: item.quantity for item in patched.items}
        self.assertEqual(quantities[1], 5)
        self.assertEqual(quantities[2], 2)

    def test_delete_cart(self):
        dto = self.service.create_cart(
            8,
            {
                "products": [
                    {"product_id": 1, "quantity": 1},
                ]
            },
        )
        result = self.service.delete_cart(dto.id)
        self.assertTrue(result)
        self.assertIsNone(self.service.get_cart(dto.id))
        replacement = self.cart_repo.get(user_id=8)
        self.assertIsNotNone(replacement)
        self.assertNotEqual(replacement.id, dto.id)
        self.assertEqual(replacement._items, [])

    def test_delete_cart_for_staff_does_not_recreate(self):
        # Manually seed a cart for a staff user to simulate legacy data
        self.user_flags[40] = {"id": 40, "is_staff": True, "is_superuser": False}
        staff_cart = self.cart_repo.create(user_id=40, date=None)
        result = self.service.delete_cart(staff_cart.id)
        self.assertTrue(result)
        self.assertIsNone(self.cart_repo.get(user_id=40))


if __name__ == "__main__":
    unittest.main()
