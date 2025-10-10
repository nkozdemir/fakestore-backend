import unittest
from apps.catalog.commands import (
    ProductCreateCommand,
    ProductUpdateCommand,
    RatingSetCommand,
)


class ProductCommandTests(unittest.TestCase):
    def test_create_command_parses_categories_and_strips_id(self):
        cmd = ProductCreateCommand.from_raw(
            {
                "id": 999,
                "title": "  Phone  ",
                "price": "10.00",
                "description": " Desc ",
                "image": "img",
                "categories": ["1", "x", 2],
                "rate": 4.5,
                "count": 3,
            }
        )
        self.assertEqual(cmd.title, "Phone")
        self.assertEqual(cmd.categories, [1, 2])
        self.assertIsNone(getattr(cmd, "id", None))

    def test_update_command_partial(self):
        cmd = ProductUpdateCommand.from_raw(
            5, {"title": "New", "categories": ["3", "bad"]}, partial=True
        )
        self.assertEqual(cmd.product_id, 5)
        self.assertEqual(cmd.title, "New")
        self.assertEqual(cmd.categories, [3])
        self.assertTrue(cmd.partial)
        self.assertIsNone(cmd.price)

    def test_rating_set_command_invalid_value(self):
        cmd = RatingSetCommand.from_raw(7, 2, "bad")
        self.assertEqual(cmd.value, -1)
