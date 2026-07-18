from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.listing.image_plan import build_image_download_plan
from scripts.listing.keepa_product_client import parse_keepa_product
from scripts.listing.master_loader import load_master_data
from scripts.listing.models import AmazonCheckResult, StoreSettings
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


ROOT_DIR = Path(__file__).resolve().parents[1]
REFERENCE_MASTER_DIR = ROOT_DIR / "reference" / "legacy_listing"


class ListingImagePlanTests(unittest.TestCase):
    def test_builds_main_and_sub_items_in_order(self) -> None:
        plan = build_image_download_plan(
            asin="b0test0001",
            image_urls=[
                "https://m.media-amazon.com/images/I/main.jpg",
                "https://m.media-amazon.com/images/I/sub1.jpg",
                "https://m.media-amazon.com/images/I/sub2.jpg",
            ],
            image_source="keepa_images",
            listing_status="eligible",
        )
        self.assertTrue(plan["execution_allowed"])
        self.assertIsNone(plan["blocked_reason"])
        self.assertEqual([item["role"] for item in plan["items"]], ["main", "sub", "sub"])
        self.assertEqual([item["order"] for item in plan["items"]], [1, 2, 3])
        self.assertEqual(plan["items"][0]["planned_filename"], "B0TEST0001_main.jpg")
        self.assertEqual(plan["items"][1]["planned_filename"], "B0TEST0001_01.jpg")
        self.assertEqual(plan["items"][2]["planned_filename"], "B0TEST0001_02.jpg")

    def test_uses_asin_relative_paths(self) -> None:
        plan = build_image_download_plan(
            asin="B0TEST0001",
            image_urls=["https://m.media-amazon.com/images/I/main.jpg"],
            image_source="keepa_images",
            listing_status="eligible",
        )
        self.assertEqual(plan["items"][0]["planned_relative_path"], "images/B0TEST0001/B0TEST0001_main.jpg")
        self.assertEqual(plan["items"][0]["source_image_id"], "main.jpg")

    def test_empty_urls_yield_empty_items(self) -> None:
        plan = build_image_download_plan(
            asin="B0TEST0001",
            image_urls=[],
            image_source="none",
            listing_status="eligible",
        )
        self.assertEqual(plan["items"], [])

    def test_business_ng_blocks_execution(self) -> None:
        plan = build_image_download_plan(
            asin="B0TEST0001",
            image_urls=["https://m.media-amazon.com/images/I/main.jpg"],
            image_source="keepa_images",
            listing_status="business_ng",
        )
        self.assertFalse(plan["execution_allowed"])
        self.assertEqual(plan["blocked_reason"], "listing_status is business_ng")
        self.assertFalse(plan["items"][0]["download_required"])

    def test_already_listed_and_system_error_block_execution(self) -> None:
        for status in ("already_listed", "system_error"):
            with self.subTest(status=status):
                plan = build_image_download_plan(
                    asin="B0TEST0001",
                    image_urls=["https://m.media-amazon.com/images/I/main.jpg"],
                    image_source="keepa_images",
                    listing_status=status,
                )
                self.assertFalse(plan["execution_allowed"])
                self.assertEqual(plan["blocked_reason"], f"listing_status is {status}")

    def test_b0cjr955sm_result_contains_image_download_plan_without_payload_generation(self) -> None:
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
        self.assertEqual(result["main_image_url"], "https://m.media-amazon.com/images/I/419M6DWuQVL.jpg")
        self.assertEqual(len(result["image_urls"]), 4)
        self.assertEqual(result["image_source"], "keepa_images")
        self.assertFalse(result["image_download_plan"]["execution_allowed"])
        self.assertEqual(result["image_download_plan"]["blocked_reason"], "listing_status is business_ng")
        self.assertEqual(len(result["image_download_plan"]["items"]), 4)
        self.assertEqual(result["image_download_plan"]["items"][0]["planned_filename"], "B0CJR955SM_main.jpg")
        self.assertEqual(result["image_download_plan"]["items"][1]["planned_filename"], "B0CJR955SM_01.jpg")
        self.assertEqual(
            result["image_download_plan"]["items"][0]["planned_relative_path"],
            "images/B0CJR955SM/B0CJR955SM_main.jpg",
        )
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])


if __name__ == "__main__":
    unittest.main()
