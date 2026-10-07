"""Exact product-name cores improve recall without relaxing known SKU guards."""
import unittest
from unittest.mock import patch

from scripts.listing import rakuten_marketplace_policy as policy


TITLE = "ホルコン メディカルシャンプー 800ml 医薬部外品"
MAKER = "昭和化学"
JAN = "4905385030115"


def item(shop, name, *, caption=""):
    return {"shopCode": shop, "shopName": shop, "itemCode": shop + ":saved", "itemName": name,
            "itemCaption": caption, "availability": 1, "postageFlag": 1}


class ProductNameCoreTests(unittest.TestCase):
    def match(self, name, *, caption="", title=TITLE, model=""):
        return policy._is_high_confidence_text_match(item("a", name, caption=caption), title=title,
            brand=MAKER, manufacturer=MAKER, model=model, part_number="", ignore_pack_count=True)

    def evidence(self, rows, *, title=TITLE, jan="", minimum=1):
        with patch.object(policy, "_search_items", return_value=rows):
            return policy.rakuten_marketplace_evidence(jan_code=jan, title=title, brand=MAKER,
                manufacturer=MAKER, minimum_shops=minimum)

    def test_short_query_excludes_maker_and_regulatory_label(self):
        queries = policy._keyword_queries(title=TITLE, brand=MAKER, manufacturer=MAKER, model="", part_number="")
        self.assertEqual(queries[0], "昭和化学 ホルコン メディカルシャンプー 800ml 医薬部外品")
        self.assertIn("ホルコン メディカルシャンプー 800ml", queries)
        self.assertLessEqual(len(queries), 4)

    def test_model_searches_still_leave_room_for_one_short_query(self):
        queries = policy._keyword_queries(title=TITLE + " MODEL-1", brand=MAKER, manufacturer=MAKER,
            model="MODEL-1", part_number="")
        self.assertEqual(queries[:2], ["昭和化学 MODEL-1", "MODEL-1"])
        self.assertIn("ホルコン メディカルシャンプー 800ml", queries)
        self.assertLessEqual(len(queries), 4)

    def test_short_query_keeps_capacity_with_a_very_long_product_name(self):
        queries = policy._keyword_queries(title="商品名" * 100 + " 800ml 医薬部外品", brand=MAKER,
            manufacturer=MAKER, model="", part_number="")
        self.assertTrue(any(query.endswith("800ml") for query in queries))
        self.assertTrue(all(len(query.encode("utf-8")) <= 128 for query in queries))

    def test_short_stage_is_used_only_when_precise_stage_is_insufficient(self):
        def results(query, timeout, **kwargs):
            return [item("a", TITLE), item("b", TITLE)] if query == "ホルコン メディカルシャンプー 800ml" else []
        with patch.object(policy, "_search_items", side_effect=results) as search:
            evidence = policy.rakuten_marketplace_evidence(jan_code="", title=TITLE,
                brand=MAKER, manufacturer=MAKER, minimum_shops=2)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(search.call_count, 2)
        self.assertEqual(evidence["search_attempts"][-1]["core_name_match_count"], 2)

    def test_long_promotional_tail_does_not_reduce_an_exact_name_core(self):
        name = "【2本セット】送料無料 " + TITLE + " フケ かゆみ 頭皮ケア 介護 美容院 サロン専売品 人気 おすすめ"
        self.assertTrue(self.match(name))
        self.assertTrue(self.evidence([item("a", name)])["accepted"])

    def test_maker_omission_requires_long_multicomponent_name_and_capacity(self):
        self.assertTrue(self.match(TITLE))
        self.assertFalse(self.match("クリーム 800ml", title="クリーム 800ml"))
        self.assertFalse(self.match("medical shampoo 800ml", title="medical shampoo 800ml"))
        self.assertFalse(self.match("モイストリッチクリーム 800ml", title="モイストリッチクリーム 800ml"))

    def test_no_manufacturer_metadata_is_not_silently_rescued(self):
        self.assertFalse(policy._is_high_confidence_text_match(item("a", TITLE), title=TITLE,
            brand="", manufacturer="", model="", part_number="", ignore_pack_count=True))

    def test_capacity_and_product_names_must_match_exactly(self):
        for name in (TITLE.replace("800ml", "700ml"), TITLE.replace("シャンプー", "ボディソープ"),
                     TITLE.replace("メディカル", "トリートメント"), TITLE.replace("ホルコン", "他ブランド")):
            with self.subTest(name=name):
                self.assertFalse(self.match(name))
                self.assertFalse(self.match(name, caption=MAKER))
                self.assertFalse(self.evidence([item("a", name)])["accepted"])

    def test_accessories_compatibles_bundles_and_editions_do_not_pass(self):
        for name in (TITLE + "用空ボトル", TITLE + " 専用ポンプ", TITLE + " 互換品", TITLE + " EX",
                     TITLE.replace("800ml", "800ml用取付キット"),
                     TITLE.replace("800ml", "800ml+リンス800ml")):
            with self.subTest(name=name):
                self.assertFalse(self.match(name))
                self.assertFalse(self.evidence([item("a", name)], jan=JAN)["accepted"])

    def test_core_matching_still_rejects_real_model_contradiction(self):
        self.assertFalse(self.match(TITLE + " MODEL-2", title=TITLE + " MODEL-1", model="MODEL-1"))

    def test_medical_modifier_is_not_removed_without_both_regulatory_labels(self):
        self.assertTrue(self.match(TITLE.replace("メディカル", "薬用メディカル")))
        self.assertFalse(self.match("ホルコン 薬用メディカルシャンプー 800ml",
            title="ホルコン メディカルシャンプー 800ml"))
        self.assertFalse(self.match("ホルコン 薬用メディカルシャンプー 800ml", caption=MAKER,
            title="ホルコン メディカルシャンプー 800ml"))

    def test_valid_jan_query_candidates_are_reused_as_text_not_as_jan_proof(self):
        rows = [item("a", TITLE), item("b", "【3本セット】送料無料 " + TITLE + " おすすめ 人気")]
        with patch.object(policy, "_search_items", return_value=rows) as search:
            evidence = policy.rakuten_marketplace_evidence(jan_code=JAN, title=TITLE,
                brand=MAKER, manufacturer=MAKER, minimum_shops=2)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["jan_exact_shop_count"], 0)
        self.assertEqual(evidence["text_match_shop_count"], 2)
        self.assertEqual(evidence["search_attempts"][0]["core_name_match_count"], 2)
        search.assert_called_once_with(JAN, 15.0, postage_included=False)

    def test_search_hit_without_jan_or_name_identity_is_not_evidence(self):
        self.assertFalse(self.evidence([item("a", "別メーカー シャンプー 800ml")], jan=JAN)["accepted"])

    def test_duplicate_shop_across_jan_and_text_is_counted_once(self):
        rows = [item("a", TITLE, caption=JAN), item("a", TITLE), item("b", TITLE)]
        evidence = self.evidence(rows, jan=JAN, minimum=2)
        self.assertEqual(evidence["confirmed_shop_count"], 2)
        self.assertEqual(evidence["jan_exact_shop_count"], 1)
        self.assertEqual(evidence["text_match_shop_count"], 1)

    def test_clear_promotional_blocks_are_removed_but_specs_are_not(self):
        name = "【クーポン10%OFF】ホルコン 【医薬部外品】シャンプー 800ml 【ブラック】 【MODEL-2】"
        clean = policy._strip_promotional_text(name)
        self.assertNotIn("クーポン", clean)
        for value in ("医薬部外品", "ブラック", "MODEL-2", "800ml"):
            self.assertIn(value, clean)

    def test_unknown_capacity_does_not_create_a_core_match(self):
        self.assertFalse(self.match(TITLE.replace(" 800ml", "")))


if __name__ == "__main__":
    unittest.main()
