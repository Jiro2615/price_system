import unittest

from scripts.price_check_one_asin_db import (
    max_quantity_from_dropdown_options,
    minimum_order_quantity_from_offer_text,
    quantity_dropdown_details,
)


class AmazonQuantityDropdownTests(unittest.TestCase):
    def test_returns_largest_numeric_option(self):
        self.assertEqual(max_quantity_from_dropdown_options(["1", "2", "3", "4", "5"]), 5)

    def test_ignores_non_quantity_option_text(self):
        self.assertEqual(max_quantity_from_dropdown_options(["数量", "", "1", "5", "さらに見る"]), 5)

    def test_returns_none_without_numeric_options(self):
        self.assertIsNone(max_quantity_from_dropdown_options(["数量を選択", "在庫あり"]))

    def test_detects_minimum_order_quantity(self):
        self.assertEqual(
            quantity_dropdown_details([("", "数量の選択"), ("2", "2 (最小注文個数)"), ("3", "3"), ("7", "7")]),
            (7, 2),
        )

    def test_detects_aod_minimum_order_quantity(self):
        self.assertEqual(minimum_order_quantity_from_offer_text("最小注文数: 2"), 2)

    def test_detects_aod_minimum_order_quantity_with_json_action(self):
        self.assertEqual(minimum_order_quantity_from_offer_text('{"minQty":3}'), 3)


if __name__ == "__main__":
    unittest.main()
