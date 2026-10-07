import unittest
from unittest.mock import patch

from scripts.listing.rakuten_marketplace_policy import _item_mentions_exact_jan, rakuten_marketplace_evidence


def item(shop: str, name: str, caption: str = "") -> dict[str, str]:
    return {
        "shopCode": shop,
        "shopName": f"{shop}店",
        "itemName": name,
        "itemCaption": caption,
        "itemCode": name,
    }


class RakutenMarketplaceEvidenceTests(unittest.TestCase):
    def test_configured_shop_threshold_changes_acceptance(self) -> None:
        jan = "4900000000001"
        matches = [item("shop-a", "テスト商品", jan), item("shop-b", "テスト商品", jan)]
        for minimum, accepted in ((1, True), (2, True), (3, False), (5, False), (30, False)):
            with self.subTest(minimum=minimum), patch(
                "scripts.listing.rakuten_marketplace_policy._search_items", side_effect=[matches, []],
            ):
                evidence = rakuten_marketplace_evidence(jan_code=jan, title="テスト商品", minimum_shops=minimum)
                self.assertEqual(evidence["accepted"], accepted)
                self.assertEqual(evidence["minimum_shops"], minimum)
                self.assertEqual(evidence["confirmed_shop_count"], 2)

    def test_exact_jan_counts_independent_shops_not_item_rows(self) -> None:
        jan = "4900000000001"
        matches = [
            item("shop-a", "テスト商品 80g", jan),
            item("shop-a", "テスト商品 80g 2個", jan),
            item("shop-b", "テスト商品 80g", jan),
        ]
        with patch(
            "scripts.listing.rakuten_marketplace_policy._search_items",
            side_effect=lambda query, timeout, **kwargs: matches if query == jan else [],
        ):
            evidence = rakuten_marketplace_evidence(
                jan_code=jan,
                title="テストブランド テスト商品 80g",
                brand="テストブランド",
                minimum_shops=5,
            )
        assert evidence is not None
        self.assertFalse(evidence["accepted"])
        self.assertEqual(evidence["jan_exact_shop_count"], 2)
        self.assertEqual(evidence["confirmed_shop_count"], 2)

    def test_high_confidence_text_matches_can_complete_missing_jan_evidence(self) -> None:
        title = "テストブランド モイストクリーム 80g 2個"
        text_matches = [item(f"shop-{index}", title) for index in range(1, 6)]
        with patch(
            "scripts.listing.rakuten_marketplace_policy._search_items",
            side_effect=[[], text_matches],
        ):
            evidence = rakuten_marketplace_evidence(
                jan_code="4900000000001",
                title=title,
                brand="テストブランド",
                minimum_shops=5,
            )
        assert evidence is not None
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["jan_exact_shop_count"], 0)
        self.assertEqual(evidence["text_match_shop_count"], 5)
        self.assertEqual(evidence["confirmed_shop_count"], 5)

    def test_text_match_rejects_a_different_capacity(self) -> None:
        title = "テストブランド モイストクリーム 80g 2個"
        wrong_variants = [item(f"shop-{index}", "テストブランド モイストクリーム 100g 2個") for index in range(1, 6)]
        with patch(
            "scripts.listing.rakuten_marketplace_policy._search_items",
            side_effect=lambda query, timeout, **kwargs: [] if query == "4900000000001" else wrong_variants,
        ):
            evidence = rakuten_marketplace_evidence(
                jan_code="4900000000001",
                title=title,
                brand="テストブランド",
                minimum_shops=5,
            )
        assert evidence is not None
        self.assertFalse(evidence["accepted"])
        self.assertEqual(evidence["text_match_shop_count"], 0)

    def test_jan_does_not_match_merged_numbers_or_longer_codes(self):
        self.assertFalse(_item_mentions_exact_jan(item("shop", "49000 00000001"), "4900000000001"))
        self.assertFalse(_item_mentions_exact_jan(item("shop", "149000000000019"), "4900000000001"))
        self.assertTrue(_item_mentions_exact_jan(item("shop", "JAN：４９００００００００００１"), "4900000000001"))

    def test_exact_jan_counts_other_packs_but_not_wrong_capacity(self):
        jan, title = "4900000000001", "テストブランド プロテイン 3kg"
        candidates = [item("a", "テストブランド プロテイン 500g", jan),
                      item("b", "テストブランド プロテイン 3kg 2個セット", jan),
                      item("c", title, jan)]
        with patch("scripts.listing.rakuten_marketplace_policy._search_items", side_effect=[candidates, []]):
            evidence = rakuten_marketplace_evidence(jan_code=jan, title=title, minimum_shops=2)
        self.assertEqual(evidence["confirmed_shop_count"], 2)
        self.assertTrue(evidence["accepted"])
        self.assertFalse(evidence["pack_count_required"])

    def test_caption_with_all_capacities_cannot_prove_the_title_match(self):
        title = "テストブランド プロテイン 3kg"
        candidates = [item("a", "テストブランド プロテイン 500g", "選べる容量 500g 3kg")]
        with patch("scripts.listing.rakuten_marketplace_policy._search_items", return_value=candidates):
            evidence = rakuten_marketplace_evidence(jan_code="", title=title, brand="テストブランド", minimum_shops=1)
        self.assertEqual(evidence["confirmed_shop_count"], 0)

    def test_reference_minimum_excludes_ranged_sku_prices_and_wrong_goods(self):
        jan, title = "4900000000001", "テストブランド プロテイン 3kg"
        ranged = {**item("a", title, jan), "itemPrice": 1280, "itemPriceMin1": 1280, "itemPriceMax1": 9000}
        good = {**item("b", title, jan), "itemPrice": 8500, "itemPriceMin1": 8500, "itemPriceMax1": 8500,
                "itemUrl": "https://item.rakuten.co.jp/b/item/"}
        wrong = {**item("c", "テストブランド ボディソープ 500ml", jan), "itemPrice": 400}
        for row in (ranged, good, wrong):
            row.update(availability=1, postageFlag=0, taxFlag=0)
        with patch("scripts.listing.rakuten_marketplace_policy._search_items", return_value=[ranged, good, wrong]):
            evidence = rakuten_marketplace_evidence(jan_code=jan, title=title, minimum_shops=1)
        self.assertEqual(evidence["reference_min_price"], 8500)
        self.assertEqual(evidence["ambiguous_price_items_excluded"], 1)
        self.assertIn("全商品の最安保証なし", evidence["reference_price_scope"])

    def test_unknown_capacity_has_no_reference_price_even_when_jan_exists(self):
        jan = "4900000000001"
        candidate = {**item("a", "テストブランド プロテイン", jan),
                     "itemPrice": 1000, "availability": 1, "postageFlag": 0, "taxFlag": 0}
        with patch("scripts.listing.rakuten_marketplace_policy._search_items", return_value=[candidate]):
            evidence = rakuten_marketplace_evidence(jan_code=jan, title="テストブランド プロテイン 3kg", minimum_shops=1)
        self.assertTrue(evidence["accepted"])
        self.assertIsNone(evidence["reference_min_price"])
        self.assertEqual(evidence["unidentified_variant_price_items_excluded"], 1)

    def test_storage_capacity_mismatch_is_not_a_comparable_product(self):
        jan = "4900000000001"
        wrong = item("a", "テストブランド SSD 256GB", jan)
        with patch("scripts.listing.rakuten_marketplace_policy._search_items", side_effect=lambda query, timeout, **kwargs: [wrong] if query == jan else []):
            evidence = rakuten_marketplace_evidence(jan_code=jan, title="テストブランド SSD 1TB", brand="テストブランド", minimum_shops=1)
        self.assertFalse(evidence["accepted"])

    def test_missing_sku_price_range_is_not_assumed_to_be_one_price(self):
        jan, title = "4900000000001", "テストブランド 商品 80g"
        candidate = {**item("a", title, jan), "itemPrice": 1000, "availability": 1, "postageFlag": 0, "taxFlag": 0}
        with patch("scripts.listing.rakuten_marketplace_policy._search_items", return_value=[candidate]):
            evidence = rakuten_marketplace_evidence(jan_code=jan, title=title, minimum_shops=1)
        self.assertTrue(evidence["accepted"])
        self.assertIsNone(evidence["reference_min_price"])
        self.assertEqual(evidence["ambiguous_price_items_excluded"], 1)

    def test_model_in_compatibility_caption_does_not_rescue_wrong_model(self):
        candidate = item("a", "テストブランド 製品 MODEL-2", "MODEL-1にも対応しています")
        with patch("scripts.listing.rakuten_marketplace_policy._search_items", return_value=[candidate]):
            evidence = rakuten_marketplace_evidence(jan_code="", title="テストブランド 製品 MODEL-1",
                brand="テストブランド", model="MODEL-1", minimum_shops=1)
        self.assertFalse(evidence["accepted"])


if __name__ == "__main__":
    unittest.main()
