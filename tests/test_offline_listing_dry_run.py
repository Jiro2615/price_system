from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_offline_listing_dry_run import build_offline_listing_dry_run
from scripts.extract_offline_listing_inputs import extract_offline_inputs


ROOT_DIR = Path(__file__).resolve().parents[1]


class OfflineListingDryRunTests(unittest.TestCase):
    def test_builds_dry_run_from_local_inputs_only(self) -> None:
        dry_run_json = ROOT_DIR / "output" / "listing" / "B0CN39X1FC_dry_run.json"
        temp_dir = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        input_dir = temp_dir / "input" / "B0CN39X1FC"
        extract_offline_inputs(dry_run_json, input_dir)
        output_json = temp_dir / "output" / "B0CN39X1FC_dry_run.json"
        result = build_offline_listing_dry_run(
            asin="B0CN39X1FC",
            amazon_json=input_dir / "amazon_result.json",
            keepa_json=input_dir / "keepa_result.json",
            store="rakuten_1",
            output_json=output_json,
            master_dir=ROOT_DIR / "reference" / "legacy_listing",
            allow_missing_master=True,
        )
        self.assertEqual(result["asin"], "B0CN39X1FC")
        self.assertEqual(result["amazon_result"]["requested_asin"], "B0CN39X1FC")
        self.assertEqual(result["keepa_result"]["asin"], "B0CN39X1FC")
        self.assertTrue(output_json.exists())

    def test_rejects_asin_mismatch_before_prepare(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        amazon_json = temp_dir / "amazon_result.json"
        keepa_json = temp_dir / "keepa_result.json"
        amazon_json.write_text(json.dumps({"requested_asin": "WRONG", "page_asin": "WRONG"}), encoding="utf-8")
        keepa_json.write_text(json.dumps({"asin": "WRONG"}), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            build_offline_listing_dry_run(
                asin="B000TEST01",
                amazon_json=amazon_json,
                keepa_json=keepa_json,
                store="rakuten_1",
                master_dir=ROOT_DIR / "reference" / "legacy_listing",
                allow_missing_master=True,
            )
