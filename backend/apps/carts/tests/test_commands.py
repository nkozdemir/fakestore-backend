import unittest
from apps.carts.commands import (
    CartCreateCommand,
    CartPatchCommand,
    CartUpdateCommand,
)


class CartCommandTests(unittest.TestCase):
    def test_cart_create_command_normalization(self):
        cmd = CartCreateCommand.from_raw(
            {
                "userId": "12",
                "date": "2025-01-02T10:20:30Z",
                "products": [
                    {"product_id": "5", "quantity": "2"},
                    {"product_id": 6, "quantity": 0},  # filtered (qty <=0)
                    {"productId": 7, "quantity": 3},  # filtered (legacy key)
                    {"product": {"id": 8}, "quantity": 3},  # filtered (legacy nested)
                    {"product_id": "bad", "quantity": "3"},  # filtered (bad id)
                ],
            }
        )
        self.assertEqual(cmd.user_id, 12)
        self.assertEqual(len(cmd.items), 1)
        self.assertEqual({i.product_id for i in cmd.items}, {5})

    def test_cart_patch_command(self):
        cmd = CartPatchCommand.from_raw(
            9,
            {
                "add": [{"product_id": "10", "quantity": 1}],
                "update": [{"product_id": 11, "quantity": "4"}],
                "remove": ["12", "bad"],
                "date": "2025-02-03",
                "userId": "33",
            },
        )
        self.assertEqual(cmd.cart_id, 9)
        self.assertEqual(len(cmd.add), 1)
        self.assertEqual(cmd.add[0].product_id, 10)
        self.assertEqual(cmd.update[0].quantity, 4)
        self.assertEqual(cmd.remove, [12])
        self.assertEqual(cmd.new_user_id, 33)
        self.assertEqual(cmd.new_date.isoformat(), "2025-02-03")

    def test_cart_update_command_requires_snake_case_items(self):
        cmd = CartUpdateCommand.from_raw(
            5, {"items": [{"product_id": "8", "quantity": "3"}]}
        )
        self.assertEqual(cmd.cart_id, 5)
        self.assertIsNotNone(cmd.items)
        self.assertEqual(len(cmd.items), 1)
        self.assertEqual(cmd.items[0].product_id, 8)
        self.assertEqual(cmd.items[0].quantity, 3)

    def test_cart_update_command_discards_legacy_item_formats(self):
        cmd = CartUpdateCommand.from_raw(
            6,
            {
                "items": [
                    {"productId": 9, "quantity": 1},
                    {"product": {"id": 10}, "quantity": 2},
                ]
            },
        )
        self.assertEqual(cmd.cart_id, 6)
        self.assertEqual(cmd.items, [])
