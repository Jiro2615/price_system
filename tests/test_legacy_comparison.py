from __future__ import annotations

import unittest

from scripts.listing.legacy_comparison import compare_with_saved_results
from scripts.listing.models import sanitize_for_output


class LegacyComparisonTests(unittest.TestCase):
    def test_classifies_legacy_success_new_ng_with_review(self) -> None:
        baseline = {
            "meta": {"source": "test"},
            "summary": {"legacy_listed_success_count": 1, "legacy_failed_count": 0, "listing_success_rate": 1.0},
            "diagnostics": {"ng_only_asins": []},
            "targets": [
                {
                    "asin": "B000SUCCESS1",
                    "legacy_status": "listed_success",
                    "legacy_reason_type": None,
                    "legacy_reason": None,
                    "legacy_listing_completed": True,
                }
            ],
        }
        new_result = {
            "listing_status": "business_ng",
            "listing_reason": "過去90日の新品出品者数平均が基準未満: 1.0 < 3.5",
            "seller_count_evaluation": {
                "metric": "avg90_new_offer_count",
                "actual_value": 1.0,
                "minimum_value": 3.5,
                "passed": False,
            },
            "matched_forbidden_words": [],
            "allowed_phrase_matches": [],
            "legacy_spacing_reviews": [],
            "blocking_reasons": ["business_ng: threshold"],
        }
        report = compare_with_saved_results(baseline, result_loader=lambda asin: new_result)
        comparison = report["comparisons"][0]

        self.assertEqual(comparison["comparison_status"], "legacy_listed_success_new_ng")
        self.assertTrue(comparison["review_required"])
        self.assertTrue(any("seller count" in note for note in comparison["notes"]))

    def test_classifies_legacy_failed_same_reason(self) -> None:
        baseline = {
            "meta": {"source": "test"},
            "summary": {"legacy_listed_success_count": 0, "legacy_failed_count": 1, "listing_success_rate": 0.0},
            "diagnostics": {"ng_only_asins": []},
            "targets": [
                {
                    "asin": "B000NG0001",
                    "legacy_status": "business_ng",
                    "legacy_reason_type": "prohibited_word",
                    "legacy_reason": "禁止キーワード(医療)",
                    "legacy_listing_completed": False,
                    "legacy_forbidden_word": "医療",
                }
            ],
        }
        new_result = {
            "listing_status": "business_ng",
            "listing_reason": "prohibited word matched: 医療",
            "matched_forbidden_words": [{"word": "医療", "field": "title"}],
            "allowed_phrase_matches": [],
            "legacy_spacing_reviews": [],
            "blocking_reasons": ["business_ng: prohibited word matched: 医療"],
        }
        report = compare_with_saved_results(baseline, result_loader=lambda asin: new_result)
        comparison = report["comparisons"][0]
        self.assertEqual(comparison["comparison_status"], "legacy_failed_new_ng_same_reason")

    def test_marks_missing_saved_input(self) -> None:
        baseline = {
            "meta": {"source": "test"},
            "summary": {"legacy_listed_success_count": 1, "legacy_failed_count": 0, "listing_success_rate": 1.0},
            "diagnostics": {"ng_only_asins": []},
            "targets": [
                {
                    "asin": "B000MISS001",
                    "legacy_status": "listed_success",
                    "legacy_reason_type": None,
                    "legacy_reason": None,
                    "legacy_listing_completed": True,
                }
            ],
        }
        report = compare_with_saved_results(baseline, result_loader=lambda asin: None)
        comparison = report["comparisons"][0]
        self.assertEqual(comparison["new_listing_status"], "not_evaluated")
        self.assertEqual(comparison["comparison_status"], "missing_saved_input")

    def test_sanitize_keeps_invalid_target_tokens_but_removes_real_secrets(self) -> None:
        payload = {
            "diagnostics": {
                "invalid_target_tokens": ["oops"],
                "ng_parse_errors": [],
            },
            "headers": {
                "authorization": "Bearer secret",
                "cookie": "session=abc",
            },
        }
        sanitized = sanitize_for_output(payload)
        self.assertEqual(sanitized["diagnostics"]["invalid_target_tokens"], ["oops"])
        self.assertEqual(sanitized["diagnostics"]["ng_parse_errors"], [])
        self.assertNotIn("authorization", sanitized["headers"])
        self.assertNotIn("cookie", sanitized["headers"])
