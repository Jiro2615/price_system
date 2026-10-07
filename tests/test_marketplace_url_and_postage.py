"""JAN URL evidence and postage-independent shop counting; no live access."""
import unittest
from unittest.mock import patch

from scripts.listing import rakuten_marketplace_policy as policy


JAN = "4900000000001"
TITLE = "テストブランド クリーム 80g"


def item(shop, *, name=TITLE, jan_in_text=False, postage=1, price=None):
    row = {"shopCode": shop, "shopName": shop, "itemCode": shop + ":item",
           "itemName": name, "itemCaption": JAN if jan_in_text else "",
           "itemUrl": f"https://item.rakuten.co.jp/{shop}/{JAN}-1pk/",
           "availability": 1, "postageFlag": postage, "taxFlag": 0}
    if price is not None:
        row.update(itemPrice=price, itemPriceMin1=price, itemPriceMax1=price)
    return row


class MarketplaceUrlAndPostageTests(unittest.TestCase):
    def test_jan_in_trusted_product_slug_is_explicit_evidence(self):
        row = item("shop")
        self.assertTrue(policy._item_mentions_exact_jan(row, JAN))
        self.assertEqual(policy._jan_evidence_sources(row, JAN), ["itemUrl_path"])

    def test_encoded_jan_path_is_decoded_without_merging_digits(self):
        row = item("shop")
        row["itemUrl"] = "https://item.rakuten.co.jp/shop/" + "".join(f"%{ord(c):02x}" for c in JAN) + "/"
        self.assertTrue(policy._item_mentions_exact_jan(row, JAN))
        for slug in ("149000000000019", "49000%20" + "00000001"):
            row["itemUrl"] = f"https://item.rakuten.co.jp/shop/{slug}/"
            self.assertFalse(policy._item_mentions_exact_jan(row, JAN))

    def test_query_fragment_and_shop_segment_are_not_product_jan_evidence(self):
        row = item("shop")
        for url in (f"https://item.rakuten.co.jp/shop/item/?keyword={JAN}",
                    f"https://item.rakuten.co.jp/shop/item/#{JAN}",
                    f"https://item.rakuten.co.jp/{JAN}/item/"):
            with self.subTest(url=url):
                row["itemUrl"] = url
                self.assertFalse(policy._item_mentions_exact_jan(row, JAN))

    def test_untrusted_hosts_userinfo_ports_and_mismatched_shops_are_rejected(self):
        row = item("shop")
        for url in (f"https://item.rakuten.co.jp.evil.example/shop/{JAN}/",
                    f"https://example.com/shop/{JAN}/",
                    f"https://user:password@item.rakuten.co.jp/shop/{JAN}/",
                    f"https://item.rakuten.co.jp:444/shop/{JAN}/",
                    f"https://item.rakuten.co.jp:invalid/shop/{JAN}/",
                    f"https://item.rakuten.co.jp/another-shop/{JAN}/",
                    f"//item.rakuten.co.jp/shop/{JAN}/",
                    f"https://[broken/shop/{JAN}/"):
            with self.subTest(url=url):
                row["itemUrl"] = url
                self.assertFalse(policy._item_mentions_exact_jan(row, JAN))

    def test_invalid_url_does_not_discard_jan_attested_in_text(self):
        row = item("shop", jan_in_text=True)
        row["itemUrl"] = "https://[broken"
        self.assertTrue(policy._item_mentions_exact_jan(row, JAN))
        self.assertEqual(policy._jan_evidence_sources(row, JAN), ["itemCaption"])

    def test_paid_shipping_jan_matches_count_shops_and_skip_fallback(self):
        rows = [item("a"), item("b"), item("b", name=TITLE + " 2個セット")]
        with patch.object(policy, "_search_items", return_value=rows) as search:
            evidence = policy.rakuten_marketplace_evidence(jan_code=JAN, title=TITLE, minimum_shops=2)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["jan_exact_shop_count"], 2)
        self.assertEqual(evidence["confirmed_shop_count"], 2)
        self.assertEqual(evidence["search_attempts"][0]["jan_url_match_count"], 3)
        self.assertFalse(evidence["postage_included_required"])
        search.assert_called_once_with(JAN, 15.0, postage_included=False)

    def test_paid_shipping_text_matches_count_when_jan_is_missing(self):
        rows = [item("a"), item("b", name=TITLE + " 2個セット")]
        for row in rows:
            row["itemUrl"] = f"https://item.rakuten.co.jp/{row['shopCode']}/plain-item/"
        with patch.object(policy, "_search_items", return_value=rows) as search:
            evidence = policy.rakuten_marketplace_evidence(jan_code="", title=TITLE,
                brand="テストブランド", minimum_shops=2)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["text_match_shop_count"], 2)
        self.assertTrue(all(call.kwargs == {"postage_included": False} for call in search.call_args_list))

    def test_jan_in_a_text_search_result_is_classified_as_jan_evidence(self):
        row = item("a", name="販促文を含む短いタイトル")
        with patch.object(policy, "_search_items", side_effect=[[], [row]]) as search:
            evidence = policy.rakuten_marketplace_evidence(jan_code=JAN, title=TITLE,
                brand="テストブランド", minimum_shops=1)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["source"], "jan_exact")
        self.assertEqual(evidence["jan_exact_shop_count"], 1)
        self.assertEqual(evidence["text_match_shop_count"], 0)
        self.assertEqual(evidence["search_attempts"][-1]["jan_url_match_count"], 1)
        self.assertEqual(search.call_count, 2)

    def test_unavailable_and_different_capacity_do_not_pass_url_jan(self):
        unavailable = dict(item("a"), availability=0)
        wrong_capacity = item("b", name="テストブランド クリーム 100g")
        with patch.object(policy, "_search_items", return_value=[unavailable, wrong_capacity]):
            evidence = policy.rakuten_marketplace_evidence(jan_code=JAN, title=TITLE,
                brand="テストブランド", minimum_shops=1)
        self.assertFalse(evidence["accepted"])
        self.assertEqual(evidence["confirmed_shop_count"], 0)
        self.assertEqual(evidence["search_attempts"][0]["rejected_counts"],
                         {"unavailable": 1, "capacity_or_spec_mismatch": 1})

    def test_reference_minimum_still_excludes_paid_shipping(self):
        rows = [item("paid", price=100), item("free", postage=0, price=900)]
        with patch.object(policy, "_search_items", return_value=rows):
            evidence = policy.rakuten_marketplace_evidence(jan_code=JAN, title=TITLE, minimum_shops=2)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["reference_min_price"], 900)
        self.assertEqual(evidence["reference_price_candidate_count"], 1)

    def test_only_paid_shipping_evidence_has_no_reference_minimum(self):
        with patch.object(policy, "_search_items", return_value=[item("a", price=100)]):
            evidence = policy.rakuten_marketplace_evidence(jan_code=JAN, title=TITLE, minimum_shops=1)
        self.assertTrue(evidence["accepted"])
        self.assertIsNone(evidence["reference_min_price"])

    def test_default_variant_guard_remains_postage_sensitive(self):
        row = item("a")
        self.assertEqual(policy._variant_rejection_reason(row, TITLE), "shipping_not_included")
        self.assertIsNone(policy._variant_rejection_reason(row, TITLE, ignore_postage=True))

    def test_search_wrapper_preserves_postage_filter_by_default(self):
        with patch.object(policy, "search_items", return_value=[]) as search:
            policy._search_items(JAN, 15.0)
            search.assert_called_once_with(JAN, 15.0, postage_included=True)
        with patch.object(policy, "search_items", return_value=[]) as search:
            policy._search_items(JAN, 15.0, postage_included=False)
            search.assert_called_once_with(JAN, 15.0, postage_included=False)

    def test_normal_prohibited_word_exception_keeps_its_postage_filter(self):
        with patch.object(policy, "search_items", return_value=[item("a", postage=0)]) as search:
            count = policy.rakuten_listing_count_for_jan(JAN)
        self.assertEqual(count, 1)
        search.assert_called_once_with(JAN, 15.0, postage_included=True)


if __name__ == "__main__":
    unittest.main()
