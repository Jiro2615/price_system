from __future__ import annotations

import unittest
from unittest import mock

from scripts.listing.common_settings import (
    DEFAULT_MIN_AVG90_NEW_OFFER_COUNT,
    ENV_MIN_AVG90_NEW_OFFER_COUNT,
    LEGACY_ENV_MIN_AVG90_SELLERS,
    build_seller_count_evaluation,
    load_listing_common_settings,
    resolve_min_avg90_new_offer_count,
)


class ListingCommonSettingsTests(unittest.TestCase):
    def test_reads_new_setting_name(self) -> None:
        settings, warnings = load_listing_common_settings({"min_avg90_new_offer_count": 4})
        self.assertEqual(settings.min_avg90_new_offer_count, 4.0)
        self.assertEqual(warnings, [])

    def test_reads_legacy_setting_name_as_compatibility(self) -> None:
        settings, warnings = load_listing_common_settings({"min_avg90_sellers": "3.5"})
        self.assertEqual(settings.min_avg90_new_offer_count, 3.5)
        self.assertEqual(warnings, [])

    def test_new_setting_takes_priority_over_legacy_setting(self) -> None:
        settings, warnings = load_listing_common_settings(
            {"min_avg90_new_offer_count": 4.2, "min_avg90_sellers": 9.9}
        )
        self.assertEqual(settings.min_avg90_new_offer_count, 4.2)
        self.assertEqual(warnings, [])

    def test_numeric_string_is_accepted(self) -> None:
        value, warnings = resolve_min_avg90_new_offer_count({"min_avg90_new_offer_count": "3.5"})
        self.assertEqual(value, 3.5)
        self.assertEqual(warnings, [])

    def test_invalid_string_falls_back_to_default(self) -> None:
        value, warnings = resolve_min_avg90_new_offer_count({"min_avg90_new_offer_count": "abc"})
        self.assertEqual(value, DEFAULT_MIN_AVG90_NEW_OFFER_COUNT)
        self.assertEqual(len(warnings), 1)

    def test_negative_and_non_finite_values_fall_back_to_default(self) -> None:
        for raw in ("-1", "NaN", "inf", ""):
            with self.subTest(raw=raw):
                value, warnings = resolve_min_avg90_new_offer_count({"min_avg90_new_offer_count": raw})
                self.assertEqual(value, DEFAULT_MIN_AVG90_NEW_OFFER_COUNT)
                self.assertEqual(len(warnings), 1)

    def test_common_env_is_preferred_over_legacy_env(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {
                ENV_MIN_AVG90_NEW_OFFER_COUNT: "4.0",
                LEGACY_ENV_MIN_AVG90_SELLERS: "9.0",
            },
            clear=False,
        ):
            settings, warnings = load_listing_common_settings()
        self.assertEqual(settings.min_avg90_new_offer_count, 4.0)
        self.assertEqual(warnings, [])

    def test_seller_count_evaluation_handles_null_as_non_blocking(self) -> None:
        evaluation = build_seller_count_evaluation(actual_value=None, minimum_value=3.5)
        self.assertTrue(evaluation["passed"])
        self.assertIsNone(evaluation["actual_value"])


if __name__ == "__main__":
    unittest.main()
