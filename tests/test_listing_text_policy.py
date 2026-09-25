from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from scripts.listing.listing_text_policy import (
    POLICY_VERSION, WORD_OR_BRAND_TERMS, analyze_listing_text_policy,
    advertising_expression_matches,
)
from scripts.listing.listing_evaluator import evaluate_listing, _is_quasi_drug_allowed_match
from scripts.listing.models import AmazonCheckResult, KeepaProductData, ListingCommonSettings, MasterData, StoreSettings


class TextPolicyTests(unittest.TestCase):
    def analyze(self, text: str, *, brand: str = "", words=None):
        return analyze_listing_text_policy(
            {"title": text}, list(WORD_OR_BRAND_TERMS) if words is None else words,
            {}, brand=brand,
        )["matched_forbidden_words"]

    def test_brand_substrings_pass(self):
        for text in ("10 Count", "Silky Touch", "Corn Plane", "Performance Tool",
                     "ハイライト", "スリーク", "スリム", "スキンケア", "スカルプケア",
                     "Ｃｏｕｎｔ", "カラースキン", "OUVER", "ORANGE"):
            with self.subTest(text=text):
                self.assertEqual([], self.analyze(text))

    def test_standalone_words_block(self):
        for word, text in (("OU", "OU 商品"), ("OU", "[ou]"), ("OU", "ＯＵ"),
                           ("ＯＲ", "(OR) shampoo"), ("イラ", "【イラ】商品"),
                           ("スリー", "スリー リップ"), ("スキン", "スキン 商品"),
                           ("スカルプ", "スカルプ 商品")):
            with self.subTest(text=text):
                matches = self.analyze(text)
                self.assertEqual(word, matches[0]["word"])
                self.assertEqual("whole_word", matches[0]["rule_kind"])

    def test_brand_field_is_checked_when_title_has_no_brand(self):
        for brand in ("ＯＵ", "OR", "ila(イラ)", "スリー", "スキン", "スカルプ"):
            with self.subTest(brand=brand):
                matches = self.analyze("商品", brand=brand)
                self.assertEqual("brand", matches[0]["field"])
                self.assertEqual("brand", matches[0]["rule_kind"])
                self.assertEqual(POLICY_VERSION, matches[0]["policy_version"])

    def test_unrelated_brands_and_disabled_keywords_do_not_block(self):
        self.assertEqual([], self.analyze("商品", brand="Count ハイライト ライラ"))
        self.assertEqual([], self.analyze("OU 商品", brand="OU", words=[]))

    def test_other_master_keywords_stay_contains(self):
        self.assertEqual("公式", self.analyze("これは公式商品", words=["公式"])[0]["word"])

    def test_brand_uses_long_vowel_mark(self):
        self.assertEqual([], self.analyze("スリム"))
        self.assertEqual("スリー", self.analyze("スリー")[0]["word"])

    def test_requested_allowed_expressions_pass(self):
        for text in (
            "保湿効果", "肌の乾燥を防ぐ", "メイクアップ効果で小ジワを目立たなく見せる",
            "乾燥による小ジワを目立たなくする", "ニキビを防ぐ", "潤滑効果を強化",
            "保温効果", "静電気を防ぐ", "操作性を改善", "寝癖を治す", "衝撃予防",
        ):
            with self.subTest(text=text):
                self.assertEqual([], self.analyze(text, words=["効果", "効能", "改善", "防ぐ", "予防", "治す"]))

    def test_explicit_advertising_expressions_block_without_master_entries(self):
        for text in ("ニキビを治す", "にきびが治る", "シミを消す", "シワが消える",
                     "病気を治す", "糖尿病を改善", "血液サラサラ", "脂肪燃焼効果",
                     "絶対に効果がある", "100%効く", "ニ キ ビ を 治 す", "治・癒"):
            with self.subTest(text=text):
                matches = self.analyze(text, words=[])
                self.assertTrue(matches)
                self.assertEqual("advertising_expression", matches[0]["rule_kind"])

    def test_explicit_makeup_visual_qualifier(self):
        self.assertEqual([], self.analyze("メイクアップ効果でシミが消えるように見せる"))
        self.assertTrue(self.analyze("メイクアップ効果。シミを消す"))
        self.assertTrue(self.analyze("メイクアップ用品でシミを消す"))
        self.assertTrue(self.analyze("メイクアップ効果で小ジワを目立たなく見せる。ニキビを治す"))

    def test_material_stain_removal_is_not_a_cosmetic_claim(self):
        for text in ("衣類のシミを消す", "シャツのシワをなくす", "カーペットについたシミを除去"):
            with self.subTest(text=text):
                self.assertEqual([], self.analyze(text))
        self.assertTrue(self.analyze("衣類のシミを消す。肌のシミを消す"))
        self.assertTrue(self.analyze("肌のシミを消す"))

    def test_negation_is_local_to_claim(self):
        for text in ("ニキビを治す効果はありません", "シミを消すものではありません"):
            with self.subTest(text=text):
                self.assertEqual([], self.analyze(text))
        self.assertTrue(self.analyze("ニキビを治す。医薬品ではありません"))
        self.assertTrue(self.analyze("シミを消すものではありません。病気を治す"))

    def test_allowed_phrase_never_masks_explicit_claim(self):
        result = analyze_listing_text_policy(
            {"title": "ニキビを治す"}, ["治す"], {"治す": ["ニキビを治す"]},
        )
        self.assertTrue(result["matched_forbidden_words"])

    def test_no_input_text_is_rewritten(self):
        fields = {"title": "保湿<b>効果</b> &amp; 潤滑効果", "attribute:説明": "シミを消す"}
        original = dict(fields)
        matches = advertising_expression_matches(fields)
        self.assertEqual(fields, original)
        self.assertEqual("attribute:説明", matches[0]["field"])

    def test_product_category_evidence_does_not_excuse_explicit_claim(self):
        match = self.analyze("ニキビを治す")[0]
        self.assertFalse(_is_quasi_drug_allowed_match(match, {"product_category": "医薬部外品"}))


class EvaluatorTextPolicyTests(unittest.TestCase):
    def setUp(self):
        self.asin = "B000TEST01"
        self.master = MasterData(
            blacklist=set(), kako_ng={}, replacements=[], prohibited_words_rakuten=list(WORD_OR_BRAND_TERMS),
            prohibited_words_other=[], listed_asins={}, category_map={10219786051: 101737},
            attribute_definitions={101737: ["ブランド名", "メーカー型番"]},
        )
        self.store = StoreSettings(
            store_id=5, store_code="rakuten_2", store_name="test", max_stock=4, fee_rate=0.15,
            use_amazon_point=False, profit_mode="amount", profit_rate=0, profit_amount=300,
            fixed_cost=0, rounding_unit=1, normal_delivery_date_id=1, back_order_delivery_date_id=1,
            normal_delivery_time_id=1, back_order_delivery_time_id=1, ship_from_ids=["1"],
        )
        self.amazon = AmazonCheckResult(
            requested_asin=self.asin, page_asin=self.asin, title="10 Count ハイライト",
            amazon_price=2000, available_qty=9, gift_available=True, shipping_status="next day shipping",
        )
        self.keepa = KeepaProductData(
            asin=self.asin, title=self.amazon.title, brand="テストブランド", model="MODEL-1",
            ean="1234567890123", images_csv="abc", category_id=10219786051,
            description="潤滑効果を強化", avg90_new_offer_count=4.2, is_adult=False,
        )
        self.no_db = patch("psycopg.connect", side_effect=AssertionError("Unexpected DB access"))
        self.no_db.start()
        self.addCleanup(self.no_db.stop)
        market_patch = patch("scripts.listing.listing_evaluator.rakuten_listing_count_for_jan", return_value=99)
        self.market = market_patch.start()
        self.addCleanup(market_patch.stop)

    def evaluate(self, **kwargs):
        return evaluate_listing(
            asin=self.asin, amazon_result=kwargs.pop("amazon_result", self.amazon),
            keepa_result=kwargs.pop("keepa_result", self.keepa), master_data=self.master,
            store_settings=self.store, management_number="20260101010101_187_test",
            common_settings=ListingCommonSettings(min_avg90_new_offer_count=3.5), **kwargs,
        )

    def test_real_flow_passes_substrings_and_functional_effect(self):
        result = self.evaluate()
        self.assertEqual("eligible", result.listing_status, result.listing_reason)
        self.assertEqual(self.amazon.title, result.title)
        self.assertIn("潤滑効果", result.description_pc)

    def test_true_brand_cannot_use_marketplace_popularity_exception(self):
        result = self.evaluate(keepa_result=replace(self.keepa, brand="OU"))
        self.assertEqual("business_ng", result.listing_status)
        self.assertEqual("brand", result.matched_forbidden_words[0]["field"])
        self.market.assert_not_called()

    def test_explicit_claim_cannot_use_marketplace_popularity_exception(self):
        result = self.evaluate(keepa_result=replace(self.keepa, description="ニキビを治す"))
        self.assertEqual("business_ng", result.listing_status)
        self.assertTrue(result.matched_forbidden_words)
        self.market.assert_not_called()

    def test_attributes_use_same_policy(self):
        result = self.evaluate(keepa_result=replace(self.keepa, model="ニキビを治す"))
        self.assertEqual("business_ng", result.listing_status)
        self.assertTrue(any(str(match["field"]).startswith("attribute:") for match in result.matched_forbidden_words))

    def test_existing_past_ng_is_not_silently_deleted_or_ignored(self):
        self.master.kako_ng[self.asin] = "prohibited word matched: 効果"
        self.assertIn("過去NG", self.evaluate().listing_reason)

    def test_blacklist_and_seller_checks_are_unchanged(self):
        self.master.blacklist.add(self.asin)
        self.assertEqual("business_ng", self.evaluate().listing_status)
        self.master.blacklist.clear()
        self.assertEqual("business_ng", self.evaluate(keepa_result=replace(self.keepa, avg90_new_offer_count=1)).listing_status)


if __name__ == "__main__":
    unittest.main()
