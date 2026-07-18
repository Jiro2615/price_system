from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.listing.legacy_offline_input_scanner import scan_offline_input


ROOT_DIR = Path(__file__).resolve().parents[1]


class LegacyOfflineInputScannerTests(unittest.TestCase):
    def test_reports_missing_files(self) -> None:
        root = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        result = scan_offline_input("B000MISS01", search_roots=[root])
        self.assertFalse(result["directory_exists"])
        self.assertIn("directory", result["missing_components"])
        self.assertFalse(result["reusable_for_offline_evaluation"])

    def test_reports_invalid_json_and_asin_mismatch(self) -> None:
        root = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        target_dir = root / "B000TEST01"
        target_dir.mkdir()
        (target_dir / "amazon_result.json").write_text("{broken", encoding="utf-8")
        (target_dir / "keepa_result.json").write_text(json.dumps({"asin": "WRONG"}), encoding="utf-8")
        result = scan_offline_input("B000TEST01", search_roots=[root])
        self.assertFalse(result["amazon_json_valid"])
        self.assertFalse(result["keepa_json_valid"])
        self.assertTrue(result["validation_errors"])

    def test_reports_reusable_when_both_inputs_are_valid(self) -> None:
        root = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        target_dir = root / "B000TEST01"
        target_dir.mkdir()
        (target_dir / "amazon_result.json").write_text(
            json.dumps(
                {
                    "requested_asin": "B000TEST01",
                    "page_asin": "B000TEST01",
                    "title": "title",
                }
            ),
            encoding="utf-8",
        )
        (target_dir / "keepa_result.json").write_text(
            json.dumps(
                {
                    "asin": "B000TEST01",
                    "title": "title",
                }
            ),
            encoding="utf-8",
        )
        (root / "B000TEST01_dry_run.json").write_text("{}", encoding="utf-8")
        result = scan_offline_input("B000TEST01", search_roots=[root])
        self.assertTrue(result["amazon_json_valid"])
        self.assertTrue(result["keepa_json_valid"])
        self.assertTrue(result["asin_matches"])
        self.assertTrue(result["reusable_for_offline_evaluation"])
        self.assertEqual(result["selected_directory"], str(target_dir))
        self.assertEqual(result["dry_run_json_sources"], [str(root / "B000TEST01_dry_run.json")])
