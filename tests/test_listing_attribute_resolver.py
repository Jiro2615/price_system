from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.listing.attribute_policy import resolve_required_attributes
from scripts.listing.attribute_resolver import build_resolved_fields
from scripts.listing.listing_evaluator import evaluate_listing
from scripts.listing.models import AmazonCheckResult, KeepaProductData, MasterData, StoreSettings, to_jsonable
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


ROOT_DIR = Path(__file__).resolve().parents[1]


class ListingAttributeResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={5263237051: 101737},
            attribute_definitions={101737: ["ブランド名", "メーカー型番"]},
            missing_files=[],
        )
        self.master_actual_mapping = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={5263237051: 111120},
            attribute_definitions={111120: ["ブランド名", "メーカー型番", "原産国／製造国"]},
            missing_files=[],
        )
        self.store = StoreSettings(
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
            min_avg90_sellers=3.5,
        )
        self.amazon = AmazonCheckResult(
            requested_asin="B0TEST0001",
            page_asin="B0TEST0001",
            title="Amazon商品タイトル",
            amazon_price=2000,
            available_qty=9,
            gift_available=True,
            shipping_status="next day shipping",
            business_ng=False,
            system_error=False,
            ng_reason="",
            current_url="",
        )
        self.keepa = KeepaProductData(
            asin="B0TEST0001",
            title="Keepa商品タイトル 日本製",
            brand="KeepaBrand",
            manufacturer="KeepaMaker",
            model="MODEL-1",
            part_number="PART-1",
            ean="1234567890123",
            images_csv="legacy1,legacy2",
            image_urls=[
                "https://m.media-amazon.com/images/I/preferred1.jpg",
                "https://m.media-amazon.com/images/I/preferred2.jpg",
            ],
            image_source="keepa_images",
            category_id=5263237051,
            features=["特徴1", "特徴2"],
            description="Keepa説明文",
            style="StyleA",
            size="60mL",
            color="Black",
            current_new_offer_count=1,
            avg90_new_offer_count=4.2,
            avg90_seller_count=4.2,
            hazardous_materials=["ETHANOL", "UN1170", "3"],
            is_heat_sensitive=False,
            scent="chapter65",
            is_adult=False,
            is_adult_source="isAdultProduct",
        )

    def test_amazon_title_is_preferred_over_keepa(self) -> None:
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["title"].value, "Amazon商品タイトル")
        self.assertEqual(resolved["title"].source, "amazon")
        self.assertFalse(resolved["title"].fallback_used)

    def test_keepa_title_is_used_when_amazon_title_missing(self) -> None:
        amazon = AmazonCheckResult(requested_asin="B0TEST0001", page_asin="B0TEST0001", title="")
        resolved = build_resolved_fields(
            amazon_result=amazon,
            keepa_result=self.keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["title"].value, "Keepa商品タイトル 日本製")
        self.assertEqual(resolved["title"].source, "keepa")
        self.assertTrue(resolved["title"].fallback_used)

    def test_brand_and_model_fallbacks_are_recorded(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "brand": "", "model": ""})
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["brand"].value, "KeepaMaker")
        self.assertTrue(resolved["brand"].fallback_used)
        self.assertEqual(resolved["model_number"].value, "PART-1")
        self.assertTrue(resolved["model_number"].fallback_used)

    def test_no_dash_fallback_is_added_for_missing_model(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "model": "", "part_number": ""})
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertIsNone(resolved["model_number"].value)
        self.assertEqual(resolved["model_number"].source, "none")

    def test_ean_category_genre_and_images_are_recorded(self) -> None:
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["ean"].value, "1234567890123")
        self.assertEqual(resolved["category_id"].value, 5263237051)
        self.assertEqual(resolved["genre_id"].value, 101737)
        self.assertEqual(resolved["main_image"].value, "https://m.media-amazon.com/images/I/preferred1.jpg")
        self.assertEqual(len(resolved["image_urls"].value), 2)
        self.assertEqual(resolved["image_source"].value, "keepa_images")

    def test_offer_counts_and_adult_source_are_distinct(self) -> None:
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["current_new_offer_count"].value, 1)
        self.assertEqual(resolved["avg90_new_offer_count"].value, 4.2)
        self.assertEqual(resolved["is_adult"].value, False)
        self.assertEqual(resolved["is_adult"].raw_path, "products[0].isAdultProduct")

    def test_hazardous_materials_and_country_candidate_are_information_only(self) -> None:
        resolved = build_resolved_fields(
            amazon_result=None,
            keepa_result=self.keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["hazardous_materials"].value[:2], ["ETHANOL", "UN1170"])
        self.assertEqual(resolved["scent"].value, "chapter65")
        self.assertEqual(resolved["country_of_origin_candidate"].value, "日本製")
        self.assertEqual(resolved["country_of_origin_candidate"].confidence, "medium")

    def test_description_candidate_falls_back_to_features_with_metadata(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "description": "", "features": ["特徴A", "特徴B"]})
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["description_candidate"].value, "特徴A\n特徴B")
        self.assertEqual(resolved["description_candidate"].raw_path, "products[0].features")
        self.assertTrue(resolved["description_candidate"].fallback_used)

    def test_country_of_origin_candidate_uses_amazon_title_path(self) -> None:
        amazon = AmazonCheckResult(**{**self.amazon.__dict__, "title": "Amazon 日本製 テスト商品"})
        keepa = KeepaProductData(**{**self.keepa.__dict__, "title": "Keepa商品タイトル", "description": ""})
        resolved = build_resolved_fields(
            amazon_result=amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["country_of_origin_candidate"].value, "日本製")
        self.assertEqual(resolved["country_of_origin_candidate"].raw_path, "amazon_result.title")
        self.assertEqual(resolved["country_of_origin_candidate"].confidence, "medium")

    def test_country_of_origin_candidate_uses_keepa_title_path(self) -> None:
        amazon = AmazonCheckResult(**{**self.amazon.__dict__, "title": ""})
        keepa = KeepaProductData(**{**self.keepa.__dict__, "title": "Keepa 日本製 商品", "description": ""})
        resolved = build_resolved_fields(
            amazon_result=amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["country_of_origin_candidate"].value, "日本製")
        self.assertEqual(resolved["country_of_origin_candidate"].raw_path, "products[0].title")

    def test_country_of_origin_candidate_uses_description_path(self) -> None:
        amazon = AmazonCheckResult(**{**self.amazon.__dict__, "title": ""})
        keepa = KeepaProductData(**{**self.keepa.__dict__, "title": "Keepa商品", "description": "これは日本製です"})
        resolved = build_resolved_fields(
            amazon_result=amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["country_of_origin_candidate"].value, "日本製")
        self.assertEqual(resolved["country_of_origin_candidate"].raw_path, "products[0].description")

    def test_country_of_origin_candidate_does_not_match_japan_targeted_only(self) -> None:
        amazon = AmazonCheckResult(**{**self.amazon.__dict__, "title": "Amazon 日本向け テスト商品"})
        keepa = KeepaProductData(**{**self.keepa.__dict__, "title": "Keepa商品", "description": "日本限定表記のみ"})
        resolved = build_resolved_fields(
            amazon_result=amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertIsNone(resolved["country_of_origin_candidate"].value)
        self.assertEqual(resolved["country_of_origin_candidate"].source, "none")

    def test_genre_id_is_unresolved_when_category_mapping_is_missing(self) -> None:
        master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={},
            attribute_definitions={},
            missing_files=[],
        )
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=self.keepa,
            master_data=master,
        )
        self.assertIsNone(resolved["genre_id"].value)
        self.assertEqual(resolved["genre_id"].source, "none")

    def test_is_adult_unknown_is_recorded_without_coercion(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "is_adult": None, "is_adult_source": "unknown"})
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        self.assertEqual(resolved["is_adult"].value, "unknown")
        self.assertEqual(resolved["is_adult"].source, "none")
        self.assertIsNone(resolved["is_adult"].raw_path)
        self.assertEqual(resolved["is_adult"].confidence, "none")

    def test_resolved_fields_are_json_serializable(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "hazardous_materials": [], "image_urls": [], "image_source": "none"})
        resolved = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master_actual_mapping,
        )
        self.assertIsNone(resolved["hazardous_materials"].value)
        self.assertIsNone(resolved["image_urls"].value)
        text = json.dumps(to_jsonable({"resolved_fields": resolved}), ensure_ascii=False)
        self.assertIn("resolved_fields", text)
        self.assertIn("111120", text)

    def test_prepare_listing_exposes_resolved_fields_without_changing_payload(self) -> None:
        result = prepare_listing(
            PrepareListingRequest(
                asin="B0TEST0001",
                store_code="rakuten_1",
                master_dir=Path("C:/dummy/master"),
                dry_run=True,
            ),
            store_settings_loader=lambda store_code: self.store,
            master_data_loader=lambda master_dir, allow_missing: self.master,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon,
            keepa_fetcher=lambda asin: self.keepa,
        )
        self.assertIn("resolved_fields", result)
        self.assertIn("resolved_attributes", result)
        self.assertEqual(result["resolved_fields"]["title"].value, "Amazon商品タイトル")
        self.assertEqual(result["item_payload"]["itemNumber"], result["management_number"])

    def test_genre_111120_resolves_actual_inferred_and_legacy_dash_fields(self) -> None:
        keepa = KeepaProductData(
            **{
                **self.keepa.__dict__,
                "brand": "A\u00edam",
                "manufacturer": "Aiam",
                "model": "",
                "part_number": "",
                "color": "",
                "title": "Aiam item \u65e5\u672c\u88fd",
                "features": [
                    "\u3042\u306a\u305f\u306e\u4eba\u751f\u306b\u5bc4\u308a\u6dfb\u3046\u300cchapter\uff08\u9999\u308a\uff09\u300d\u30b7\u30ea\u30fc\u30ba\u306f\u51688\u7a2e\u985e"
                ],
                "category_id": 5263237051,
            }
        )
        resolved_fields = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master_actual_mapping,
        )
        resolved_attributes = resolve_required_attributes(
            genre_id=111120,
            attr_names=[
                "\u30ab\u30e9\u30fc",
                "\u30b7\u30ea\u30fc\u30ba\u540d",
                "\u30d6\u30e9\u30f3\u30c9\u540d",
                "\u30e1\u30fc\u30ab\u30fc\u578b\u756a",
                "\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd",
            ],
            resolved_fields=resolved_fields,
            keepa_result=keepa,
            amazon_result=self.amazon,
            asin=keepa.asin,
        )
        self.assertEqual(resolved_attributes["\u30d6\u30e9\u30f3\u30c9\u540d"].value, "A\u00edam")
        self.assertEqual(resolved_attributes["\u30d6\u30e9\u30f3\u30c9\u540d"].resolution_action, "use_actual")
        self.assertEqual(resolved_attributes["\u30b7\u30ea\u30fc\u30ba\u540d"].value, "chapter")
        self.assertEqual(resolved_attributes["\u30b7\u30ea\u30fc\u30ba\u540d"].resolution_action, "use_inferred")
        self.assertEqual(resolved_attributes["\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd"].value, "\u65e5\u672c\u88fd")
        self.assertEqual(resolved_attributes["\u30ab\u30e9\u30fc"].value, "-")
        self.assertEqual(resolved_attributes["\u30ab\u30e9\u30fc"].resolution_action, "use_legacy_dash")
        self.assertEqual(resolved_attributes["\u30e1\u30fc\u30ab\u30fc\u578b\u756a"].value, "-")
        self.assertEqual(resolved_attributes["\u30e1\u30fc\u30ab\u30fc\u578b\u756a"].resolution_action, "use_legacy_dash")

    def test_series_name_uses_legacy_dash_when_no_explicit_phrase_exists(self) -> None:
        keepa = KeepaProductData(
            **{
                **self.keepa.__dict__,
                "category_id": 5263237051,
                "features": ["chapter65 \u306e\u9999\u308a"],
                "style": "",
                "title": "chapter65 item",
            }
        )
        resolved_fields = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master_actual_mapping,
        )
        resolved_attributes = resolve_required_attributes(
            genre_id=111120,
            attr_names=["\u30b7\u30ea\u30fc\u30ba\u540d"],
            resolved_fields=resolved_fields,
            keepa_result=keepa,
            amazon_result=self.amazon,
            asin=keepa.asin,
        )
        self.assertEqual(resolved_attributes["\u30b7\u30ea\u30fc\u30ba\u540d"].value, "-")
        self.assertEqual(resolved_attributes["\u30b7\u30ea\u30fc\u30ba\u540d"].resolution_action, "use_legacy_dash")

    def test_country_of_origin_requires_exact_nihonsei(self) -> None:
        amazon = AmazonCheckResult(**{**self.amazon.__dict__, "title": "Amazon \u65e5\u672c\u5411\u3051 \u30c6\u30b9\u30c8"})
        keepa = KeepaProductData(
            **{
                **self.keepa.__dict__,
                "category_id": 5263237051,
                "title": "Keepa \u65e5\u672c\u5411\u3051",
                "description": "\u65e5\u672c\u5411\u3051\u8aac\u660e",
            }
        )
        resolved_fields = build_resolved_fields(
            amazon_result=amazon,
            keepa_result=keepa,
            master_data=self.master_actual_mapping,
        )
        resolved_attributes = resolve_required_attributes(
            genre_id=111120,
            attr_names=["\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd"],
            resolved_fields=resolved_fields,
            keepa_result=keepa,
            amazon_result=amazon,
            asin=keepa.asin,
        )
        self.assertEqual(resolved_attributes["\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd"].value, "-")
        self.assertEqual(resolved_attributes["\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd"].resolution_action, "use_legacy_dash")

    def test_legacy_dash_fills_unresolved_attributes_for_other_genres(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "model": "", "part_number": ""})
        resolved_fields = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        resolved_attributes = resolve_required_attributes(
            genre_id=101737,
            attr_names=self.master.attribute_definitions[101737],
            resolved_fields=resolved_fields,
            keepa_result=keepa,
            amazon_result=self.amazon,
            asin=keepa.asin,
        )
        self.assertEqual(resolved_attributes["\u30e1\u30fc\u30ab\u30fc\u578b\u756a"].value, "-")
        self.assertEqual(resolved_attributes["\u30e1\u30fc\u30ab\u30fc\u578b\u756a"].resolution_action, "use_legacy_dash")

    def test_numeric_or_unit_attribute_does_not_use_legacy_dash(self) -> None:
        keepa = KeepaProductData(**{**self.keepa.__dict__, "size": ""})
        resolved_fields = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=self.master,
        )
        resolved_attributes = resolve_required_attributes(
            genre_id=101737,
            attr_names=["\u7dcf\u672c\u6570", "\u5358\u54c1\u5bb9\u91cf"],
            resolved_fields=resolved_fields,
            keepa_result=keepa,
            amazon_result=self.amazon,
            asin=keepa.asin,
        )
        self.assertIsNone(resolved_attributes["\u7dcf\u672c\u6570"].value)
        self.assertEqual(resolved_attributes["\u7dcf\u672c\u6570"].resolution_action, "needs_review")
        self.assertIsNone(resolved_attributes["\u5358\u54c1\u5bb9\u91cf"].value)
        self.assertEqual(resolved_attributes["\u5358\u54c1\u5bb9\u91cf"].resolution_action, "needs_review")

    def test_genre_213661_representative_color_reuses_keepa_color(self) -> None:
        master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={2189601051: 213661},
            attribute_definitions={213661: ["ブランド名", "メーカー型番", "代表カラー"]},
            missing_files=[],
        )
        keepa = KeepaProductData(
            **{
                **self.keepa.__dict__,
                "category_id": 2189601051,
                "brand": "ビバリー(BEVERLY)",
                "manufacturer": "ビバリー(BEVERLY)",
                "model": "SF031CEL",
                "part_number": "SF031CEL",
                "color": "クリアブルーラメ",
                "avg90_new_offer_count": 4.0,
            }
        )
        resolved_fields = build_resolved_fields(
            amazon_result=self.amazon,
            keepa_result=keepa,
            master_data=master,
        )
        resolved_attributes = resolve_required_attributes(
            genre_id=213661,
            attr_names=["ブランド名", "メーカー型番", "代表カラー"],
            resolved_fields=resolved_fields,
            keepa_result=keepa,
            amazon_result=self.amazon,
            asin=keepa.asin,
        )
        self.assertEqual(resolved_attributes["代表カラー"].value, "クリアブルーラメ")
        self.assertEqual(resolved_attributes["代表カラー"].source, "keepa")
        self.assertEqual(resolved_attributes["代表カラー"].resolution_action, "use_actual")

    def test_evaluator_and_payload_share_resolved_attributes_for_genre_111120(self) -> None:
        amazon = AmazonCheckResult(**{**self.amazon.__dict__, "requested_asin": "B0CJR955SM", "page_asin": "B0CJR955SM"})
        keepa = KeepaProductData(
            **{
                **self.keepa.__dict__,
                "asin": "B0CJR955SM",
                "brand": "A\u00edam",
                "manufacturer": "Aiam",
                "model": "",
                "part_number": "",
                "color": "",
                "title": "Aiam item \u65e5\u672c\u88fd",
                "features": [
                    "\u3042\u306a\u305f\u306e\u4eba\u751f\u306b\u5bc4\u308a\u6dfb\u3046\u300cchapter\uff08\u9999\u308a\uff09\u300d\u30b7\u30ea\u30fc\u30ba\u306f\u51688\u7a2e\u985e"
                ],
                "category_id": 5263237051,
                "avg90_seller_count": 4.2,
            }
        )
        master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={5263237051: 111120},
            attribute_definitions={
                111120: [
                    "\u30ab\u30e9\u30fc",
                    "\u30b7\u30ea\u30fc\u30ba\u540d",
                    "\u30d6\u30e9\u30f3\u30c9\u540d",
                    "\u30e1\u30fc\u30ab\u30fc\u578b\u756a",
                    "\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd",
                ]
            },
            missing_files=[],
        )
        evaluation = evaluate_listing(
            asin="B0CJR955SM",
            amazon_result=amazon,
            keepa_result=keepa,
            master_data=master,
            store_settings=self.store,
            management_number="20250101010101_187_ab12",
        )
        self.assertEqual(evaluation.listing_status, "eligible")
        self.assertEqual(
            [item["name"] for item in evaluation.attributes],
            [
                "\u30ab\u30e9\u30fc",
                "\u30b7\u30ea\u30fc\u30ba\u540d",
                "\u30d6\u30e9\u30f3\u30c9\u540d",
                "\u30e1\u30fc\u30ab\u30fc\u578b\u756a",
                "\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd",
            ],
        )
        self.assertEqual(evaluation.resolved_attributes["\u30ab\u30e9\u30fc"].value, "-")
        self.assertEqual(evaluation.resolved_attributes["\u30e1\u30fc\u30ab\u30fc\u578b\u756a"].value, "-")
        self.assertEqual(evaluation.resolved_attributes["\u30b7\u30ea\u30fc\u30ba\u540d"].value, "chapter")
        self.assertEqual(evaluation.attributes[0]["value"], evaluation.resolved_attributes["\u30ab\u30e9\u30fc"].value)

    def test_saved_raw_b0cjr955sm_matches_expected_resolution(self) -> None:
        raw_path = ROOT_DIR / "output" / "keepa_inspect" / "B0CJR955SM_raw.json"
        raw_response = json.loads(raw_path.read_text(encoding="utf-8"))
        product = raw_response["products"][0]
        keepa = KeepaProductData(
            asin=product["asin"],
            title="Aiam アイアム ボディフレグランスミスト チャプター65 60mL オーデコロン フレグランス ボディミスト 日本製",
            brand="Aíam",
            manufacturer="Aiam",
            ean="4589642981374",
            image_urls=[
                "https://m.media-amazon.com/images/I/419M6DWuQVL.jpg",
                "https://m.media-amazon.com/images/I/510HdMwr3fL.jpg",
                "https://m.media-amazon.com/images/I/51CB1qOWXUL.jpg",
                "https://m.media-amazon.com/images/I/51zXOCzodWL.jpg",
            ],
            image_source="keepa_images",
            category_id=5263237051,
            size="60mL",
            current_new_offer_count=1,
            avg90_new_offer_count=1.0,
            hazardous_materials=["ETHANOL", "UN1170", "II", "3"],
            is_heat_sensitive=False,
            scent="chapter65",
            is_adult=False,
            is_adult_source="isAdultProduct",
        )
        resolved = build_resolved_fields(
            amazon_result=None,
            keepa_result=keepa,
            master_data=self.master_actual_mapping,
        )
        self.assertEqual(resolved["brand"].value, "Aíam")
        self.assertFalse(resolved["brand"].fallback_used)
        self.assertEqual(resolved["genre_id"].value, 111120)
        self.assertEqual(resolved["main_image"].value, "https://m.media-amazon.com/images/I/419M6DWuQVL.jpg")
        self.assertEqual(resolved["image_source"].value, "keepa_images")
        self.assertEqual(resolved["current_new_offer_count"].value, 1)
        self.assertEqual(resolved["avg90_new_offer_count"].value, 1.0)
        self.assertEqual(resolved["country_of_origin_candidate"].confidence, "medium")


if __name__ == "__main__":
    unittest.main()
