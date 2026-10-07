"""Shop evidence ignores sale-pack counts; reference prices do not."""
import unittest
from unittest.mock import patch

from scripts.listing import rakuten_marketplace_policy as policy


JAN = "4900000000001"


def item(shop, title, *, jan=True, price=None):
    row = {"shopCode": shop, "shopName": shop, "itemCode": shop + ":item",
           "itemName": title, "itemCaption": JAN if jan else "",
           "availability": 1, "postageFlag": 0, "taxFlag": 0}
    if price is not None:
        row.update(itemPrice=price, itemPriceMin1=price, itemPriceMax1=price)
    return row


class MarketplacePackCountTests(unittest.TestCase):
    def evidence(self, title, rows, *, jan=JAN, minimum=1, model=""):
        with patch.object(policy, "_search_items", return_value=rows):
            return policy.rakuten_marketplace_evidence(jan_code=jan, title=title,
                brand="テストブランド", model=model, minimum_shops=minimum)

    def test_jan_counts_single_two_and_four_packs_but_deduplicates_shops(self):
        title = "テストブランド シャンプー 800ml"
        rows = [item("a", title), item("b", title + " 2本セット"),
                item("c", title + "×4個"), item("c", title + " 6本")]
        evidence = self.evidence(title, rows, minimum=3)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["jan_exact_shop_count"], 3)
        self.assertEqual(evidence["search_attempts"][0]["matched_item_count"], 4)
        self.assertNotIn("pack_mismatch", evidence["search_attempts"][0]["rejected_counts"])
        self.assertFalse(evidence["pack_count_required"])

    def test_text_match_accepts_other_sale_packs_for_a_four_pack_reference(self):
        title = "テストブランド 洗顔フォーム 200g×4個"
        rows = [item("a", "テストブランド 洗顔フォーム 200g", jan=False),
                item("b", "テストブランド 洗顔フォーム 200g 2個セット", jan=False)]
        evidence = self.evidence(title, rows, jan="", minimum=2)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["text_match_shop_count"], 2)
        self.assertTrue(all("4個" not in a["query"] for a in evidence["search_attempts"]))

    def test_name_queries_ignore_pack_count_but_keep_product_capacity(self):
        queries = policy._keyword_queries(title="テストブランド 洗顔フォーム 200g×4個",
            brand="テストブランド", manufacturer="", model="", part_number="")
        self.assertTrue(all("4個" not in query and "200g" in query for query in queries))

    def test_capacity_colour_age_and_model_conflicts_are_still_rejected(self):
        cases = [
            ("テストブランド クリーム 80g", "テストブランド クリーム 100g 2個", ""),
            ("テストブランド ケース ブラック", "テストブランド ケース ホワイト 2個", ""),
            ("テストブランド キャット チキン 1歳以上 2kg", "テストブランド キャット チキン 7歳以上 2kg 2袋", ""),
            ("テストブランド 製品 MODEL-1", "テストブランド 製品 MODEL-2 2個", "MODEL-1"),
            ("テストブランド キャット チキン 2kg", "テストブランド キャット サーモン 2kg 2袋", ""),
        ]
        for reference, candidate, model in cases:
            with self.subTest(candidate=candidate):
                evidence = self.evidence(reference, [item("a", candidate, jan=False)], jan="", model=model)
                self.assertFalse(evidence["accepted"])

    def test_bread_capacity_is_retained_while_number_of_toasters_is_ignored(self):
        reference = "テストブランド 食パン2枚焼き MODEL-1"
        candidate = reference + " 2個セット"
        self.assertEqual(policy._strip_pack_quantities(candidate), reference)
        evidence = self.evidence(reference, [item("a", candidate)], model="MODEL-1")
        self.assertTrue(evidence["accepted"])
        wrong = self.evidence(reference, [item("a", "テストブランド 食パン4枚焼き MODEL-1 2個セット")])
        self.assertFalse(wrong["accepted"])

    def test_reference_minimum_never_compares_different_pack_prices(self):
        title = "テストブランド クリーム 80g"
        rows = [item("single", title, price=900), item("two", title + " 2個セット", price=600)]
        evidence = self.evidence(title, rows, minimum=2)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["reference_min_price"], 900)
        self.assertEqual(evidence["different_pack_price_items_excluded"], 1)

    def test_other_packs_can_prove_shops_without_creating_a_reference_price(self):
        title = "テストブランド クリーム 80g 4個セット"
        evidence = self.evidence(title, [item("a", "テストブランド クリーム 80g", price=100)])
        self.assertTrue(evidence["accepted"])
        self.assertIsNone(evidence["reference_min_price"])
        self.assertEqual(evidence["different_pack_price_items_excluded"], 1)

    def test_reference_prices_can_compare_matching_four_packs(self):
        title = "テストブランド クリーム 80g×4個"
        rows = [item("a", "テストブランド クリーム 80g 4個セット", price=900),
                item("b", "テストブランド クリーム 80g", price=100)]
        evidence = self.evidence(title, rows, minimum=2)
        self.assertEqual(evidence["reference_min_price"], 900)
        self.assertEqual(evidence["different_pack_price_items_excluded"], 1)

    def test_bare_multiplier_cannot_leak_into_single_pack_reference_prices(self):
        for suffix in ("×4", " (x 4)"):
            with self.subTest(suffix=suffix):
                title = "テストブランド クリーム 80g"
                candidate = title + suffix
                evidence = self.evidence(title, [item("a", candidate, price=100)])
                self.assertTrue(evidence["accepted"])
                self.assertIsNone(evidence["reference_min_price"])
                self.assertEqual(policy._strip_pack_quantities(candidate), title)

    def test_stripping_does_not_remove_dimensions_or_an_uppercase_model(self):
        for title in ("テストブランド ケース 10cm×20cm X4", "テストブランド ケース 10cm×20 cm X4", "トースター 食パン2枚 MODEL-1"):
            self.assertEqual(policy._strip_pack_quantities(title), title)
            self.assertNotIn("count", policy._variant_groups(title))

    def test_quantity_guard_remains_strict_by_default_outside_shop_evidence(self):
        candidate = item("a", "テストブランド クリーム 80g 2個")
        title = "テストブランド クリーム 80g"
        self.assertEqual(policy._variant_rejection_reason(candidate, title), "pack_mismatch")
        self.assertIsNone(policy._variant_rejection_reason(candidate, title, ignore_pack_count=True))


if __name__ == "__main__":
    unittest.main()
