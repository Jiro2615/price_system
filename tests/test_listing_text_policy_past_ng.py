import unittest
from unittest.mock import MagicMock, patch

from scripts.preview_listing_text_policy_past_ng import is_legacy_policy_recheck_candidate, preview
from scripts.listing.listing_text_policy import POLICY_VERSION


class PastNgPolicyPreviewTests(unittest.TestCase):
    def row(self, **kwargs):
        return {
            "id": 1, "asin": "B000TEST01", "source": "listing_rule_auto", "enabled": True,
            "reason": "prohibited word matched: 効果", "matched_rules": [{"word": "効果"}],
            **kwargs,
        }

    def test_legacy_changed_rules_are_candidates_not_auto_eligible(self):
        for word in ("効果", "防ぐ", "OU", "ＯＲ", "イラ"):
            with self.subTest(word=word):
                self.assertTrue(is_legacy_policy_recheck_candidate(self.row(
                    reason=f"prohibited word matched: {word}", matched_rules=[{"word": word}],
                )))

    def test_manual_unrelated_mixed_and_incomplete_records_stay_excluded(self):
        for updates in (
            {"source": "manual"}, {"source": "legacy_import"}, {"enabled": False},
            {"matched_rules": []}, {"matched_rules": None}, {"matched_rules": ["効果"]},
            {"matched_rules": [{"word": "効果"}, {"word": "公式"}]},
            {"reason": "別のNG理由"},
            {"matched_rules": [{"word": "効果", "policy_version": POLICY_VERSION}]},
            {"matched_rules": [{"word": "効果", "policy_version": "future_version"}]},
        ):
            with self.subTest(updates=updates):
                self.assertFalse(is_legacy_policy_recheck_candidate(self.row(**updates)))

    @patch("scripts.preview_listing_text_policy_past_ng.connect_db")
    def test_preview_enforces_readonly_and_never_updates(self, connect):
        conn = MagicMock()
        connect.return_value.__enter__.return_value = conn
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = {"id": 5}
        cur.fetchmany.side_effect = [[self.row()], []]
        report = preview("rakuten_2")
        self.assertIn("default_transaction_read_only=on", connect.call_args.kwargs["options"])
        self.assertEqual(1, report["recheck_candidate_count"])
        self.assertFalse(report["past_ng_changed"])
        self.assertTrue(all(call.args[0].lstrip().startswith("SELECT") for call in cur.execute.call_args_list))
        conn.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
