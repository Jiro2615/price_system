from __future__ import annotations

import unittest
from pathlib import Path

from scripts.listing.models import (
    AmazonCheckResult,
    EvaluationResult,
    KeepaProductData,
    MasterData,
    StoreSettings,
)
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


class ListingPrepareFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = PrepareListingRequest(
            asin="B000TEST01",
            store_code="rakuten_1",
            master_dir=Path("C:/dummy/master"),
            dry_run=True,
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
        self.master = MasterData(
            blacklist=set(),
            kako_ng={},
            replacements=[],
            prohibited_words_rakuten=[],
            prohibited_words_other=[],
            listed_asins={},
            category_map={10219786051: 101737},
            attribute_definitions={101737: ["ブランド名", "メーカー型番"]},
            missing_files=[],
        )
        self.amazon_ok = AmazonCheckResult(
            requested_asin="B000TEST01",
            page_asin="B000TEST01",
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
        self.amazon_ng = AmazonCheckResult(
            requested_asin="B000TEST01",
            page_asin="B000TEST01",
            title="Amazon商品タイトル",
            amazon_price=2000,
            available_qty=9,
            gift_available=False,
            shipping_status="gift disabled",
            business_ng=True,
            system_error=False,
            ng_reason="Amazonギフト設定が無効です",
            current_url="",
        )
        self.amazon_system_error = AmazonCheckResult(
            requested_asin="B000TEST01",
            page_asin="B000TEST01",
            title="Amazon商品タイトル",
            amazon_price=None,
            available_qty=None,
            gift_available=None,
            shipping_status="",
            business_ng=False,
            system_error=True,
            ng_reason="Amazon確認でシステムエラー",
            current_url="",
        )
        self.keepa = KeepaProductData(
            asin="B000TEST01",
            title="Keepa商品タイトル",
            brand="テストブランド",
            model="MODEL-1",
            ean="1234567890123",
            images_csv="abc123,def456",
            category_id=10219786051,
            features=["特徴1", "特徴2"],
            description="商品説明テキスト",
            style="スタイルA",
            size="L",
            color="ブラック",
            avg90_seller_count=4.2,
            is_adult=False,
        )

    def _store_loader(self, store_code: str) -> StoreSettings:
        self.assertEqual(store_code, "rakuten_1")
        return self.store

    def _master_loader(self, master_dir: Path, allow_missing: bool) -> MasterData:
        self.assertEqual(master_dir, Path("C:/dummy/master"))
        self.assertFalse(allow_missing)
        return self.master

    def test_already_listed_skips_external_calls(self) -> None:
        master = MasterData(**{**self.master.__dict__, "listed_asins": {"B00A25RH18": "20241117070745_187"}})
        request = PrepareListingRequest(
            asin="B00A25RH18",
            store_code="rakuten_1",
            master_dir=Path("C:/dummy/master"),
            dry_run=True,
        )

        def fail_amazon_fetcher(asin: str, page_timeout_ms: int) -> AmazonCheckResult:
            raise AssertionError("already listed path must not call Amazon")

        def fail_keepa_fetcher(asin: str) -> KeepaProductData:
            raise AssertionError("already listed path must not call Keepa")

        def fail_resolved_fields_builder(**kwargs: object) -> dict[str, object]:
            raise AssertionError("already listed path must not build resolved fields")

        def fail_evaluator(**kwargs: object) -> EvaluationResult:
            raise AssertionError("already listed path must not call evaluator")

        def fail_management_builder(suffix: str) -> object:
            raise AssertionError("already listed path must not generate management number")

        def fail_item_builder(**kwargs: object) -> dict[str, object]:
            raise AssertionError("already listed path must not build item payload")

        def fail_inventory_builder(**kwargs: object) -> dict[str, object]:
            raise AssertionError("already listed path must not build inventory payload")

        result = prepare_listing(
            request,
            store_settings_loader=self._store_loader,
            master_data_loader=lambda master_dir, allow_missing: master,
            amazon_fetcher=fail_amazon_fetcher,
            keepa_fetcher=fail_keepa_fetcher,
            resolved_fields_builder=fail_resolved_fields_builder,
            evaluator=fail_evaluator,
            management_number_builder=fail_management_builder,
            item_payload_builder=fail_item_builder,
            inventory_payload_builder=fail_inventory_builder,
        )

        self.assertEqual(result["listing_status"], "already_listed")
        self.assertEqual(result["listing_reason"], "既に出品済み: 20241117070745_187")
        self.assertIsNone(result["management_number"])
        self.assertEqual(result["existing_management_number"], "20241117070745_187")
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])
        self.assertIsNone(result["resolved_fields"])

    def test_amazon_business_ng_skips_keepa_and_followups(self) -> None:
        calls: list[str] = []

        def amazon_fetcher(asin: str, page_timeout_ms: int) -> AmazonCheckResult:
            calls.append("amazon")
            return self.amazon_ng

        def fail_keepa_fetcher(asin: str) -> KeepaProductData:
            raise AssertionError("Amazon business NG must skip Keepa")

        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=amazon_fetcher,
            keepa_fetcher=fail_keepa_fetcher,
            resolved_fields_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build resolved fields")),
            evaluator=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not call evaluator")),
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(calls, ["amazon"])
        self.assertEqual(result["listing_status"], "business_ng")
        self.assertEqual(result["listing_reason"], "Amazonギフト設定が無効です")
        self.assertIsNone(result["keepa_result"])
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_amazon_system_error_skips_keepa_and_followups(self) -> None:
        def fail_keepa_fetcher(asin: str) -> KeepaProductData:
            raise AssertionError("Amazon system error must skip Keepa")

        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon_system_error,
            keepa_fetcher=fail_keepa_fetcher,
            resolved_fields_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build resolved fields")),
            evaluator=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not call evaluator")),
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(result["listing_status"], "system_error")
        self.assertEqual(result["listing_reason"], "Amazon確認でシステムエラー")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_keepa_missing_does_not_generate_management_number_or_payload(self) -> None:
        calls: list[str] = []

        def resolved_fields_builder(**kwargs: object) -> dict[str, object]:
            calls.append("resolved_fields")
            self.assertIsNone(kwargs["keepa_result"])
            return {"status": "resolved"}

        def evaluator(**kwargs: object) -> EvaluationResult:
            calls.append("evaluator")
            self.assertIsNone(kwargs["keepa_result"])
            return EvaluationResult("missing_required_data", "Keepa結果がありません")

        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon_ok,
            keepa_fetcher=lambda asin: None,
            resolved_fields_builder=resolved_fields_builder,
            evaluator=evaluator,
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(calls, ["resolved_fields", "evaluator"])
        self.assertEqual(result["listing_status"], "missing_required_data")
        self.assertEqual(result["listing_reason"], "Keepa結果がありません")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_keepa_exception_is_classified_as_system_error(self) -> None:
        def keepa_fetcher(asin: str) -> KeepaProductData:
            raise RuntimeError("Keepa timeout while fetching product")

        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon_ok,
            keepa_fetcher=keepa_fetcher,
            resolved_fields_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build resolved fields")),
            evaluator=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not call evaluator")),
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(result["listing_status"], "system_error")
        self.assertEqual(result["listing_reason"], "Keepa timeout while fetching product")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_keepa_explicit_error_result_is_classified_as_system_error(self) -> None:
        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon_ok,
            keepa_fetcher=lambda asin: {"system_error": True, "ng_reason": "Keepa API error response"},
            resolved_fields_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build resolved fields")),
            evaluator=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not call evaluator")),
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(result["listing_status"], "system_error")
        self.assertEqual(result["listing_reason"], "Keepa API error response")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_keepa_no_products_exception_is_classified_as_missing_required_data(self) -> None:
        def keepa_fetcher(asin: str) -> KeepaProductData:
            raise RuntimeError(f"Keepa returned no products for ASIN: {asin}")

        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon_ok,
            keepa_fetcher=keepa_fetcher,
            resolved_fields_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build resolved fields")),
            evaluator=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not call evaluator")),
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(result["listing_status"], "missing_required_data")
        self.assertEqual(result["listing_reason"], "Keepa returned no products for ASIN: B000TEST01")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_noneligible_missing_required_data_skips_management_and_payload(self) -> None:
        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon_ok,
            keepa_fetcher=lambda asin: self.keepa,
            resolved_fields_builder=lambda **kwargs: {"status": "resolved"},
            evaluator=lambda **kwargs: EvaluationResult("missing_required_data", "属性不足"),
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(result["listing_status"], "missing_required_data")
        self.assertEqual(result["listing_reason"], "属性不足")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_noneligible_other_status_skips_management_and_payload(self) -> None:
        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=lambda asin, page_timeout_ms: self.amazon_ok,
            keepa_fetcher=lambda asin: self.keepa,
            resolved_fields_builder=lambda **kwargs: {"status": "resolved"},
            evaluator=lambda **kwargs: EvaluationResult("unknown_category", "カテゴリ未対応"),
            management_number_builder=lambda suffix: (_ for _ in ()).throw(AssertionError("must not generate management number")),
            item_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build item payload")),
            inventory_payload_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not build inventory payload")),
        )

        self.assertEqual(result["listing_status"], "unknown_category")
        self.assertEqual(result["listing_reason"], "カテゴリ未対応")
        self.assertIsNone(result["management_number"])
        self.assertIsNone(result["item_payload"])
        self.assertIsNone(result["inventory_payload"])

    def test_eligible_generates_management_number_after_evaluator_and_builds_payloads(self) -> None:
        calls: list[str] = []

        def amazon_fetcher(asin: str, page_timeout_ms: int) -> AmazonCheckResult:
            calls.append("amazon")
            return self.amazon_ok

        def keepa_fetcher(asin: str) -> KeepaProductData:
            calls.append("keepa")
            return self.keepa

        def resolved_fields_builder(**kwargs: object) -> dict[str, object]:
            calls.append("resolved_fields")
            return {"title": {"value": "Amazon商品タイトル"}}

        def evaluator(**kwargs: object) -> EvaluationResult:
            calls.append("evaluator")
            return EvaluationResult(
                "eligible",
                "出品可能",
                title="Amazon商品タイトル",
                description_pc="pc",
                description_sp="sp",
                genre_id=101737,
                attributes=[{"name": "ブランド名", "value": "テストブランド"}],
                article_number="1234567890123",
                image_candidates=[{"source": "https://m.media-amazon.com/images/I/abc123.jpg", "target": "/generated_1.jpg"}],
            )

        class FakeBundle:
            selected = "20260708120000_187_ab12"
            legacy_candidate = "20260708120000_187"
            safe_candidate = "20260708120000_187_ab12"
            note = "test"

        def management_builder(suffix: str) -> FakeBundle:
            calls.append("management_number")
            self.assertEqual(suffix, "187")
            return FakeBundle()

        def item_builder(**kwargs: object) -> dict[str, object]:
            calls.append("item_payload")
            self.assertEqual(kwargs["management_number"], "20260708120000_187_ab12")
            return {"itemNumber": kwargs["management_number"]}

        def inventory_builder(**kwargs: object) -> dict[str, object]:
            calls.append("inventory_payload")
            self.assertEqual(kwargs["management_number"], "20260708120000_187_ab12")
            return {"quantity": 4}

        result = prepare_listing(
            self.request,
            store_settings_loader=self._store_loader,
            master_data_loader=self._master_loader,
            amazon_fetcher=amazon_fetcher,
            keepa_fetcher=keepa_fetcher,
            resolved_fields_builder=resolved_fields_builder,
            evaluator=evaluator,
            management_number_builder=management_builder,
            item_payload_builder=item_builder,
            inventory_payload_builder=inventory_builder,
        )

        self.assertEqual(
            calls,
            ["amazon", "keepa", "resolved_fields", "evaluator", "management_number", "item_payload", "inventory_payload"],
        )
        self.assertEqual(result["listing_status"], "eligible")
        self.assertEqual(result["management_number"], "20260708120000_187_ab12")
        self.assertEqual(result["item_payload"], {"itemNumber": "20260708120000_187_ab12"})
        self.assertEqual(result["inventory_payload"], {"quantity": 4})
        self.assertEqual(result["resolved_fields"]["title"]["value"], "Amazon商品タイトル")


if __name__ == "__main__":
    unittest.main()
