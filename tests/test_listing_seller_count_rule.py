from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.listing.keepa_product_client import parse_keepa_product
from scripts.listing.listing_evaluator import evaluate_listing
from scripts.listing.master_loader import load_master_data
from scripts.listing.models import AmazonCheckResult, KeepaProductData, MasterData, StoreSettings
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
REFERENCE_MASTER_DIR = ROOT_DIR / "reference" / "legacy_listing"


class ListingSellerCountRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={10219786051: 101737},
            attribute_definitions={101737: ["ブランド名", "メーカー型番"]},
            missing_files=[],
        )
        self.store = StoreSettings(
            store_id=4,
            store_code="rakuten_1",
            store_name="rakuten_1",
            max_stock=4,
            fee_rate=0.15,
            use_amazon_point=False,
            profit_mode="amount",
            profit_rate=0.0,
            profit_amount=300,
            fixed_cost=0,
            rounding_unit=1,
            normal_delivery_date_id=1,
            back_order_delivery_date_id=1,
            normal_delivery_time_id=1,
            back_order_delivery_time_id=1,
            ship_from_ids=["1"],
        )
        self.amazon = AmazonCheckResult(
            requested_asin="B000TEST01",
            page_asin="B000TEST01",
            title="Amazon商品タイトル",
            amazon_price=2000,
            available_qty=9,
            gift_available=True,
            shipping_status="next day shipping",
            business_ng=False,
            system_error=False,
            ng_reason="",
            current_url="",
        )

    def _keepa(self, avg90_new_offer_count: float | None) -> KeepaProductData:
        compatibility_value = None if avg90_new_offer_count is None else avg90_new_offer_count
        return KeepaProductData(
            asin="B000TEST01",
            title="Keepa商品タイトル",
            brand="テストブランド",
            model="MODEL-1",
            ean="1234567890123",
            images_csv="abc123",
            category_id=10219786051,
            features=["特徴1"],
            description="商品説明",
            style="スタイルA",
            size="L",
            color="ブラック",
            avg90_new_offer_count=avg90_new_offer_count,
            avg90_seller_count=compatibility_value,
            is_adult=False,
        )

    def test_349_is_business_ng(self) -> None:
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=self._keepa(3.49),
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "business_ng")
        self.assertIn("3.49 < 3.5", result.listing_reason)
        self.assertFalse(result.seller_count_evaluation["passed"])

    def test_35_passes(self) -> None:
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=self._keepa(3.5),
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        self.assertTrue(result.seller_count_evaluation["passed"])

    def test_351_passes(self) -> None:
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=self._keepa(3.51),
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        self.assertTrue(result.seller_count_evaluation["passed"])

    def test_null_does_not_immediately_fail(self) -> None:
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=self._keepa(None),
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        self.assertTrue(result.seller_count_evaluation["passed"])
        self.assertIsNone(result.seller_count_evaluation["actual_value"])

    def test_b0cjr955sm_is_business_ng_and_keeps_resolved_attributes(self) -> None:
        raw = json.loads((ROOT_DIR / "output" / "keepa_inspect" / "B0CJR955SM_raw.json").read_text(encoding="utf-8"))
        keepa = parse_keepa_product("B0CJR955SM", raw["products"][0])
        result = prepare_listing(
            PrepareListingRequest(
                asin="B0CJR955SM",
                store_code="rakuten_1",
                master_dir=REFERENCE_MASTER_DIR,
                dry_run=True,
                allow_missing_master=True,
            ),
            store_settings_loader=lambda store_code: self.store,
            master_data_loader=load_master_data,
            amazon_fetcher=lambda asin, page_timeout_ms: AmazonCheckResult(
                requested_asin="B0CJR955SM",
                page_asin="B0CJR955SM",
                title=keepa.title,
                amazon_price=5980,
                available_qty=4,
                gift_available=True,
                shipping_status="fixture",
                business_ng=False,
                system_error=False,
                ng_reason="",
                current_url="",
            ),
            keepa_fetcher=lambda asin: keepa,
        )
        self.assertEqual(result["listing_status"], "business_ng")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])
        self.assertEqual(result["seller_count_evaluation"]["actual_value"], 1.0)
        self.assertEqual(result["seller_count_evaluation"]["minimum_value"], 3.5)
        self.assertFalse(result["seller_count_evaluation"]["passed"])
        self.assertEqual(result["resolved_attributes"]["カラー"].value, "-")
        self.assertEqual(result["resolved_attributes"]["シリーズ名"].value, "chapter")
        self.assertEqual(result["resolved_attributes"]["ブランド名"].value, "Aíam")
        self.assertEqual(result["resolved_attributes"]["メーカー型番"].value, "-")
        self.assertEqual(result["resolved_attributes"]["原産国／製造国"].value, "日本製")

    def test_offline_fixture_can_use_new_common_setting_name_without_store_duplication(self) -> None:
        store_payload = json.loads((FIXTURE_DIR / "offline_store_settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("min_avg90_new_offer_count", store_payload)
        self.assertIn("min_avg90_sellers", store_payload)


if __name__ == "__main__":
    unittest.main()
