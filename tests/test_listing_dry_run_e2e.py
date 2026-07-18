from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.listing.master_loader import load_master_data
from scripts.listing.models import AmazonCheckResult, MasterData, StoreSettings, to_jsonable
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
REFERENCE_MASTER_DIR = ROOT_DIR / "reference" / "legacy_listing"


class ListingDryRunE2ETests(unittest.TestCase):
    def _run_offline_fixture(self) -> dict[str, object]:
        return prepare_listing(
            PrepareListingRequest(
                asin="B0ELIGIBLE1",
                store_code="rakuten_1",
                master_dir=REFERENCE_MASTER_DIR,
                offline=True,
                allow_missing_master=True,
                store_settings_json=FIXTURE_DIR / "eligible_store_settings.json",
                amazon_result_json=FIXTURE_DIR / "eligible_amazon_result.json",
                keepa_result_json=FIXTURE_DIR / "eligible_keepa_result.json",
            ),
            master_data_loader=load_master_data,
        )

    def test_eligible_fixture_reaches_final_dry_run(self) -> None:
        result = self._run_offline_fixture()
        self.assertEqual(result["asin"], "B0ELIGIBLE1")
        self.assertEqual(result["store_code"], "rakuten_1")
        self.assertEqual(result["listing_status"], "eligible")
        self.assertEqual(result["seller_count_evaluation"]["actual_value"], 4.0)
        self.assertTrue(result["seller_count_evaluation"]["passed"])
        self.assertIsNotNone(result["management_number"])
        self.assertIsNotNone(result["item_payload"])
        self.assertIsNotNone(result["inventory_payload"])
        self.assertTrue(result["execution_allowed"])
        self.assertTrue(result["execution_summary"]["can_execute_listing"])
        self.assertFalse(result["execution_summary"]["external_actions_performed"])
        self.assertEqual(result["image_source"], "keepa_images")
        self.assertEqual(len(result["image_urls"]), 4)
        self.assertTrue(result["image_download_plan"]["execution_allowed"])
        self.assertEqual(result["main_image_url"], "https://m.media-amazon.com/images/I/419M6DWuQVL.jpg")

        expected_attr_order = ["カラー", "シリーズ名", "ブランド名", "メーカー型番", "原産国／製造国"]
        payload_attrs = result["item_payload"]["variants"][result["management_number"]]["attributes"]
        self.assertEqual([item["name"] for item in payload_attrs], expected_attr_order)
        self.assertEqual([item["value"] for item in payload_attrs], ["-", "chapter", "Aíam", "-", "日本製"])
        self.assertEqual(payload_attrs[0]["value"], result["resolved_attributes"]["カラー"].value)

    def test_business_ng_saved_raw_has_blocking_reasons_and_resolved_attributes(self) -> None:
        from scripts.listing.keepa_product_client import parse_keepa_product

        raw = json.loads((ROOT_DIR / "output" / "keepa_inspect" / "B0CJR955SM_raw.json").read_text(encoding="utf-8"))
        keepa = parse_keepa_product("B0CJR955SM", raw["products"][0])
        store = StoreSettings(
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
        result = prepare_listing(
            PrepareListingRequest(
                asin="B0CJR955SM",
                store_code="rakuten_1",
                master_dir=REFERENCE_MASTER_DIR,
                dry_run=True,
                allow_missing_master=True,
            ),
            store_settings_loader=lambda store_code: store,
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
        self.assertFalse(result["execution_allowed"])
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])
        self.assertFalse(result["image_download_plan"]["execution_allowed"])
        self.assertIn("seller_count_below_threshold: 1.0 < 3.5", result["blocking_reasons"])
        self.assertEqual(result["resolved_attributes"]["カラー"].value, "-")
        self.assertEqual(result["resolved_attributes"]["シリーズ名"].value, "chapter")

    def test_already_listed_skips_external_and_marks_checklist(self) -> None:
        store = StoreSettings(
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
        master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={"B000LISTED1": "20250101010101_187"},
            category_map={},
            attribute_definitions={},
            missing_files=[],
        )
        result = prepare_listing(
            PrepareListingRequest(
                asin="B000LISTED1",
                store_code="rakuten_1",
                master_dir=Path("C:/dummy/master"),
                dry_run=True,
            ),
            store_settings_loader=lambda store_code: store,
            master_data_loader=lambda master_dir, allow_missing: master,
            amazon_fetcher=lambda asin, page_timeout_ms: (_ for _ in ()).throw(AssertionError("should not call Amazon")),
            keepa_fetcher=lambda asin: (_ for _ in ()).throw(AssertionError("should not call Keepa")),
        )
        self.assertEqual(result["listing_status"], "already_listed")
        self.assertFalse(result["execution_allowed"])
        self.assertIn("already_listed: 20250101010101_187", result["blocking_reasons"])
        checklist = {item["key"]: item for item in result["review_checklist"]}
        self.assertEqual(checklist["existing_management_number"]["status"], "blocked")

    def test_amazon_business_ng_blocks_before_keepa(self) -> None:
        store = StoreSettings(
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
        master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={},
            attribute_definitions={},
            missing_files=[],
        )
        result = prepare_listing(
            PrepareListingRequest(
                asin="B000AMZNG1",
                store_code="rakuten_1",
                master_dir=Path("C:/dummy/master"),
                dry_run=True,
            ),
            store_settings_loader=lambda store_code: store,
            master_data_loader=lambda master_dir, allow_missing: master,
            amazon_fetcher=lambda asin, page_timeout_ms: AmazonCheckResult(
                requested_asin="B000AMZNG1",
                page_asin="B000AMZNG1",
                title="ng",
                amazon_price=1000,
                available_qty=1,
                gift_available=False,
                shipping_status="ng",
                business_ng=True,
                system_error=False,
                ng_reason="Amazon business NG",
                current_url="",
            ),
            keepa_fetcher=lambda asin: (_ for _ in ()).throw(AssertionError("should not call Keepa")),
        )
        self.assertEqual(result["listing_status"], "business_ng")
        self.assertFalse(result["execution_allowed"])
        self.assertIn("business_ng: Amazon business NG", result["blocking_reasons"])

    def test_system_error_blocks_execution(self) -> None:
        store = StoreSettings(
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
        master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={},
            attribute_definitions={},
            missing_files=[],
        )
        result = prepare_listing(
            PrepareListingRequest(
                asin="B000SYSERR1",
                store_code="rakuten_1",
                master_dir=Path("C:/dummy/master"),
                dry_run=True,
            ),
            store_settings_loader=lambda store_code: store,
            master_data_loader=lambda master_dir, allow_missing: master,
            amazon_fetcher=lambda asin, page_timeout_ms: AmazonCheckResult(
                requested_asin="B000SYSERR1",
                page_asin="B000SYSERR1",
                title="",
                amazon_price=None,
                available_qty=None,
                gift_available=None,
                shipping_status="",
                business_ng=False,
                system_error=True,
                ng_reason="Amazon system error",
                current_url="",
            ),
            keepa_fetcher=lambda asin: (_ for _ in ()).throw(AssertionError("should not call Keepa")),
        )
        self.assertEqual(result["listing_status"], "system_error")
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["execution_summary"]["can_execute_listing"])

    def test_warnings_include_fallbacks_and_image_not_checked(self) -> None:
        result = self._run_offline_fixture()
        warnings = result["warnings"]
        self.assertTrue(any("legacy dash fallback" in item for item in warnings))
        self.assertTrue(any("inferred value used" in item for item in warnings))
        self.assertIn("image validation not checked", warnings)

    def test_final_results_are_json_serializable(self) -> None:
        eligible = self._run_offline_fixture()
        text = json.dumps(to_jsonable(eligible), ensure_ascii=False)
        self.assertIn("execution_summary", text)


if __name__ == "__main__":
    unittest.main()
