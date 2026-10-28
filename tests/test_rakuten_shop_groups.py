"""Shop counting only. No HTTP, production DB, listing or inventory operations."""
import unittest
from unittest.mock import patch

from scripts.listing.rakuten_shop_groups import shop_group_evidence
from scripts.listing.rakuten_marketplace_policy import rakuten_marketplace_evidence


def item(code, name, title='キューサイ コラリッチ プレミアムリフトジェル 55g', jan='4900000000001'):
    return {'shopCode':code, 'shopName':name, 'itemName':title, 'itemCaption':jan,
            'itemCode':code+':item', 'itemPrice':5000, 'itemPriceMin1':5000, 'itemPriceMax1':5000,
            'availability':1, 'postageFlag':0, 'taxFlag':0}


def qsai_sample():
    # Actual shop names returned by the public search on 2026-10-28. Their
    # similar names are counting candidates, not verified common ownership.
    return [item('qsai','【公式】キューサイ楽天市場店'),
            item('kyusai-kenko','キューサイ健康食品販売株式会社'),
            item('kyusai-gifu','キューサイ岐阜センター'),
            item('kyusai-kantou','キューサイ青汁関東センター'),
            item('auc-genki-kai','介護ストアげんき介 楽天市場店')]


class ShopGroupTests(unittest.TestCase):
    def test_real_shop_names_five_ids_become_two_candidates(self):
        result = shop_group_evidence(qsai_sample(),[],maker_aliases=['コラリッチ','キューサイ'])
        self.assertEqual(result['raw_shop_count'],5)
        self.assertEqual(result['confirmed_shop_count'],2)
        self.assertEqual(result['merged_shop_count'],3)
        family = result['shop_groups'][0]
        self.assertEqual(family['raw_shop_count'],4)
        self.assertEqual(family['grouping_reasons'],['maker_prefix:キューサイ'])
        self.assertEqual(len(family['shop_names']),4)

    def test_generic_rakuten_official_labels_do_not_merge_unrelated_shops(self):
        rows=[item('a','さくら生活 楽天市場店'),item('b','みどり生活 楽天市場店'),
              item('c','【公式】楽天市場店'),item('d','【公式】楽天市場店'),
              item('e','健康食品楽天市場店'),item('f','健康食品楽天市場店')]
        self.assertEqual(shop_group_evidence(rows,[])['confirmed_shop_count'],6)

    def test_width_case_punctuation_and_common_suffixes_are_normalized(self):
        rows=[item('a','【公式】ＡＣＭＥ　楽天市場店'),item('b','acme本店'),
              item('c','株式会社ACME オンラインショップ')]
        result=shop_group_evidence(rows,[])
        self.assertEqual(result['confirmed_shop_count'],1)
        self.assertEqual(result['shop_groups'][0]['grouping_reasons'],['name:acme'])

    def test_same_raw_shop_with_multiple_names_and_packs_is_counted_once(self):
        rows=[item('a','キューサイ健康食品'),item('a','販売店'),item('b','キューサイ岐阜センター')]
        result=shop_group_evidence(rows,[],maker_aliases=['キューサイ'])
        self.assertEqual(result['raw_shop_count'],2)
        self.assertEqual(result['confirmed_shop_count'],1)

    def test_jan_and_text_only_members_of_one_group_are_not_double_counted(self):
        result=shop_group_evidence(qsai_sample()[:1],qsai_sample()[1:],maker_aliases=['キューサイ'])
        self.assertEqual(result['jan_exact_shop_count'],1)
        self.assertEqual(result['text_match_shop_count'],1)
        self.assertEqual(result['confirmed_shop_count'],2)

    def test_grouping_is_independent_of_query_order(self):
        rows=qsai_sample()
        for exact,text in ((rows[:1],rows[1:]),(rows[1:4],rows[:1]+rows[4:]),(rows[::-1],[])):
            result=shop_group_evidence(exact,text,maker_aliases=['キューサイ'])
            self.assertEqual(result['confirmed_shop_count'],2)
            self.assertEqual(result['jan_exact_shop_count']+result['text_match_shop_count'],2)

    def test_product_title_or_caption_mentions_do_not_group_retailers(self):
        rows=[item('a','さくら販売店'),item('b','みどり販売店'),item('c','取扱店 キューサイ等')]
        self.assertEqual(shop_group_evidence(rows,[],maker_aliases=['キューサイ'])['confirmed_shop_count'],3)

    def test_english_prefix_requires_a_word_boundary(self):
        rows=[item('a','ACME Tokyo'),item('b','ACME Osaka'),item('c','ACMEplus'),item('d','ACMEmax')]
        self.assertEqual(shop_group_evidence(rows,[],maker_aliases=['ACME'])['confirmed_shop_count'],3)

    def test_short_or_generic_makers_and_similar_names_do_not_trigger_fuzzy_match(self):
        rows=[item('a','AI東京'),item('b','AI大阪'),item('c','健康食品東京'),item('d','健康食品大阪'),
              item('e','さくら健康店'),item('f','さくら健幸店')]
        self.assertEqual(shop_group_evidence(rows,[],maker_aliases=['AI','健康食品'])['confirmed_shop_count'],6)

    def test_no_maker_data_does_not_guess_from_a_common_prefix(self):
        self.assertEqual(shop_group_evidence(qsai_sample(),[])['confirmed_shop_count'],5)

    def test_empty_names_do_not_merge_codes_and_missing_identity_is_not_counted(self):
        rows=[item('a',''),item('b',''),{'itemName':'no shop'}]
        result=shop_group_evidence(rows,[])
        self.assertEqual(result['raw_shop_count'],2)
        self.assertEqual(result['confirmed_shop_count'],2)

    def test_raw_id_fallback_and_empty_results(self):
        rows=[{'shopUrl':'https://example.invalid/a','shopName':''}, {'shopName':'さくら生活'}]
        self.assertEqual(shop_group_evidence(rows,[])['confirmed_shop_count'],2)
        self.assertEqual(shop_group_evidence([],[])['confirmed_shop_count'],0)

    def test_unmerged_shops_do_not_bloat_saved_audit_groups(self):
        rows=[item('retailer-'+str(i),'独立店舗'+str(i)) for i in range(150)]
        result=shop_group_evidence(rows,[])
        self.assertEqual(result['confirmed_shop_count'],150)
        self.assertEqual(result['shop_groups'],[])


class EvidenceGroupingTests(unittest.TestCase):
    def test_raw_five_shops_no_longer_pass_five_shop_threshold(self):
        rows=qsai_sample()
        with patch('scripts.listing.rakuten_marketplace_policy._search_items', return_value=rows):
            result=rakuten_marketplace_evidence(jan_code='4900000000001',title=rows[0]['itemName'],
                brand='コラリッチ',manufacturer='キューサイ',minimum_shops=5)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['raw_shop_count'],5)
        self.assertEqual(result['confirmed_shop_count'],2)
        self.assertGreater(len(result['search_attempts']),1)

    def test_early_stop_waits_for_enough_groups_and_keeps_original_price_offers(self):
        rows=qsai_sample(); rows[1]['itemPrice']=4000; rows[1]['itemPriceMin1']=4000; rows[1]['itemPriceMax1']=4000
        extras=[item('retailer-'+str(i),'独立した店舗'+str(i)) for i in range(4)]
        with patch('scripts.listing.rakuten_marketplace_policy._keyword_queries', return_value=['q1','q2']), \
             patch('scripts.listing.rakuten_marketplace_policy._search_items', side_effect=[rows,[],extras]) as search:
            result=rakuten_marketplace_evidence(jan_code='4900000000001',title=rows[0]['itemName'],manufacturer='キューサイ',minimum_shops=5)
        self.assertEqual(search.call_count,3)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['confirmed_shop_count'],6)
        self.assertEqual(result['raw_shop_count'],9)
        self.assertEqual(result['reference_min_price'],4000)

    def test_jan_early_success_uses_group_counts(self):
        rows=qsai_sample()
        with patch('scripts.listing.rakuten_marketplace_policy._search_items', return_value=rows) as search:
            result=rakuten_marketplace_evidence(jan_code='4900000000001',title=rows[0]['itemName'],manufacturer='キューサイ',minimum_shops=2)
        self.assertEqual(search.call_count,1)
        self.assertTrue(result['accepted']); self.assertEqual(result['confirmed_shop_count'],2)

    def test_no_product_identity_return_still_has_group_details(self):
        with patch('scripts.listing.rakuten_marketplace_policy._search_items',return_value=[]):
            result=rakuten_marketplace_evidence(jan_code='',title='',manufacturer='キューサイ',minimum_shops=5)
        self.assertFalse(result['accepted']); self.assertEqual(result['raw_shop_count'],0)
        self.assertEqual(result['shop_groups'],[])


if __name__ == '__main__':
    unittest.main()
