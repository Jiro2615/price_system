from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from scripts.listing.legacy_comparison import load_legacy_baseline
from scripts.listing.legacy_sample_selector import select_legacy_comparison_samples


ROOT_DIR = Path(__file__).resolve().parents[1]


class LegacySampleSelectorTests(unittest.TestCase):
    def test_selects_expected_group_counts_without_duplicates(self) -> None:
        baseline = load_legacy_baseline(ROOT_DIR / "tests" / "fixtures" / "legacy_listing_baseline.json")
        samples = select_legacy_comparison_samples(baseline)
        counts = Counter(item["group"] for item in samples)
        self.assertEqual(len(samples), 32)
        self.assertEqual(counts["legacy_listed_success"], 10)
        self.assertEqual(counts["likely_false_positive"], 10)
        self.assertEqual(counts["regulatory_or_safety"], 8)
        self.assertEqual(counts["rakuten_api_error_ie0270"], 3)
        self.assertEqual(counts["fba_out_of_stock"], 1)
        self.assertEqual(len({item["asin"] for item in samples}), len(samples))

    def test_fixture_matches_selection(self) -> None:
        baseline = load_legacy_baseline(ROOT_DIR / "tests" / "fixtures" / "legacy_listing_baseline.json")
        expected = select_legacy_comparison_samples(baseline)
        fixture = json.loads((ROOT_DIR / "tests" / "fixtures" / "legacy_comparison_sample_asins.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture["samples"], expected)
