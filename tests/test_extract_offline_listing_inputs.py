from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_offline_listing_inputs import extract_offline_inputs


ROOT_DIR = Path(__file__).resolve().parents[1]


class ExtractOfflineListingInputsTests(unittest.TestCase):
    def test_extracts_amazon_keepa_and_metadata(self) -> None:
        dry_run_json = ROOT_DIR / "output" / "listing" / "B0CN39X1FC_dry_run.json"
        temp_dir = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        result = extract_offline_inputs(dry_run_json, temp_dir)
        self.assertEqual(result["asin"], "B0CN39X1FC")
        amazon_payload = json.loads((temp_dir / "amazon_result.json").read_text(encoding="utf-8"))
        keepa_payload = json.loads((temp_dir / "keepa_result.json").read_text(encoding="utf-8"))
        metadata_payload = json.loads((temp_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(amazon_payload["requested_asin"], "B0CN39X1FC")
        self.assertEqual(keepa_payload["asin"], "B0CN39X1FC")
        self.assertEqual(metadata_payload["asin"], "B0CN39X1FC")

    def test_refuses_overwrite_without_flag(self) -> None:
        dry_run_json = ROOT_DIR / "output" / "listing" / "B0CN39X1FC_dry_run.json"
        temp_dir = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        extract_offline_inputs(dry_run_json, temp_dir)
        with self.assertRaises(RuntimeError):
            extract_offline_inputs(dry_run_json, temp_dir, overwrite=False)
