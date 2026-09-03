from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import export_rakuten_normal_item_price_csv as price_csv  # noqa: E402


class RakutenPriceCsvManifestTests(unittest.TestCase):
    def test_uses_only_the_confirmed_store_and_normal_item_fields(self) -> None:
        payload = {
            "total_targets": 2,
            "items": [
                {
                    "store_product_id": 1,
                    "store_code": "rakuten_2",
                    "asin": "B000000001",
                    "manageNumber": "item-1",
                    "variantId": "item-1-red",
                    "item_name": "confirmed item",
                    "current_price": 1000,
                    "target_price": 1200,
                    "current_stock": 1,
                    "target_stock": 1,
                },
                {
                    "store_product_id": 2,
                    "store_code": "rakuten_1",
                    "asin": "B000000002",
                    "manageNumber": "item-2",
                    "variantId": "item-2-blue",
                    "current_price": 1000,
                    "target_price": 1300,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "targets.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            rows, skipped = price_csv.fetch_price_targets_from_manifest(
                manifest_path=manifest,
                store_code="rakuten_2",
                limit=50000,
                include_stock=False,
                allow_large_change=True,
                max_change_rate=0.5,
            )

        self.assertEqual([], skipped)
        self.assertEqual(1, len(rows))
        self.assertEqual("item-1", rows[0]["mall_item_code"])
        self.assertEqual("item-1-red", rows[0]["sku_code"])
        self.assertEqual(
            [["item-1", "", "", ""], ["item-1", "", "item-1-red", 1200]],
            price_csv.make_normal_item_rows(rows, include_stock=False, include_product_rows=True),
        )

    def test_invalid_confirmed_target_is_reported_as_skip(self) -> None:
        payload = {
            "items": [
                {
                    "store_code": "rakuten_2",
                    "manageNumber": "item-1",
                    "variantId": "",
                    "target_price": 1200,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "targets.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            rows, skipped = price_csv.fetch_price_targets_from_manifest(
                manifest_path=manifest,
                store_code="rakuten_2",
                limit=50000,
                include_stock=False,
                allow_large_change=True,
                max_change_rate=0.5,
            )

        self.assertEqual([], rows)
        self.assertEqual("SKU管理番号が空", skipped[0]["_skip_reason"])


if __name__ == "__main__":
    unittest.main()
