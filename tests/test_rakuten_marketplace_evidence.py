import unittest
from unittest.mock import patch

from scripts.listing.rakuten_marketplace_policy import rakuten_marketplace_evidence


def item(shop: str, name: str, caption: str = "") -> dict[str, str]:
    return {
        "shopCode": shop,
        "shopName": f"{shop}店",
        "itemName": name,
        "itemCaption": caption,
        "itemCode": name,
    }


class RakutenMarketplaceEvidenceTests(unittest.TestCase):
    def test_exact_jan_counts_independent_shops_not_item_rows(self) -> None:
        jan = "4900000000001"
        matches = [
            item("shop-a", "テスト商品 80g", jan),
            item("shop-a", "テスト商品 80g 2個", jan),
            item("shop-b", "テスト商品 80g", jan),
        ]
        with patch(
            "scripts.listing.rakuten_marketplace_policy._search_items",
            side_effect=[matches, []],
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
            side_effect=[[], wrong_variants],
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


if __name__ == "__main__":
    unittest.main()
