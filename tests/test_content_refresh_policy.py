from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.listing.content_refresh_policy import content_refresh_artifact_error
from scripts.listing.image_downloader import DownloadedImageResult
from scripts.listing.listing_evaluator import evaluate_listing
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.models import AmazonCheckResult, KeepaProductData, ListingCommonSettings, MasterData, StoreSettings, to_jsonable
from scripts.listing.prepare_service import PrepareListingRequest, precheck_keepa_before_amazon, precheck_local_listing_exclusion, prepare_listing
from scripts.listing.preflight_service import _build_checks
from scripts.listing.rakuten_item_client import RakutenItemClient, RakutenItemResult
from scripts.listing.rakuten_image_client import RakutenImageClient, RakutenImageUploadResult


class ContentRefreshTests(unittest.TestCase):
    def setUp(self):
        # Fail closed if a regression accidentally reaches live services.
        for name in ("psycopg.connect", "requests.sessions.Session.request"):
            guard = patch(name, side_effect=AssertionError("Live service forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        for name in ("apply_store_master_overrides", "apply_asin_master_overrides"):
            stub = patch("scripts.listing.prepare_service." + name, side_effect=lambda master, *args: master)
            stub.start()
            self.addCleanup(stub.stop)
        fixture = Path(__file__).parent / "fixtures" / "eligible_store_settings.json"
        self.store = StoreSettings(**json.loads(fixture.read_text(encoding="utf-8")))
        self.asin = "B000TEST01"
        self.amazon = AmazonCheckResult(self.asin, page_asin=self.asin, title="置換前 禁止語 商品", amazon_price=1000, available_qty=2, gift_available=True)
        self.keepa = KeepaProductData(self.asin, title=self.amazon.title, description="置換前 禁止語 説明", features=["置換前 特徴"],
                                     brand="ブランド", model="型番", category_id=1, avg90_new_offer_count=4,
                                     image_urls=["https://m.media-amazon.com/images/I/test.jpg"], image_source="keepa_images")
        self.master = MasterData(set(), {}, [], [], [], {}, {1: 101737}, {101737: ["ブランド名", "メーカー型番"]},
                                 cleanup_replacements=[("置換前", "置換済")])
        self.existing = {"management_number": "20261027120000_187", "current_price": 3456, "current_stock": 1}
        self.request = PrepareListingRequest(self.asin, "rakuten_1", Path("dummy"), dry_run=True, update_existing=True)

    def prepare(self, **kwargs):
        options = dict(store_settings_loader=lambda _: self.store, master_data_loader=lambda *_: self.master,
                       common_settings_loader=lambda _: (ListingCommonSettings(3.5), []),
                       existing_listing_lookup=lambda *_: self.existing,
                       amazon_fetcher=lambda *_: self.amazon, keepa_fetcher=lambda _: self.keepa)
        options.update(kwargs)
        return prepare_listing(self.request, **options)

    def test_refresh_skips_all_listing_rules_but_converts_text_and_preserves_price_stock(self):
        self.master.kako_ng[self.asin] = "過去NG"
        self.master.blacklist.add(self.asin)
        self.master.company_brand_ng[self.asin] = "会社NG"
        self.master.prohibited_words_rakuten = ["禁止語"]
        self.master.prohibited_words_other = ["ブランド"]
        self.master.amazon_category_exclusions = {1: "カテゴリNG"}
        self.master.legacy_spacing_replacements = [{"source": "禁止語", "target": "禁 止語"}]
        self.keepa.is_adult = True
        self.keepa.avg90_new_offer_count = None
        self.amazon = replace(self.amazon, amazon_price=None, available_qty=0, gift_available=False, business_ng=True, ng_reason="配送条件NG")
        self.request.forced_company_brand_block = self.request.forced_word_review_mode = True
        self.request.require_minimum_same_jan_listings = True
        with patch("scripts.listing.listing_evaluator.analyze_listing_text_policy", side_effect=AssertionError("word screening")), \
             patch("scripts.listing.listing_evaluator.rakuten_marketplace_evidence", side_effect=AssertionError("marketplace screening")), \
             patch("scripts.listing.prepare_service.load_groups", side_effect=AssertionError("forced screening")):
            result = self.prepare()
        self.assertEqual(result["listing_status"], "eligible")
        self.assertTrue(result["content_refresh"])
        self.assertTrue(result["execution_allowed"])
        self.assertEqual(result["blocking_reasons"], [])
        self.assertTrue(result["seller_count_evaluation"]["skipped"])
        self.assertEqual(result["matched_forbidden_words"], [])
        self.assertEqual(result["legacy_spacing_reviews"], [])
        payload = result["item_payload"]
        self.assertEqual(payload["title"], "置換済 禁止語 商品")
        for text in payload["productDescription"].values():
            self.assertIn("置換済", text)
            self.assertNotIn("置換前", text)
        self.assertEqual(payload["variants"][self.existing["management_number"]]["standardPrice"], "3456")
        self.assertEqual(result["inventory_payload"]["quantity"], 1)
        self.assertIsNone(result["amazon_result"].amazon_price)  # no fake purchase facts
        self.assertIsNone(content_refresh_artifact_error(to_jsonable(result)))

    def test_local_and_keepa_prechecks_do_not_screen_refresh(self):
        self.keepa.avg90_new_offer_count = None
        self.keepa.is_adult = True
        self.assertIsNone(precheck_local_listing_exclusion(self.request))
        rejected, observed = precheck_keepa_before_amazon(self.request, keepa_fetcher=lambda _: self.keepa)
        self.assertIsNone(rejected)
        self.assertIs(observed, self.keepa)

    def test_identity_failure_and_retrieval_failure_still_block(self):
        for changes in ({"page_asin": "B000OTHER1"}, {"page_asin": ""}, {"requested_asin": "B000OTHER1"},
                        {"business_ng": True, "ng_reason": "ASIN不一致: canonical mismatch"},
                        {"business_ng": True, "ng_reason": "ASIN未確認: no identity"},
                        {"system_error": True, "ng_reason": "timeout"},
                        {"amazon_confirmation_waiting": True}):
            with self.subTest(changes=changes):
                result = self.prepare(amazon_fetcher=lambda *_, changes=changes: replace(self.amazon, **changes))
                self.assertFalse(result["execution_allowed"])
                self.assertIsNone(result["item_payload"])

    def test_keepa_mismatch_and_missing_images_still_block(self):
        for changes in ({"asin": "B000OTHER1"}, {"image_urls": []}):
            with self.subTest(changes=changes):
                result = self.prepare(keepa_fetcher=lambda _, changes=changes: replace(self.keepa, **changes))
                self.assertFalse(result["execution_allowed"])

    def test_refresh_does_not_create_new_listing_or_invent_price(self):
        for existing in (None, {**self.existing, "current_price": None}, {**self.existing, "current_price": 0}):
            with self.subTest(existing=existing), self.assertRaises(RuntimeError):
                self.prepare(existing_listing_lookup=lambda *_: existing)

    def test_normal_listing_retains_past_ng_words_and_seller_rules(self):
        for rule in ("past_ng", "words", "seller"):
            with self.subTest(rule=rule):
                master, keepa = copy.deepcopy(self.master), copy.deepcopy(self.keepa)
                if rule == "past_ng": master.kako_ng[self.asin] = "past"
                if rule == "words": master.prohibited_words_rakuten = ["禁止語"]
                if rule == "seller": keepa.avg90_new_offer_count = 0
                with patch("scripts.listing.listing_evaluator.same_jan_prohibited_word_exception", return_value=None):
                    result = evaluate_listing(asin=self.asin, amazon_result=self.amazon, keepa_result=keepa, master_data=master,
                                              store_settings=self.store, management_number="item", common_settings=ListingCommonSettings(3.5))
                self.assertEqual(result.listing_status, "business_ng")

    def test_preflight_skips_empty_jan_but_checks_identity_and_payload(self):
        result = to_jsonable(self.prepare())
        def checks(dry):
            return {check["key"]: check for check in _build_checks(
                dry, input_json_path=Path(__file__), asin=self.asin, store="rakuten_1", management_number=self.existing["management_number"],
                unresolved_specifications=[], text_validation_issues=[], auth_configuration_summary={}, management_consistency={"all_match": True})}
        self.assertEqual(checks(result)["jan_ean"]["status"], "ok")
        self.assertEqual(checks(result)["content_refresh_identity"]["status"], "ok")
        result["item_payload"]["title"] += " ク リア"
        self.assertEqual(checks(result)["title_contains_legacy_spacing_artifact"]["status"], "ok")
        result["amazon_result"]["page_asin"] = "B000OTHER1"
        self.assertEqual(checks(result)["content_refresh_identity"]["status"], "blocked")

    def test_saved_identity_failure_stops_before_images_or_api(self):
        result = self.prepare()
        result["amazon_result"] = replace(self.amazon, business_ng=True, ng_reason="ASIN不一致: guarded")
        download = Mock(side_effect=AssertionError("image write forbidden"))
        executed = execute_listing(ExecuteListingRequest(dry_run_result=result, execute=True, approved=True, asin=self.asin, content_refresh=True), image_downloader=download)
        self.assertEqual(executed["execute_status"], "validation_failed")
        download.assert_not_called()

    def test_refresh_mock_send_skips_final_category_rule_and_inventory_write(self):
        result = self.prepare()
        downloaded = DownloadedImageResult("main", 1, self.keepa.image_urls[0], "test.jpg", "test.jpg", "test.jpg", True, "downloaded", 200, "image/jpeg", 100)
        validated = replace(downloaded, validation_status="valid", validation_errors=[], width=1000, height=1000)
        image = RakutenImageClient(uploader=lambda _: RakutenImageUploadResult("uploaded", "https://shop.r10s.jp/test/cabinet/test.jpg", {}, 200))
        sent = []
        def send(request):
            sent.append(request.payload)
            return RakutenItemResult(True, request.management_number, 200, {}, False, {})
        inventory = Mock()
        category = Mock(side_effect=AssertionError("listing-only category rule"))
        executed = execute_listing(ExecuteListingRequest(dry_run_result=result, execute=True, approved=True, asin=self.asin, content_refresh=True),
                                   image_downloader=lambda *_args, **_kwargs: {"items": [downloaded]},
                                   image_validator=lambda _: {"items": [validated]}, image_client=image,
                                   item_client=RakutenItemClient(sender=send), inventory_client=inventory, category_checker=category)
        self.assertEqual(executed["execute_status"], "completed")
        self.assertTrue(executed["inventory_result"]["skipped"])
        inventory.put_inventory.assert_not_called()
        category.assert_not_called()
        self.assertEqual(sent[0]["variants"][self.existing["management_number"]]["standardPrice"], "3456")
        self.assertIn("置換済", sent[0]["title"])

    def test_regulated_evidence_absence_is_not_a_refresh_eligibility_rule(self):
        self.keepa.category_tree = [{"catId": 1, "name": "ビューティー"}]
        self.master.genre_paths[101737] = "美容・コスメ・香水>その他"
        with patch("scripts.listing.quasi_drug_compliance.lookup_japanese_regulated_product_evidence", return_value={}), \
             patch("scripts.listing.quasi_drug_compliance.has_same_jan_rakuten_candidate", return_value=False):
            result = self.prepare()
        self.assertEqual(result["listing_status"], "eligible")

    def test_missing_attributes_use_dash_and_missing_images_do_not_pass(self):
        self.keepa.brand = self.keepa.model = ""
        result = self.prepare()
        self.assertTrue(result["execution_allowed"])
        self.assertEqual([a["values"] for a in result["item_payload"]["variants"][self.existing["management_number"]]["attributes"]], [["-"], ["-"]])

    def test_saved_old_refresh_artifact_is_not_accepted(self):
        result = self.prepare()
        result.pop("content_refresh")
        self.assertIn("再取得", content_refresh_artifact_error(to_jsonable(result)))


if __name__ == "__main__":
    unittest.main()
