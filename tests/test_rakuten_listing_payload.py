from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.listing import amazon_bridge
from scripts.listing.listing_evaluator import evaluate_listing
from scripts.listing.master_loader import load_master_data
from scripts.listing.management_number import generate_management_number_bundle
from scripts.listing.models import AmazonCheckResult, KeepaProductData, MasterData, StoreSettings, sanitize_for_output, to_jsonable
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing
from scripts.listing.rakuten_payload_builder import build_inventory_payload, build_item_payload


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
REFERENCE_MASTER_DIR = Path(__file__).resolve().parents[1] / "reference" / "legacy_listing"


class RakutenListingPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_keepa_category_id = 10219786051
        self.valid_rakuten_genre_id = 101737
        self.master = MasterData(
            blacklist={"B000BLACK01"},
            kako_ng={"B000NG0001": "\u904e\u53bbNG\u7406\u7531"},
            replacements=[("\u65e7\u8a9e", ""), ("Amazon", "AMZ")],
            prohibited_words_rakuten=["18\u7981"],
            prohibited_words_other=["\u9055\u6cd5"],
            listed_asins={"B000LISTED1": "20250101010101_187"},
            category_map={self.valid_keepa_category_id: self.valid_rakuten_genre_id},
            attribute_definitions={self.valid_rakuten_genre_id: ["\u30d6\u30e9\u30f3\u30c9\u540d", "\u30e1\u30fc\u30ab\u30fc\u578b\u756a"]},
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
            min_avg90_sellers=3.5,
        )
        self.amazon = AmazonCheckResult(
            requested_asin="B000TEST01",
            page_asin="B000TEST01",
            title="Amazon\u65e7\u8a9e\u30c6\u30b9\u30c8\u5546\u54c1",
            amazon_price=2000,
            available_qty=9,
            gift_available=True,
            shipping_status="next day shipping",
            business_ng=False,
            system_error=False,
            ng_reason="",
            current_url="https://www.amazon.co.jp/dp/B000TEST01?th=1&psc=1",
        )
        self.keepa = KeepaProductData(
            asin="B000TEST01",
            title="Keepa\u5546\u54c1\u30bf\u30a4\u30c8\u30eb",
            brand="\u30c6\u30b9\u30c8\u30d6\u30e9\u30f3\u30c9",
            model="MODEL-1",
            ean="1234567890123",
            images_csv="abc123,def456",
            category_id=self.valid_keepa_category_id,
            features=["\u7279\u5fb41", "\u7279\u5fb42"],
            description="\u5546\u54c1\u8aac\u660e\u30c6\u30ad\u30b9\u30c8",
            style="\u30b9\u30bf\u30a4\u30ebA",
            size="L",
            color="\u30d6\u30e9\u30c3\u30af",
            buy_box_price=1980,
            buy_box_shipping=0,
            avg90_seller_count=4.2,
            is_adult=False,
        )

    def test_blacklist_blocks_listing(self) -> None:
        result = evaluate_listing(
            asin="B000BLACK01",
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "business_ng")

    def test_kako_ng_blocks_listing(self) -> None:
        result = evaluate_listing(
            asin="B000NG0001",
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertIn("\u904e\u53bbNG", result.listing_reason)

    def test_already_listed_status(self) -> None:
        result = evaluate_listing(
            asin="B000LISTED1",
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "already_listed")

    def test_prohibited_word_blocks_listing(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "description": "\u3053\u308c\u306f18\u7981\u306e\u8aac\u660e\u3067\u3059"})
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "business_ng")
        self.assertIn("prohibited word", result.listing_reason)

    def test_unknown_category(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "category_id": 99999})
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "unknown_category")

    def test_missing_required_attribute(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "model": ""})
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "missing_required_data")
        self.assertIn("\u30e1\u30fc\u30ab\u30fc\u578b\u756a", result.listing_reason)

    def test_ean_fallback_to_asin(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "ean": ""})
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        self.assertEqual(result.article_number, "B000TEST01")

    def test_payload_builders(self) -> None:
        evaluation = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(evaluation.listing_status, "eligible")

        item_payload = build_item_payload(
            management_number="20250101010101_187_ab12",
            evaluation=evaluation,
            store_settings=self.store,
            amazon_price=self.amazon.amazon_price or 0,
            amazon_point=0,
        )
        inventory_payload = build_inventory_payload(
            management_number="20250101010101_187_ab12",
            quantity=self.amazon.available_qty or 0,
            store_settings=self.store,
        )

        self.assertEqual(item_payload["itemNumber"], "20250101010101_187_ab12")
        self.assertEqual(item_payload["genreId"], str(self.valid_rakuten_genre_id))
        self.assertEqual(item_payload["features"]["inventoryDisplay"], "DISPLAY_ABSOLUTE_STOCK_COUNT")
        self.assertIsInstance(item_payload["variants"]["20250101010101_187_ab12"]["standardPrice"], str)
        self.assertEqual(item_payload["payment"]["taxRate"], "0.1")
        self.assertEqual(item_payload["variants"]["20250101010101_187_ab12"]["articleNumber"], {"exemptionReason": 5})
        self.assertEqual(inventory_payload["quantity"], 4)
        self.assertEqual(inventory_payload["shipFromIds"], [1])

    def test_management_number_bundle(self) -> None:
        bundle = generate_management_number_bundle("187", datetime(2026, 7, 8, 10, 11, 12))
        self.assertEqual(bundle.legacy_candidate, "20260708101112_187")
        self.assertTrue(bundle.selected.startswith("20260708101112_187_"))
        self.assertNotEqual(bundle.selected, bundle.legacy_candidate)

    def test_secret_is_not_exposed(self) -> None:
        payload = {
            "keepa_api_key": "SECRET-123",
            "authorization": "Bearer abc",
            "listing_status": "eligible",
        }
        public_payload = sanitize_for_output(payload)
        text = json.dumps(to_jsonable(public_payload), ensure_ascii=False)
        self.assertNotIn("SECRET-123", text)
        self.assertNotIn("Bearer abc", text)

    def test_prepare_listing_uses_injected_dependencies(self) -> None:
        result = prepare_listing(
            PrepareListingRequest(
                asin="b000test01",
                store_code="rakuten_1",
                master_dir=Path("C:/dummy/master"),
                dry_run=True,
            ),
            store_settings_loader=lambda store_code: self.store,
            master_data_loader=lambda master_dir, allow_missing: self.master,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon,
            keepa_fetcher=lambda asin: self.keepa,
        )

        self.assertEqual(result["asin"], "B000TEST01")
        self.assertEqual(result["mode"], "dry_run")
        self.assertEqual(result["listing_status"], "eligible")
        self.assertEqual(result["item_payload"]["itemNumber"], result["management_number"])
        self.assertEqual(result["inventory_payload"]["quantity"], 4)

    def test_prepare_listing_skip_flags_append_warnings(self) -> None:
        result = prepare_listing(
            PrepareListingRequest(
                asin="B000TEST01",
                store_code="rakuten_1",
                master_dir=Path("C:/dummy/master"),
                skip_amazon=True,
                skip_keepa=True,
            ),
            store_settings_loader=lambda store_code: self.store,
            master_data_loader=lambda master_dir, allow_missing: self.master,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon,
            keepa_fetcher=lambda asin: self.keepa,
        )

        warnings = result["warnings"]
        self.assertIn("\u3053\u306e\u30b3\u30de\u30f3\u30c9\u306f\u975e\u7834\u58ca\u30e2\u30fc\u30c9\u5c02\u7528\u306e\u305f\u3081\u3001dry-run \u3068\u3057\u3066\u7d9a\u884c\u3057\u307e\u3059", warnings)
        self.assertIn("Amazon check skipped by CLI option", warnings)
        self.assertIn("Keepa check skipped by CLI option", warnings)

    def test_amazon_bridge_allows_missing_log_result_summary(self) -> None:
        async def fake_check_amazon_one(
            asin: str,
            page_timeout_ms: int = 15000,
            debug_html: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(asin, "B000TEST01")
            self.assertEqual(page_timeout_ms, 1234)
            self.assertFalse(debug_html)
            return {
                "asin": asin,
                "title": "Amazon正常テスト商品",
                "amazon_price": 2000,
                "available_qty": 9,
                "gift_available": True,
                "shipping_status": "next day shipping",
                "business_ng": False,
                "system_error": False,
                "ng_reason": "",
            }

        fake_module = SimpleNamespace(check_amazon_one=fake_check_amazon_one)

        with mock.patch.object(amazon_bridge, "_amazon_module", fake_module):
            result = amazon_bridge.fetch_amazon_result_sync("B000TEST01", page_timeout_ms=1234)

        self.assertEqual(result.requested_asin, "B000TEST01")
        self.assertEqual(result.page_asin, "B000TEST01")
        self.assertEqual(result.title, "Amazon正常テスト商品")
        self.assertEqual(result.amazon_price, 2000)
        self.assertEqual(result.available_qty, 9)
        self.assertTrue(result.gift_available)
        self.assertEqual(result.shipping_status, "next day shipping")
        self.assertEqual(result.current_url, "")

    def test_brand_prefers_brand_over_manufacturer(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "manufacturer": "\u5225\u30e1\u30fc\u30ab\u30fc"})
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        brand_attr = next(item for item in result.attributes if item["name"] == "\u30d6\u30e9\u30f3\u30c9\u540d")
        self.assertEqual(brand_attr["value"], "\u30c6\u30b9\u30c8\u30d6\u30e9\u30f3\u30c9")

    def test_brand_falls_back_to_manufacturer(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "brand": "", "manufacturer": "\u30c6\u30b9\u30c8\u30e1\u30fc\u30ab\u30fc"})
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        brand_attr = next(item for item in result.attributes if item["name"] == "\u30d6\u30e9\u30f3\u30c9\u540d")
        self.assertEqual(brand_attr["value"], "\u30c6\u30b9\u30c8\u30e1\u30fc\u30ab\u30fc")

    def test_model_falls_back_to_part_number(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "model": "", "part_number": "PART-1"})
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        model_attr = next(item for item in result.attributes if item["name"] == "\u30e1\u30fc\u30ab\u30fc\u578b\u756a")
        self.assertEqual(model_attr["value"], "PART-1")

    def test_listing_evaluator_prefers_image_urls_over_images_csv(self) -> None:
        keepa = KeepaProductData(
            **{
                **self.keepa.__dict__,
                "images_csv": "legacy1,legacy2",
                "image_urls": ["https://m.media-amazon.com/images/I/preferred.jpg"],
                "image_source": "keepa_images",
            }
        )
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        self.assertEqual(result.image_candidates[0]["source"], "https://m.media-amazon.com/images/I/preferred.jpg")

    def test_listing_evaluator_uses_images_csv_for_legacy_fixture(self) -> None:
        result = evaluate_listing(
            asin="B000TEST01",
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(result.listing_status, "eligible")
        self.assertEqual(
            [item["source"] for item in result.image_candidates],
            [
                "https://m.media-amazon.com/images/I/abc123.jpg",
                "https://m.media-amazon.com/images/I/def456.jpg",
            ],
        )

    def test_offline_mode_generates_payload_from_fixture_json(self) -> None:
        def fail_store_loader(store_code: str) -> StoreSettings:
            raise AssertionError("offline mode must not query store settings from DB")

        def fail_amazon_fetcher(asin: str, page_timeout_ms: int) -> AmazonCheckResult:
            raise AssertionError("offline mode must not call Amazon")

        def fail_keepa_fetcher(asin: str) -> KeepaProductData:
            raise AssertionError("offline mode must not call Keepa")

        result = prepare_listing(
            PrepareListingRequest(
                asin="B000TEST01",
                store_code="rakuten_1",
                master_dir=REFERENCE_MASTER_DIR,
                offline=True,
                allow_missing_master=True,
                store_settings_json=FIXTURE_DIR / "offline_store_settings.json",
                amazon_result_json=FIXTURE_DIR / "offline_amazon_result.json",
                keepa_result_json=FIXTURE_DIR / "offline_keepa_result.json",
            ),
            store_settings_loader=fail_store_loader,
            master_data_loader=load_master_data,
            amazon_fetcher=fail_amazon_fetcher,
            keepa_fetcher=fail_keepa_fetcher,
        )

        self.assertEqual(result["mode"], "offline")
        self.assertEqual(result["listing_status"], "eligible")
        self.assertIn("\u51fa\u54c1\u53ef\u80fd", result["listing_reason"])
        self.assertEqual(result["item_payload"]["itemNumber"], result["management_number"])
        self.assertEqual(result["item_payload"]["genreId"], str(self.valid_rakuten_genre_id))
        self.assertEqual(result["item_payload"]["payment"]["taxRate"], "0.1")
        self.assertEqual(result["item_payload"]["variants"][result["management_number"]]["articleNumber"], {"exemptionReason": 5})
        self.assertEqual(result["inventory_payload"]["quantity"], 4)
        self.assertEqual(result["inventory_payload"]["operationLeadTime"]["normalDeliveryTimeId"], 1)
        self.assertEqual(result["inventory_payload"]["operationLeadTime"]["backOrderDeliveryTimeId"], 1)
        self.assertEqual(result["inventory_payload"]["shipFromIds"], [1])
        self.assertIn("\u30aa\u30d5\u30e9\u30a4\u30f3\u30e2\u30fc\u30c9: \u30ed\u30fc\u30ab\u30eb fixture JSON \u306e\u307f\u3092\u4f7f\u7528\u3057\u307e\u3059", result["warnings"])
        self.assertIn("missing master files: kinsiword_other.txt", result["warnings"])


if __name__ == "__main__":
    unittest.main()
