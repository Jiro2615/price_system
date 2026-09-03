import unittest
from unittest.mock import patch

from scripts.price_check_one_asin_db import (
    delivery_promise_end_date,
    delivery_within_one_week,
    parse_shipping_status,
)


class AmazonDeliveryRangeTests(unittest.TestCase):
    def test_uses_the_end_of_a_same_month_delivery_range(self) -> None:
        self.assertEqual(
            delivery_promise_end_date("無料配送 9月9日-15日にお届け", require_delivery_context=True),
            (9, 15),
        )

    def test_uses_the_end_of_a_cross_month_delivery_range(self) -> None:
        self.assertEqual(
            delivery_promise_end_date("無料配送 12月30日-1月2日にお届け", require_delivery_context=True),
            (1, 2),
        )

    def test_aod_range_is_judged_by_its_last_date(self) -> None:
        with patch(
            "scripts.price_check_one_asin_db.calc_diff_days", return_value=7
        ) as calc_diff_days:
            self.assertTrue(delivery_within_one_week("9月9日-15日"))
        calc_diff_days.assert_called_once_with(9, 15)

    def test_buybox_range_is_judged_by_its_last_date(self) -> None:
        with patch(
            "scripts.price_check_one_asin_db.calc_diff_days", return_value=6
        ) as calc_diff_days:
            self.assertEqual(
                parse_shipping_status("無料配送 9月9日-15日にお届け"),
                ("OK", "配送OK"),
            )
        calc_diff_days.assert_called_once_with(9, 15)


if __name__ == "__main__":
    unittest.main()
