"""Mock/offline only: no listing, DB mutations, credential or browser access."""
import ast
import copy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from scripts.listing.forced_word_policy import load_groups, noun_matches, restored_observations, screen_forced_words
from scripts.listing.models import AmazonCheckResult, KeepaProductData
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing
from scripts.listing.models import ListingCommonSettings

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("test_v1", {"ou": "review", "イラ": "review", "コーセー": "block", "小林製薬": "block", "effect": "ignore"})


def prepared(title="商品 OU", brand="", manufacturer=""):
    return {"asin": "B000TEST01", "store_code": "rakuten_2", "listing_status": "eligible", "execution_allowed": True,
            "management_number": "test-item", "blocking_reasons": [], "warnings": [],
            "amazon_result": AmazonCheckResult("B000TEST01", title=title, amazon_price=1000, available_qty=2, gift_available=True),
            "keepa_result": KeepaProductData("B000TEST01", title=title, brand=brand, manufacturer=manufacturer),
            "item_payload": {"title": title, "productDescription": {"pc": title, "sp": title}},
            "inventory_payload": {"quantity": 2}, "image_download_plan": {"items": []}}


class WholeWordPolicyTests(unittest.TestCase):
    def test_classification_contains_only_user_selected_categories(self):
        version, groups = load_groups()
        self.assertEqual(version, "forced_nouns_20261007_v1")
        self.assertEqual(groups["ou"], "review")
        self.assertEqual(groups["イラ"], "review")
        self.assertEqual(groups["医薬部外品"], "ignore")
        self.assertEqual(groups["(株)コパコーポレーション"], "block")

    def test_substrings_do_not_match_even_casefold_nfkc_and_html(self):
        for title in ("Count Highlight ハイライト", "young your house イラスト", "OUST KOU OU型", "小林製薬品"):
            with self.subTest(title=title):
                dry = screen_forced_words(prepared(title), ["OU", "イラ", "小林製薬"],
                                           block_company=True, review_uncertain=True, groups=GROUPS)
                self.assertEqual(dry["listing_status"], "eligible")
        dry = screen_forced_words(prepared("<b>ＯＵ</b>　商品"), ["OU"], review_uncertain=True, groups=GROUPS)
        self.assertEqual(dry["listing_status"], "word_review_pending")
        self.assertTrue(all(match["matched"] == "ou" for match in dry["forced_word_review"]["matches"]))

    def test_company_name_in_structured_field_and_longer_name_distinction(self):
        dry = screen_forced_words(prepared("商品", manufacturer="株式会社小林製薬"), ["小林製薬"],
                                   block_company=True, groups=GROUPS)
        self.assertEqual(dry["listing_status"], "company_brand_blocked")
        self.assertEqual(dry["forced_word_review"]["matches"][0]["field"], "メーカー")
        dry = screen_forced_words(prepared("商品", manufacturer="株式会社小林製薬品"), ["小林製薬"],
                                   block_company=True, groups=GROUPS)
        self.assertEqual(dry["listing_status"], "eligible")

    def test_blocker_precedes_review_and_cannot_be_approved(self):
        dry = screen_forced_words(prepared("OU コーセー"), ["OU", "コーセー"], block_company=True,
                                   review_uncertain=True, groups=GROUPS)
        self.assertEqual(dry["listing_status"], "company_brand_blocked")
        token = dry["forced_word_review"]["review_token"]
        again = screen_forced_words(prepared("OU コーセー"), ["OU", "コーセー"], block_company=True,
                                     review_uncertain=True, approved_token=token, groups=GROUPS)
        self.assertEqual(again["listing_status"], "company_brand_blocked")
        self.assertNotIn("forced_word_review_cache", again)

    def test_hold_has_real_observations_payload_and_no_permission_to_execute(self):
        dry = screen_forced_words(prepared(), ["OU"], review_uncertain=True, groups=GROUPS)
        self.assertEqual(dry["listing_status"], "word_review_pending")
        self.assertFalse(dry["execution_allowed"])
        self.assertFalse(dry["external_actions_performed"])
        cache = dry["forced_word_review_cache"]
        amazon, keepa = restored_observations(cache)
        self.assertEqual(amazon.amazon_price, 1000)
        self.assertEqual(keepa.title, "商品 OU")
        self.assertEqual(cache["item_payload"]["title"], "商品 OU")
        self.assertNotIn("store_settings", cache)
        approved = screen_forced_words(prepared(), ["OU"], review_uncertain=True,
                                        approved_token=dry["forced_word_review"]["review_token"], groups=GROUPS)
        self.assertEqual(approved["listing_status"], "eligible")
        self.assertEqual(approved["forced_word_review"]["state"], "approved")

    def test_approval_does_not_exempt_new_word_new_title_or_different_store(self):
        pending = screen_forced_words(prepared(), ["OU"], review_uncertain=True, groups=GROUPS)
        token = pending["forced_word_review"]["review_token"]
        for dry in (prepared("商品 OU イラ"), prepared("別の商品 OU")):
            self.assertEqual(screen_forced_words(dry, ["OU", "イラ"], review_uncertain=True,
                                                 approved_token=token, groups=GROUPS)["listing_status"], "word_review_pending")
        dry = prepared()
        dry["store_code"] = "rakuten_1"
        self.assertEqual(screen_forced_words(dry, ["OU"], review_uncertain=True,
                                             approved_token=token, groups=GROUPS)["listing_status"], "word_review_pending")

    def test_unknown_new_words_review_ignored_words_and_active_master_intersection(self):
        dry = screen_forced_words(prepared("NewName effect"), ["NewName", "effect"], review_uncertain=True, groups=GROUPS)
        self.assertEqual({match["word"] for match in dry["forced_word_review"]["matches"]}, {"NewName"})
        self.assertEqual(screen_forced_words(prepared("コーセー"), [], block_company=True, groups=GROUPS)["listing_status"], "eligible")
        self.assertEqual(screen_forced_words(prepared("OU コーセー"), ["OU", "コーセー"], groups=GROUPS)["listing_status"], "eligible")

    def test_other_ng_never_becomes_approvable_and_normal_request_defaults_off(self):
        dry = prepared()
        dry.update(listing_status="business_ng", execution_allowed=False)
        self.assertEqual(screen_forced_words(dry, ["OU"], review_uncertain=True, groups=GROUPS)["listing_status"], "business_ng")
        self.assertNotIn("forced_word_review_cache", dry)
        request = PrepareListingRequest("B000TEST01", "rakuten_2", Path("unused"))
        self.assertFalse(request.forced_company_brand_block)
        self.assertFalse(request.forced_word_review_mode)

    def test_batch_stops_holds_before_preflight_or_write_and_rechecks_approval_flags(self):
        text = (ROOT / "scripts/rakuten_listing_batch_execute.py").read_text(encoding="utf-8")
        self.assertEqual(text.count('{"already_listed", "business_ng", *HOLD_STATUSES}'), 2)
        self.assertLess(text.index('*HOLD_STATUSES'), text.index('build_preflight_result,\n'))
        self.assertIn("forced_company_brand_block=getattr(args", text)
        self.assertIn('approved_forced_word_review_token=getattr(args', text)
        self.assertIn('age <= 86400', text)
        self.assertIn('fresh_amazon = await fetch_amazon_result', text)

    def test_worker_reads_only_the_exact_approved_source_and_rejects_changed_token(self):
        source = ROOT / "scripts/rakuten_listing_batch_execute.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load_review_caches")
        cursor = MagicMock()
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        connect = MagicMock(return_value=connection)
        env = {"connect_db": connect}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), env)
        dry = screen_forced_words(prepared(), ["OU"], review_uncertain=True, groups=GROUPS)
        token = dry["forced_word_review"]["review_token"]
        cursor.fetchall.return_value = [("B000TEST01", dry, "rakuten_2", {"forced_word_review_mode": True})]
        load = env["load_review_caches"]
        self.assertEqual(load("source", "rakuten_2", ["B000TEST01"], token)["B000TEST01"]["review_token"], token)
        connect.assert_called_once_with(options="-c default_transaction_read_only=on")
        self.assertEqual(cursor.execute.call_args.args[1], ("source", ["B000TEST01"]))
        with self.assertRaises(ValueError): load("source", "rakuten_2", ["B000TEST01"], "unseen-token")
        with self.assertRaises(ValueError): load("source", "rakuten_1", ["B000TEST01"], token)
        with self.assertRaises(ValueError): load("source", "rakuten_2", ["B000TEST01", "B000OTHER1"], token)
        self.assertEqual(load("", "rakuten_2", [], ""), {})

    def test_real_preparation_does_not_let_legacy_contains_block_new_review_mode(self):
        # Reuse the bounded public fixtures, while injecting every DB loader.
        from tests.test_rakuten_listing_payload import RakutenListingPhase1Tests
        fixture = RakutenListingPhase1Tests()
        fixture.setUp()
        fixture.master.prohibited_words_rakuten = ["OU", "イラ"]
        fixture.keepa.avg90_new_offer_count = 4.2
        fixture.keepa.image_urls = ["https://example.invalid/product.jpg"]
        request = PrepareListingRequest("B000TEST01", "rakuten_1", Path("unused"), dry_run=True,
                                        forced_company_brand_block=True, forced_word_review_mode=True)
        def run(title):
            fixture.amazon.title = title
            return prepare_listing(request, store_settings_loader=lambda _:fixture.store,
                                   master_data_loader=lambda *_:fixture.master,
                                   amazon_fetcher=lambda *_:fixture.amazon, keepa_fetcher=lambda _:fixture.keepa,
                                   common_settings_loader=lambda *_:(ListingCommonSettings(3.5),[]),
                                   existing_listing_lookup=lambda *_:None)
        with patch("scripts.listing.prepare_service.apply_asin_master_overrides", side_effect=lambda master,*_:master), \
             patch("scripts.listing.prepare_service.apply_store_master_overrides", side_effect=lambda master,*_:master), \
             patch("scripts.listing.forced_word_classification_db.read_overrides", return_value={}):
            # No prohibited_words bypass: new mode still owns these words.
            partial = run("Count ハイライト 商品")
            self.assertEqual(partial["listing_status"], "eligible", partial.get("listing_reason"))
            held = run("商品 OU")
            self.assertEqual(held["listing_status"], "word_review_pending", held.get("listing_reason"))
            self.assertFalse(held["execution_allowed"])
            self.assertTrue(held["forced_word_review_cache"])
        self.assertEqual(fixture.master.prohibited_words_rakuten, ["OU", "イラ"])


if __name__ == "__main__":
    unittest.main()
