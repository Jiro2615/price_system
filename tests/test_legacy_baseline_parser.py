from __future__ import annotations

import unittest

from scripts.listing.legacy_baseline_parser import build_legacy_baseline


class LegacyBaselineParserTests(unittest.TestCase):
    def test_builds_listed_success_and_ng_entries(self) -> None:
        raw_text = (
            "処理対象 B000SUCCESS1 B000NG0001 B000API0001 "
            'NGリスト B000NG0001 禁止キーワード(医療) '
            'B000API0001 {"errors":[{"code":"IE0270","message":"Machine dependent characters cannot be registered.","metadata":{"propertyPath":"productDescription.pc"}}]}'
        )
        baseline = build_legacy_baseline(raw_text, raw_text)
        entries = {entry["asin"]: entry for entry in baseline["targets"]}

        self.assertEqual(entries["B000SUCCESS1"]["legacy_status"], "listed_success")
        self.assertTrue(entries["B000SUCCESS1"]["legacy_listing_completed"])
        self.assertEqual(entries["B000NG0001"]["legacy_reason_type"], "prohibited_word")
        self.assertEqual(entries["B000NG0001"]["legacy_forbidden_word"], "医療")
        self.assertEqual(entries["B000API0001"]["legacy_status"], "api_rejected")
        self.assertEqual(entries["B000API0001"]["legacy_property_paths"], ["productDescription.pc"])
        self.assertEqual(baseline["summary"]["legacy_listed_success_count"], 1)
        self.assertEqual(baseline["summary"]["legacy_failed_count"], 2)

    def test_reports_ng_only_inconsistency(self) -> None:
        target_text = "処理対象 B000ONLY001 NGリスト B000OUTSIDE1 FBA在庫切れ"
        baseline = build_legacy_baseline(target_text, target_text)
        self.assertEqual(baseline["diagnostics"]["ng_only_asins"], ["B000OUTSIDE1"])

