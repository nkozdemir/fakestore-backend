import unittest
from apps.carts.commands import CartCreateCommand, CartPatchCommand

class CartCommandTests(unittest.TestCase):
    def test_cart_create_command_normalization(self):
        cmd = CartCreateCommand.from_raw({
            'userId': '12',
            'date': '2025-01-02T10:20:30Z',
            'products': [
                {'productId': '5', 'quantity': '2'},
                {'productId': 6, 'quantity': 0},  # filtered (qty <=0)
                {'product': {'id': 7}, 'quantity': 3},
                {'productId': 'bad', 'quantity': '3'}  # filtered (bad id)
            ]
        })
        self.assertEqual(cmd.user_id, 12)
        self.assertEqual(len(cmd.items), 2)
        self.assertEqual({i.product_id for i in cmd.items}, {5, 7})

    def test_cart_patch_command(self):
        cmd = CartPatchCommand.from_raw(9, {
            'add': [{'productId': '10', 'quantity': 1}],
            'update': [{'productId': 11, 'quantity': '4'}],
            'remove': ['12', 'bad'],
            'date': '2025-02-03',
            'userId': '33'
        })
        self.assertEqual(cmd.cart_id, 9)
        self.assertEqual(len(cmd.add), 1)
        self.assertEqual(cmd.add[0].product_id, 10)
        self.assertEqual(cmd.update[0].quantity, 4)
        self.assertEqual(cmd.remove, [12])
        self.assertEqual(cmd.new_user_id, 33)
        self.assertEqual(cmd.new_date.isoformat(), '2025-02-03')
