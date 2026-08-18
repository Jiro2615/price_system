import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from price_check_one_asin_db import (
    is_amazon_delivery_origin_offer_text,
    is_amazon_fulfilled_offer_text,
    is_eligible_buybox_condition_text,
    judge_basic_ng,
)


class AmazonShipFromPolicyTests(unittest.TestCase):
    def test_delivery_origin_amazon_is_rejected(self) -> None:
        self.assertTrue(is_amazon_delivery_origin_offer_text("配送元: Amazon.co.jp"))
        self.assertTrue(is_amazon_delivery_origin_offer_text("発送元 Amazon"))
        self.assertIn("配送元Amazon", judge_basic_ng("ギフト 配送元 Amazon.co.jp"))

    def test_explicit_ship_from_amazon_is_not_rejected(self) -> None:
        self.assertFalse(is_amazon_delivery_origin_offer_text("出荷元: Amazon.co.jp"))

    def test_combined_amazon_official_buybox_is_eligible_without_new_label(self) -> None:
        text = "出荷元 / 販売元\nAmazon.co.jp\n無料配送 明日お届け"
        self.assertTrue(is_amazon_fulfilled_offer_text(text))
        self.assertTrue(is_eligible_buybox_condition_text(text))

    def test_amazon_fulfilled_buybox_is_eligible_without_new_label(self) -> None:
        text = "出荷元\nAmazon\n販売元\nSouth's Choice\n無料配送 明日お届け"
        self.assertTrue(is_amazon_fulfilled_offer_text(text))
        self.assertTrue(is_eligible_buybox_condition_text(text))

    def test_combined_amazon_official_buybox_stays_ineligible_when_used(self) -> None:
        text = "中古 - 非常に良い\n出荷元 / 販売元\nAmazon.co.jp"
        self.assertFalse(is_eligible_buybox_condition_text(text))


if __name__ == "__main__":
    unittest.main()
