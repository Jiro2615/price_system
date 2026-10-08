"""Ordering tests with live DB/network/writes forbidden."""
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from scripts.listing import prepare_service as service
from scripts.listing import listing_evaluator as evaluator
from scripts.listing.models import EvaluationResult, ListingCommonSettings
from tests import test_rakuten_listing_payload as fixture_module


class OrderingTests(unittest.TestCase):
    def setUp(self):
        fixture=fixture_module.RakutenListingPhase1Tests();fixture.setUp()
        fixture.keepa.avg90_new_offer_count=4.5
        self.fixture=fixture
        self.request=service.PrepareListingRequest(asin="B000TEST01",store_code="rakuten_1",master_dir=Path("unused"),dry_run=True)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("psycopg.connect",side_effect=AssertionError("Live DB forbidden")))
        self.stack.enter_context(patch("requests.sessions.Session.request",side_effect=AssertionError("Live HTTP forbidden")))
        self.stack.enter_context(patch("urllib.request.OpenerDirector.open",side_effect=AssertionError("Live urllib forbidden")))
        self.master=self.stack.enter_context(patch.object(service,"load_preparation_masters",return_value=fixture.master))
        self.overrides=self.stack.enter_context(patch.object(service,"apply_asin_master_overrides",side_effect=lambda master,*args:master))
        self.options={"store_settings_loader":lambda _:fixture.store,"common_settings_loader":lambda _:(ListingCommonSettings(3.5),[]),
            "existing_listing_lookup":lambda *_:None,"amazon_fetcher":Mock(return_value=fixture.amazon),"keepa_fetcher":Mock(return_value=fixture.keepa)}
        self.evidence=self.stack.enter_context(patch("scripts.listing.quasi_drug_compliance.lookup_japanese_regulated_product_evidence",side_effect=AssertionError("Regulated HTTP forbidden")))
        self.candidate=self.stack.enter_context(patch("scripts.listing.quasi_drug_compliance.has_same_jan_rakuten_candidate",side_effect=AssertionError("Rakuten HTTP forbidden")))

    def test_duplicate_precedes_master_and_phrase_loading_in_both_entrypoints(self):
        self.master.side_effect=AssertionError("Word master must not be loaded")
        self.overrides.side_effect=AssertionError("ASIN phrase overrides must not be loaded")
        self.options["existing_listing_lookup"]=lambda *_:{"management_number":"existing","source":"test"}
        result=service.prepare_listing(self.request,**self.options)
        self.assertEqual(result["listing_status"],"already_listed")
        local_options={key:value for key,value in self.options.items() if key.endswith("loader") or key=="existing_listing_lookup"}
        result=service.precheck_local_listing_exclusion(self.request,**local_options)
        self.assertEqual(result["listing_status"],"already_listed")
        self.master.assert_not_called();self.overrides.assert_not_called()
        self.options["amazon_fetcher"].assert_not_called();self.options["keepa_fetcher"].assert_not_called()

    def test_past_ng_and_blacklist_precede_all_external_calls_and_overrides(self):
        for kind in ("past_ng","blacklist"):
            with self.subTest(kind=kind):
                self.fixture.master.kako_ng={self.request.asin:"existing NG"} if kind=="past_ng" else {}
                self.fixture.master.blacklist={self.request.asin} if kind=="blacklist" else set()
                result=service.prepare_listing(self.request,**self.options)
                self.assertEqual(result["listing_status"],"business_ng")
        self.overrides.assert_not_called()
        self.options["amazon_fetcher"].assert_not_called();self.options["keepa_fetcher"].assert_not_called()

    def test_explicit_local_bypasses_continue_to_external_screening(self):
        self.fixture.master.kako_ng={self.request.asin:"existing NG"}
        self.fixture.master.blacklist={self.request.asin}
        full=Mock(return_value=EvaluationResult("business_ng","full evaluator reached",[],[]))
        result=service.prepare_listing(replace(self.request,bypass_rules=("past_ng","blacklist")),**self.options,evaluator=full)
        self.assertEqual(result["listing_reason"],"full evaluator reached")
        self.options["amazon_fetcher"].assert_called_once();self.options["keepa_fetcher"].assert_called_once()
        self.assertEqual(full.call_args.kwargs["bypass_rules"],{"past_ng","blacklist"})

    def keepa_precheck(self,keepa,request=None,extra=None):
        options={k:v for k,v in self.options.items() if k not in {"amazon_fetcher","keepa_fetcher"}}
        options.update(extra or {})
        return service.precheck_keepa_before_amazon(request or self.request,keepa_fetcher=lambda _:keepa,prepare_kwargs=options)

    def test_adult_digital_and_seller_exclusions_precede_attributes_and_rakuten(self):
        for keepa,reason in ((replace(self.fixture.keepa,is_adult=True),"isAdult"),
                             (replace(self.fixture.keepa,title="Kindle版 商品",category_tree=[{"name":"Kindleストア","catId":1}]),"デジタル"),
                             (replace(self.fixture.keepa,avg90_new_offer_count=1.0),"基準未満"),
                             (replace(self.fixture.keepa,avg90_new_offer_count=None,avg90_seller_count=None),"未取得")):
            with self.subTest(reason=reason):
                block,actual=self.keepa_precheck(keepa,extra={"resolved_fields_builder":Mock(side_effect=AssertionError("Attributes must not run"))})
                self.assertEqual(block["listing_status"],"business_ng")
                self.assertIn(reason,block["listing_reason"])
                self.assertIsNone(block["amazon_result"])
                self.assertIs(actual,keepa)
        self.evidence.assert_not_called();self.candidate.assert_not_called()

    def test_company_block_precedes_regulated_search_but_does_not_make_approval_cache(self):
        self.fixture.master.prohibited_words_rakuten=["Foo"]
        keepa=replace(self.fixture.keepa,brand="株式会社Foo",category_tree=[{"name":"ビューティー","catId":1}])
        request=replace(self.request,forced_company_brand_block=True,forced_word_review_mode=True)
        self.stack.enter_context(patch.object(service,"load_groups",return_value=("test",{"foo":"block"})))
        block,actual=self.keepa_precheck(keepa,request)
        self.assertEqual(block["listing_status"],"company_brand_blocked")
        self.assertEqual(block["forced_word_review"]["state"],"company_brand_blocked")
        self.assertIsNone(block["item_payload"])
        self.assertNotIn("forced_word_review_cache",block)
        self.evidence.assert_not_called();self.candidate.assert_not_called()

    def test_seller_bypass_and_word_substrings_still_reach_the_full_evaluator(self):
        self.fixture.master.prohibited_words_rakuten=["OU"]
        self.stack.enter_context(patch.object(service,"load_groups",return_value=("test",{"ou":"block"})))
        full=Mock(return_value=EvaluationResult("business_ng","full evaluator reached",[],[]))
        request=replace(self.request,forced_company_brand_block=True,bypass_rules=("seller_count",))
        keepa=replace(self.fixture.keepa,title="Count 商品",brand="Count",avg90_new_offer_count=1.0)
        block,_=self.keepa_precheck(keepa,request,{"evaluator":full})
        self.assertEqual(block["listing_reason"],"full evaluator reached")
        full.assert_called_once()
        self.assertIn("seller_count",full.call_args.kwargs["bypass_rules"])

    def test_raw_description_words_wait_for_cleanup_and_final_payload_screening(self):
        self.fixture.master.prohibited_words_rakuten=["Foo"]
        self.stack.enter_context(patch.object(service,"load_groups",return_value=("test",{"foo":"block"})))
        full=Mock(return_value=EvaluationResult("business_ng","full evaluator reached",[],[]))
        request=replace(self.request,forced_company_brand_block=True)
        keepa=replace(self.fixture.keepa,description="説明 Foo",features=["Foo"])
        block,_=self.keepa_precheck(keepa,request,{"evaluator":full})
        self.assertEqual(block["listing_reason"],"full evaluator reached")
        full.assert_called_once()

    def test_uncertain_words_wait_for_real_amazon_and_complete_payload(self):
        self.fixture.master.prohibited_words_rakuten=["OU"]
        self.stack.enter_context(patch.object(service,"load_groups",return_value=("test",{"ou":"review"})))
        request=replace(self.request,forced_company_brand_block=True,forced_word_review_mode=True)
        keepa=replace(self.fixture.keepa,title="商品 OU",brand="OU")
        block,actual=self.keepa_precheck(keepa,request)
        self.assertIsNone(block)
        self.assertIs(actual,keepa)

    def evaluate(self,keepa=None,**kwargs):
        return evaluator.evaluate_listing(asin=self.request.asin,amazon_result=self.fixture.amazon,
            keepa_result=keepa or self.fixture.keepa,master_data=self.fixture.master,store_settings=self.fixture.store,
            management_number="existing",**kwargs)

    def test_marketplace_waits_until_seller_and_image_checks_pass(self):
        lookup=self.stack.enter_context(patch.object(evaluator,"rakuten_marketplace_evidence",side_effect=AssertionError("Marketplace must not run")))
        for keepa,reason in ((replace(self.fixture.keepa,avg90_new_offer_count=1.0),"基準未満"),
                             (replace(self.fixture.keepa,images_csv="",image_urls=[]),"画像候補")):
            with self.subTest(reason=reason):
                result=self.evaluate(keepa,require_minimum_same_jan_listings=True)
                self.assertIn(reason,result.listing_reason)
        lookup.assert_not_called()

    def test_passed_candidate_still_requires_configured_marketplace_threshold(self):
        lookup=self.stack.enter_context(patch.object(evaluator,"rakuten_marketplace_evidence",return_value={"accepted":True,"confirmed_shop_count":7,"jan_exact_shop_count":7,"source":"test"}))
        result=self.evaluate(require_minimum_same_jan_listings=True,minimum_rakuten_shops=7)
        self.assertEqual(result.listing_status,"eligible")
        self.assertEqual(lookup.call_args.kwargs["minimum_shops"],7)
        lookup.return_value={"accepted":False,"confirmed_shop_count":6}
        result=self.evaluate(require_minimum_same_jan_listings=True,minimum_rakuten_shops=7)
        self.assertEqual(result.listing_status,"business_ng")
        self.assertIn("6 < 7",result.listing_reason)

    def test_explicit_word_bypass_does_not_call_same_jan_exception_search(self):
        self.fixture.master.prohibited_words_rakuten=["テストブランド"]
        exception=self.stack.enter_context(patch.object(evaluator,"same_jan_prohibited_word_exception",side_effect=AssertionError("Ignored-word search must not run")))
        result=self.evaluate(bypass_rules={"prohibited_words"})
        self.assertEqual(result.listing_status,"eligible")
        exception.assert_not_called()
        self.assertTrue(any(item["rule"]=="prohibited_words" for item in result.forced_bypass_checks))


if __name__=="__main__":unittest.main()
