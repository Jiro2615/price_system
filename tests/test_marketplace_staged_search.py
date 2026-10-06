"""Staged search must improve recall without changing the SKU/offer guards."""
import unittest
from unittest.mock import patch

from scripts.listing import rakuten_marketplace_policy as policy


def item(shop, title, caption=""):
    return {"shopCode": shop, "shopName": shop, "itemCode": shop + ":item", "itemName": title,
            "itemCaption": caption, "availability": 1, "postageFlag": 0}


class StagedSearchTests(unittest.TestCase):
    def test_bilingual_maker_is_not_one_literal_query(self):
        queries = policy._keyword_queries(title="象印マホービン(ZOJIRUSHI) トースター EQ-AM22-BA ブラック",
            brand="象印マホービン(ZOJIRUSHI)", manufacturer="象印マホービン", model="EQ-AM22-BA", part_number="")
        self.assertEqual(queries[0], "象印 EQ-AM22-BA")
        self.assertIn("EQ-AM22-BA", queries)
        self.assertFalse(any("(ZOJIRUSHI)" in q for q in queries))
        self.assertLessEqual(len(queries), policy.MAX_TEXT_SEARCHES)

    def test_supplier_only_number_is_not_required_as_a_search_keyword(self):
        queries = policy._keyword_queries(title="ピュリナ ワン キャット チキン 1歳以上 2kg", brand="ピュリナ ワン",
            manufacturer="ネスレ", model="1019603", part_number="")
        self.assertTrue(queries)
        self.assertFalse(any("1019603" in q for q in queries))
        self.assertTrue(any("チキン" in q and "2kg" in q for q in queries))

    def test_shortened_maker_with_exact_model_recovers_seven_shops(self):
        title = "象印マホービン(ZOJIRUSHI) オーブントースター こんがり倶楽部 食パン2枚焼き EQ-AM22-BA ブラック"
        rows = [item(str(i), "象印 オーブントースター こんがり倶楽部 EQ-AM22-BA ブラック") for i in range(7)]
        with patch.object(policy, "_search_items", side_effect=[[], rows]) as search:
            evidence = policy.rakuten_marketplace_evidence(jan_code="4900000000001", title=title,
                brand="象印マホービン(ZOJIRUSHI)", manufacturer="象印マホービン", model="EQ-AM22-BA", minimum_shops=7)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["confirmed_shop_count"], 7)
        self.assertEqual(search.call_count, 2)
        self.assertEqual(evidence["search_attempts"][-1]["query"], "象印 EQ-AM22-BA")

    def test_fallback_continues_after_nonmatching_hits_and_deduplicates_shops(self):
        title = "テストブランド クリーム MODEL-1 80g"
        responses = [[], [item("a", "テストブランド クリーム MODEL-2 80g")],
                     [item("a", title), item("a", title), item("b", title)]]
        with patch.object(policy, "_search_items", side_effect=responses):
            evidence = policy.rakuten_marketplace_evidence(jan_code="4900000000001", title=title,
                brand="テストブランド", model="MODEL-1", minimum_shops=2)
        self.assertEqual(evidence["confirmed_shop_count"], 2)
        self.assertEqual(evidence["search_attempts"][1]["raw_result_count"], 1)
        self.assertEqual(evidence["search_attempts"][1]["matched_item_count"], 0)
        self.assertEqual(evidence["search_attempts"][1]["rejected_counts"]["identity_not_proven"], 1)

    def test_bread_capacity_is_not_number_of_toasters(self):
        self.assertNotIn("count", policy._variant_groups("食パン2枚焼き"))
        self.assertNotIn("count", policy._variant_groups("トースター 食パン2枚"))
        self.assertIn("count", policy._variant_groups("食パン2枚セット"))
        self.assertFalse(policy._candidate_matches_variant(item("a", "食パン4枚焼き"), "食パン2枚焼き"))
        self.assertFalse(policy._candidate_matches_variant(item("a", "食パン2枚焼き 2個セット"), "食パン2枚焼き"))

    def test_age_flavour_capacity_and_colour_conflicts_remain_blocked(self):
        reference = "テストブランド キャット チキン 1歳以上 2kg"
        for candidate in ("テストブランド キャット チキン 7歳以上 2kg", "テストブランド キャット サーモン 1歳以上 2kg",
                          "テストブランド キャット チキン 1歳以上 1kg", "テストブランド キャット チキン 1歳以上 2kg 2袋"):
            self.assertFalse(policy._candidate_matches_variant(item("a", candidate), reference))
        self.assertFalse(policy._candidate_matches_variant(item("a", "トースター MODEL-1 ホワイト"), "トースター MODEL-1 ブラック"))
        self.assertFalse(policy._candidate_matches_variant(item("a", "チキン 1歳まで 2kg"), "チキン 1歳以上 2kg"))

    def test_internal_model_missing_from_title_needs_a_strong_name_match(self):
        title = "テストブランド キャット チキン 1歳以上 2kg"
        self.assertTrue(policy._is_high_confidence_text_match(item("a", title), title=title,
            brand="テストブランド", manufacturer="", model="ND387", part_number=""))
        self.assertFalse(policy._is_high_confidence_text_match(item("a", title.replace("チキン", "サーモン")), title=title,
            brand="テストブランド", manufacturer="", model="ND387", part_number=""))

    def test_search_queries_stay_within_utf8_byte_limit(self):
        queries = policy._keyword_queries(title="商品名" * 100 + " 80g", brand="テストブランド",
            manufacturer="", model="", part_number="")
        self.assertTrue(all(len(q.encode("utf-8")) <= 128 for q in queries))


if __name__ == "__main__":
    unittest.main()
