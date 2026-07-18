from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.master_loader import load_master_data
from scripts.listing.models import AmazonCheckResult, KeepaProductData, StoreSettings, to_jsonable
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing
from scripts.listing.prohibited_word_masking import (
    analyze_prohibited_word_issues,
    detect_legacy_spacing_reviews,
    detect_prohibited_word_issues,
    load_allowed_phrase_rules,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
REFERENCE_MASTER_DIR = ROOT_DIR / "reference" / "legacy_listing"


def _rules() -> dict[str, list[str]]:
    return {
        "クリ": ["クリア"],
        "アルコール": [
            "アルコールフリー",
            "エチルアルコール",
            "ステアリルアルコール",
            "セテアリルアルコール",
            "ベヘニルアルコール",
            "変性アルコール",
        ],
        "スキン": [
            "スキンケース",
            "スキンタイプ",
            "スキントーン",
            "スキンプロテクトミルク",
        ],
    }


class ProhibitedWordMaskingTests(unittest.TestCase):
    def test_clear_phrase_is_allowed(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues({"title": "クリアブルーラメ"}, ["クリ"], _rules())
        self.assertEqual(forbidden, [])
        self.assertEqual([item["allowed_phrase"] for item in allowed], ["クリア"])

    def test_acrylic_is_still_ng(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues({"title": "アクリルケース"}, ["クリ"], _rules())
        self.assertEqual(allowed, [])
        self.assertEqual([item["word"] for item in forbidden], ["クリ"])

    def test_clear_then_plain_kuri_only_hits_second(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues({"title": "クリア クリ成分"}, ["クリ"], _rules())
        self.assertEqual([item["allowed_phrase"] for item in allowed], ["クリア"])
        self.assertEqual(len(forbidden), 1)
        self.assertIn("クリ成分", forbidden[0]["context"])

    def test_multiple_allowed_occurrences_are_all_ignored(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues({"title": "クリアクリア"}, ["クリ"], _rules())
        self.assertEqual(len(allowed), 2)
        self.assertEqual(forbidden, [])

    def test_alcohol_free_is_allowed_but_other_alcohol_is_ng(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues(
            {"title": "アルコールフリー アルコール配合"},
            ["アルコール"],
            _rules(),
        )
        self.assertEqual([item["allowed_phrase"] for item in allowed], ["アルコールフリー"])
        self.assertEqual(len(forbidden), 1)
        self.assertIn("アルコール配合", forbidden[0]["context"])

    def test_ethyl_alcohol_is_allowed(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues({"title": "エチルアルコール"}, ["アルコール"], _rules())
        self.assertEqual([item["allowed_phrase"] for item in allowed], ["エチルアルコール"])
        self.assertEqual(forbidden, [])

    def test_skin_type_is_allowed_but_skin_component_is_ng(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues({"title": "スキンタイプ / スキン成分"}, ["スキン"], _rules())
        self.assertEqual([item["allowed_phrase"] for item in allowed], ["スキンタイプ"])
        self.assertEqual(len(forbidden), 1)

    def test_non_alcohol_is_not_enabled_yet(self) -> None:
        allowed, forbidden = detect_prohibited_word_issues({"title": "ノンアルコール"}, ["アルコール"], _rules())
        self.assertEqual(allowed, [])
        self.assertEqual(len(forbidden), 1)

    def test_original_text_is_not_changed(self) -> None:
        text = "クリアブルーラメ"
        detect_prohibited_word_issues({"title": text}, ["クリ"], _rules())
        self.assertEqual(text, "クリアブルーラメ")

    def test_legacy_spacing_reviews_capture_unmigrated_rule(self) -> None:
        reviews = detect_legacy_spacing_reviews(
            {"title": "サイエンスクイズ"},
            [{"source": "サイエンス", "target": "サイエ ンス", "suspected_forbidden_word": "エンス"}],
            _rules(),
        )
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["migration_status"], "needs_review")
        self.assertEqual(reviews[0]["legacy_replaced_text"], "サイエ ンスクイズ")

    def test_diagnostics_are_json_serializable(self) -> None:
        payload = {
            "allowed": detect_prohibited_word_issues({"title": "クリアブルーラメ"}, ["クリ"], _rules())[0],
            "reviews": detect_legacy_spacing_reviews(
                {"title": "サイエンスクイズ"},
                [{"source": "サイエンス", "target": "サイエ ンス", "suspected_forbidden_word": "エンス"}],
                _rules(),
            ),
        }
        text = json.dumps(to_jsonable(payload), ensure_ascii=False)
        self.assertIn("クリア", text)
        self.assertIn("needs_review", text)

    def test_b0cn39x1fc_stays_eligible_and_preserves_original_text(self) -> None:
        saved = json.loads((ROOT_DIR / "output" / "listing" / "B0CN39X1FC_dry_run.json").read_text(encoding="utf-8"))
        master = load_master_data(REFERENCE_MASTER_DIR, allow_missing=True)
        store = StoreSettings(
            store_id=4,
            store_code="rakuten_1",
            store_name="rakuten_1",
            max_stock=4,
            fee_rate=0.15,
            use_amazon_point=False,
            profit_mode="amount",
            profit_rate=0.0,
            profit_amount=300,
            fixed_cost=0,
            rounding_unit=1,
            normal_delivery_date_id=1,
            back_order_delivery_date_id=1,
            normal_delivery_time_id=1,
            back_order_delivery_time_id=1,
            ship_from_ids=["1"],
            management_suffix="187",
        )
        amazon = AmazonCheckResult(**saved["amazon_result"])
        keepa = KeepaProductData(**saved["keepa_result"])
        result = prepare_listing(
            PrepareListingRequest(
                asin="B0CN39X1FC",
                store_code="rakuten_1",
                master_dir=REFERENCE_MASTER_DIR,
                dry_run=True,
                allow_missing_master=True,
            ),
            store_settings_loader=lambda store_code: store,
            master_data_loader=lambda master_dir, allow_missing: master,
            amazon_fetcher=lambda asin, page_timeout_ms: amazon,
            keepa_fetcher=lambda asin: keepa,
        )
        self.assertEqual(result["listing_status"], "eligible")
        self.assertEqual(result["resolved_attributes"]["代表カラー"].value, "クリアブルーラメ")
        self.assertEqual(result["item_payload"]["title"], saved["amazon_result"]["title"])
        self.assertNotIn("ク リア", result["item_payload"]["title"])
        payload_attrs = result["item_payload"]["variants"][result["management_number"]]["attributes"]
        representative_color = next(item["value"] for item in payload_attrs if item["name"] == "代表カラー")
        self.assertEqual(representative_color, "ブルー")
        self.assertEqual(result["representative_color_mapping"]["original_value"], "クリアブルーラメ")
        self.assertEqual(result["representative_color_mapping"]["api_value"], "ブルー")
        self.assertTrue(any(item["allowed_phrase"] == "クリア" for item in result["allowed_phrase_matches"]))
        self.assertEqual(result["matched_forbidden_words"], [])
        self.assertEqual(result["required_separate_checks"], [])
        self.assertEqual(result["matched_separate_check_phrases"], [])
        self.assertEqual(result["legacy_spacing_reviews"], [])


    def test_execute_is_blocked_when_legacy_spacing_review_remains(self) -> None:
        result = execute_listing(
            ExecuteListingRequest(
                dry_run_result={
                    "asin": "B000TEST01",
                    "store_code": "rakuten_1",
                    "listing_status": "eligible",
                    "management_number": "20250101010101_187",
                    "execution_allowed": True,
                    "blocking_reasons": [],
                    "legacy_spacing_reviews": [
                        {
                            "field": "title",
                            "original_text": "繧ｵ繧､繧ｨ繝ｳ繧ｹ繧ｯ繧､繧ｺ",
                            "legacy_replaced_text": "繧ｵ繧､繧ｨ 繝ｳ繧ｹ繧ｯ繧､繧ｺ",
                            "migration_status": "needs_review",
                        }
                    ],
                    "item_payload": {"itemNumber": "20250101010101_187"},
                    "inventory_payload": {"inventoryType": 1},
                },
                execute=True,
                approved=True,
                asin="B000TEST01",
                management_number="20250101010101_187",
            ),
            image_downloader=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not download")),
        )
        self.assertEqual(result["execute_status"], "validation_failed")
        self.assertIn("legacy spacing replacements require migration review", result["errors"][0])

    def test_allowed_phrase_master_schema_loads_meta_and_separate_checks(self) -> None:
        payload = load_allowed_phrase_rules(REFERENCE_MASTER_DIR / "allowed_phrases_rakuten.json")
        self.assertIn("meta", payload)
        self.assertIn("rules", payload)
        self.assertIn("separate_checks", payload)
        self.assertGreater(payload["rule_count"], 0)
        self.assertGreater(payload["allowed_phrase_count"], 0)
        self.assertGreater(payload["separate_check_count"], 0)
        self.assertIn("クリ", payload["rules"])
        self.assertIn("クリア", payload["rules"]["クリ"])

    def test_separate_check_phrase_is_reported_without_forbidden_hit(self) -> None:
        analysis = analyze_prohibited_word_issues(
            {"title": "iPhone対応ケース"},
            ["iPhone"],
            {"iPhone": ["iPhone"]},
            separate_check_rules={"iPhone": [{"phrase": "iPhone", "forbidden_word": "iPhone", "required_checks": ["brand_masking"]}]},
        )
        self.assertEqual(analysis["matched_forbidden_words"], [])
        self.assertEqual(analysis["required_separate_checks"], ["brand_masking"])
        self.assertEqual(analysis["matched_separate_check_phrases"][0]["phrase"], "iPhone")

    def test_separate_check_phrase_and_ng_word_can_coexist(self) -> None:
        analysis = analyze_prohibited_word_issues(
            {"title": "アルコールフリー アルコール配合"},
            ["アルコール"],
            {"アルコール": ["アルコールフリー"]},
            separate_check_rules={"アルコールフリー": [{"phrase": "アルコールフリー", "forbidden_word": "アルコール", "required_checks": ["alcohol"]}]},
        )
        self.assertEqual(analysis["required_separate_checks"], ["alcohol"])
        self.assertEqual(len(analysis["matched_forbidden_words"]), 1)
        self.assertEqual(analysis["matched_forbidden_words"][0]["word"], "アルコール")


if __name__ == "__main__":
    unittest.main()
