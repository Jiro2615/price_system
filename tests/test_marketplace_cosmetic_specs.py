"""Cosmetic performance is not a model; shade and known specification conflicts remain guards."""
import unittest
from unittest.mock import patch

from scripts.listing import rakuten_marketplace_policy as policy


JAN = "4580374260522"
TITLE = "リップスボーイ フェイスジェル 25g BBクリーム SPF26 PA++ 自然な肌色"


def item(title, caption=""):
    return {"itemName": title, "itemCaption": caption, "shopCode": "test", "shopName": "テスト店",
            "itemCode": "test:item", "availability": 1, "postageFlag": 0}


class CosmeticSpecificationTests(unittest.TestCase):
    def match(self, candidate, *, title=TITLE, part="TYU-987"):
        return policy._is_high_confidence_text_match(item(candidate), title=title,
            brand="LIPPS BOY", manufacturer="株式会社リップス", model="", part_number=part,
            ignore_pack_count=True)

    def evidence(self, candidate, *, jan="", title=TITLE):
        with patch.object(policy, "_search_items", return_value=[item(candidate, JAN if jan else "")]):
            return policy.rakuten_marketplace_evidence(jan_code=jan, title=title,
                brand="LIPPS BOY", manufacturer="株式会社リップス", part_number="TYU-987", minimum_shops=1)

    def test_spf_performance_labels_are_not_model_tokens(self):
        for label in ("SPF26", "SPF50+", "SPF-50", "ＳＰＦ５０＋", "SPF26/PA++", "SPF26PA++", "SPF50PA++++"):
            with self.subTest(label=label):
                self.assertEqual(policy._model_tokens(label), set())

    def test_real_model_tokens_are_preserved(self):
        self.assertEqual(policy._model_tokens("SPF26 TYU-987 MODEL-1 EQ-AM22-BA"),
                         {"tyu987", "model1", "eqam22ba"})

    def test_missing_supplier_part_number_can_use_a_strong_title_match(self):
        self.assertTrue(self.match(TITLE))
        self.assertTrue(self.evidence(TITLE)["accepted"])

    def test_exact_supplier_model_remains_accepted(self):
        self.assertTrue(self.match(TITLE + " TYU-987"))

    def test_different_real_model_is_not_accepted(self):
        self.assertFalse(self.match(TITLE + " TYU-988"))
        self.assertFalse(self.evidence(TITLE + " TYU-988")["accepted"])

    def test_different_capacity_is_not_accepted(self):
        self.assertFalse(self.evidence(TITLE.replace("25g", "50g"))["accepted"])

    def test_natural_and_light_skin_shades_are_not_interchangeable(self):
        candidate = TITLE.replace("自然な肌色", "明るい肌色")
        self.assertFalse(self.match(candidate))
        self.assertFalse(self.evidence(candidate)["accepted"])
        self.assertEqual(policy._variant_rejection_reason(item(candidate), TITLE), "shade_mismatch")

    def test_unstated_shade_cannot_pass_a_text_only_match(self):
        self.assertFalse(self.match(TITLE.replace(" 自然な肌色", "")))

    def test_title_enumerating_both_shades_is_not_exact_shade_evidence(self):
        self.assertFalse(self.match(TITLE + "・明るい肌色"))
        self.assertFalse(self.evidence(TITLE + "・明るい肌色")["accepted"])

    def test_performance_conflicts_are_not_model_conflicts_but_are_rejected(self):
        for candidate in (TITLE.replace("SPF26", "SPF50"), TITLE.replace("PA++", "PA++++")):
            with self.subTest(candidate=candidate):
                self.assertEqual(policy._model_tokens(candidate), set())
                self.assertEqual(policy._variant_rejection_reason(item(candidate), TITLE), "sun_protection_mismatch")
                self.assertFalse(self.match(candidate))
                self.assertFalse(self.evidence(candidate)["accepted"])

    def test_spf_plus_and_pa_grades_are_normalized_separately(self):
        self.assertEqual(policy._sun_protection("ＳＰＦ５０＋／ＰＡ＋＋＋＋"), {"spf": {"50+"}, "pa": {"++++"}})
        self.assertEqual(policy._sun_protection("SPF26PA++"), {"spf": {"26"}, "pa": {"++"}})
        self.assertEqual(policy._sun_protection("SPF-26 PA++"), {"spf": {"26"}, "pa": {"++"}})

    def test_jan_does_not_rescue_known_wrong_shade_or_performance(self):
        for candidate in (TITLE.replace("自然な肌色", "明るい肌色"), TITLE.replace("SPF26", "SPF50")):
            with self.subTest(candidate=candidate):
                self.assertFalse(self.evidence(candidate, jan=JAN)["accepted"])

    def test_weak_name_match_does_not_pass_just_because_spf_was_removed(self):
        self.assertFalse(self.match("リップスボーイ フェイスパウダー 25g SPF26 PA++ 自然な肌色"))


if __name__ == "__main__":
    unittest.main()
