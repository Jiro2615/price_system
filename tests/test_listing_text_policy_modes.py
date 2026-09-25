"""Per-store opt-in, legacy equivalence, and DB-to-worker policy propagation."""
import unittest
from unittest.mock import MagicMock, patch

from scripts.listing.listing_text_policy import (
    analyze_listing_text_policy, normalize_listing_text_policy_mode,
    LEGACY_MANDATORY_FORBIDDEN_WORDS,
)
from scripts.listing.prohibited_word_masking import analyze_prohibited_word_issues
from scripts.listing.store_config import get_store_settings
from scripts.listing.models import StoreSettings


class ModeTests(unittest.TestCase):
    def test_missing_invalid_and_new_values(self):
        for value in (None, "", "legacy", "v2", True, False, [], {}):
            with self.subTest(value=value):
                self.assertEqual("legacy", normalize_listing_text_policy_mode(value))
        self.assertEqual("contextual_v1", normalize_listing_text_policy_mode("contextual_v1"))
        self.assertEqual("legacy", StoreSettings.__dataclass_fields__["listing_text_policy_mode"].default)

    def test_legacy_mode_exactly_uses_previous_analyzer_for_both_field_types(self):
        words = ["OU", "ＯＲ", "イラ", "スキン", "公式"]
        allowed = {"スキン": ["スキンケア"]}
        for text in ("10 Count ハイライト", "保湿効果で肌の乾燥を防ぐ", "ニキビを治す",
                     "メイクアップ効果で小ジワを目立たなく見せる", "スキンケア", "【公式】商品", "商品"):
            for mandatory in (True, False):
                with self.subTest(text=text, mandatory=mandatory):
                    fields = {"title" if mandatory else "attribute:説明": text}
                    expected_words = list(dict.fromkeys(words + (list(LEGACY_MANDATORY_FORBIDDEN_WORDS) if mandatory else [])))
                    expected = analyze_prohibited_word_issues(fields, expected_words, allowed)
                    actual = analyze_listing_text_policy(fields, words, allowed, brand="OU", include_legacy_mandatory=mandatory)
                    self.assertEqual(expected, actual)

    def test_new_mode_is_explicit_and_can_be_reverted(self):
        args = ({"title": "10 Count ハイライト 保湿効果"}, ["OU", "イラ"], {})
        self.assertTrue(analyze_listing_text_policy(*args)["matched_forbidden_words"])
        self.assertEqual([], analyze_listing_text_policy(*args, mode="contextual_v1")["matched_forbidden_words"])
        self.assertTrue(analyze_listing_text_policy(*args, mode="legacy")["matched_forbidden_words"])

    def test_settings_are_loaded_for_each_store_without_new_db_columns(self):
        saved = {"rakuten_1": {}, "rakuten_2": {"listing_text_policy_mode": "contextual_v1"}}
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        with patch("scripts.listing.store_config.connect_db") as connect, \
             patch("scripts.listing.store_config._get_store_cabinet_settings", side_effect=lambda code: saved[code]), \
             patch("scripts.listing.store_config.get_store_cabinet_config", return_value={}), \
             patch("scripts.listing.store_config._get_env", side_effect=lambda code, key, default="": default):
            connect.return_value.__enter__.return_value = conn
            for code, expected in (("rakuten_1", "legacy"), ("rakuten_2", "contextual_v1"), ("rakuten_1", "legacy")):
                cur.fetchone.return_value = (5, code, "test", 4, .15, False, "amount", 0, 1, 0, 300, None, None, None, None)
                settings = get_store_settings(code)
                self.assertEqual(code, settings.store_code)
                self.assertEqual(expected, settings.listing_text_policy_mode)
            saved["rakuten_2"]["listing_text_policy_mode"] = "legacy"
            cur.fetchone.return_value = (5, "rakuten_2", "test", 4, .15, False, "amount", 0, 1, 0, 300, None, None, None, None)
            self.assertEqual("legacy", get_store_settings("rakuten_2").listing_text_policy_mode)


if __name__ == "__main__":
    unittest.main()
