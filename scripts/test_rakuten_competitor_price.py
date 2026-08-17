import unittest

from calc_store_targets import apply_rakuten_competitor_price_floor, apply_rakuten_competitor_price_rules
from rakuten_competitor_price_check import normalize_items


class RakutenCompetitorPriceTests(unittest.TestCase):
    def test_competitor_price_only_raises_base_target_when_enabled(self):
        self.assertEqual(apply_rakuten_competitor_price_floor(1200, False, 1500), (1200, False))
        self.assertEqual(apply_rakuten_competitor_price_floor(1200, True, 1100), (1200, False))
        self.assertEqual(apply_rakuten_competitor_price_floor(1200, True, 1500), (1500, True))

    def test_modern_and_legacy_api_item_shapes_are_normalized(self):
        self.assertEqual(normalize_items({"items": [{"itemPrice": 100}]}), [{"itemPrice": 100}])
        self.assertEqual(normalize_items({"Items": [{"Item": {"itemPrice": 200}}]}), [{"itemPrice": 200}])

    def test_undercut_uses_competitor_price_only_when_minimum_profit_is_met(self):
        result = apply_rakuten_competitor_price_rules(
            base_target_price=1500,
            competitor_price_enabled=True,
            competitor_lowest_price=1800,
            competitor_undercut_yen=50,
            competitor_floor_enabled=False,
            competitor_undercut_enabled=True,
            competitor_min_profit_amount=200,
            amazon_price=1000,
            amazon_point=0,
            use_amazon_point=False,
            fee_rate=0.1,
            fixed_cost=0,
        )
        self.assertEqual(result, (1750, "rakuten_competitor_undercut=1750/profit=575"))
        rejected = apply_rakuten_competitor_price_rules(
            base_target_price=1500,
            competitor_price_enabled=True,
            competitor_lowest_price=1300,
            competitor_undercut_yen=50,
            competitor_floor_enabled=False,
            competitor_undercut_enabled=True,
            competitor_min_profit_amount=200,
            amazon_price=1000,
            amazon_point=0,
            use_amazon_point=False,
            fee_rate=0.1,
            fixed_cost=0,
        )
        self.assertEqual(rejected, (1500, ""))


if __name__ == "__main__":
    unittest.main()
