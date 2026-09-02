from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.rakuten_competitor_researcher import (
    amazon_keyword_context,
    choose_amazon_candidate,
    fetch_html,
    load_store_urls,
    normalize_store_url,
    parse_store_products,
    title_similarity,
)


class RakutenCompetitorResearcherTests(unittest.TestCase):
    def test_normalize_store_url_accepts_only_rakuten_store_search(self) -> None:
        url, sid = normalize_store_url("https://search.rakuten.co.jp/search/mall/?sid=427886")
        self.assertEqual(url, "https://search.rakuten.co.jp/search/mall/?sid=427886")
        self.assertEqual(sid, "427886")
        with self.assertRaises(ValueError):
            normalize_store_url("https://item.rakuten.co.jp/donzstore/b0d9gsqpwm/")

    def test_load_store_urls_deduplicates_same_sid_and_caps_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "stores.txt"
            path.write_text(
                "https://search.rakuten.co.jp/search/mall/?sid=427886\n"
                "https://search.rakuten.co.jp/search/mall/?sid=427886&foo=bar\n",
                encoding="utf-8",
            )
            stores = load_store_urls(path)
        self.assertEqual(stores, [{"store_url": "https://search.rakuten.co.jp/search/mall/?sid=427886", "sid": "427886"}])

    def test_parse_store_products_preserves_first_seen_order(self) -> None:
        html = """
        <a href="https://item.rakuten.co.jp/shop/b0first001/?variant=1"><img alt="商品 一" /></a>
        <a href="https://item.rakuten.co.jp/shop/b0first001/">duplicate</a>
        <a href="https://item.rakuten.co.jp/shop/b0second02/"><img alt="商品 二" /></a>
        <a href="https://item.rakuten.co.jp/shop/c/">category</a>
        """
        products = parse_store_products(html)
        self.assertEqual([row["item_code"] for row in products], ["b0first001", "b0second02"])
        self.assertEqual(products[0]["rakuten_title"], "商品 一")

    def test_amazon_keyword_uses_visible_text_and_rakuten_item_data(self) -> None:
        self.assertEqual(amazon_keyword_context("<script>const seller='Amazon'</script><p>通常発送</p>"), (False, ""))
        matched, context = amazon_keyword_context("<p>一部の商品はamazonの倉庫から発送します。</p>")
        self.assertTrue(matched)
        self.assertIn("amazon", context)
        self.assertTrue(amazon_keyword_context("<p>アマゾン倉庫を利用</p>")[0])
        self.assertTrue(amazon_keyword_context('<p>当店はFBAから発送します。</p>')[0])
        self.assertFalse(amazon_keyword_context('<script>const fbAppId = "123";</script>')[0])
        self.assertTrue(
            amazon_keyword_context(
                '<script id="item-page-app-data" type="application/json">'
                '{"customizationOptions":[{"label":"Amazon倉庫から発送します"}]}'
                '</script>'
            )[0]
        )

    def test_fetch_html_retries_temporary_rakuten_error(self) -> None:
        unavailable = Mock(status_code=503, headers={"content-type": "text/html"}, encoding="utf-8")
        ok = Mock(status_code=200, headers={"content-type": "text/html; charset=utf-8"}, encoding="utf-8")
        ok.content = "商品".encode("utf-8")
        session = Mock()
        session.get.side_effect = [unavailable, ok]
        with patch("scripts.rakuten_competitor_researcher.time.sleep") as sleep:
            self.assertEqual(fetch_html(session, "https://example.invalid/"), "商品")
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_choose_amazon_candidate_prefers_item_code_confirmed_by_search(self) -> None:
        candidates = [
            {"asin": "B000OTHER1", "title": "似ていない商品", "url": ""},
            {"asin": "B0D9GSQPWM", "title": "お薬カレンダー 壁掛け ポケット付き", "url": ""},
        ]
        chosen = choose_amazon_candidate("送料無料 お薬カレンダー 壁掛け ポケット付き", candidates, "B0D9GSQPWM")
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["asin"], "B0D9GSQPWM")
        self.assertEqual(chosen["match_method"], "item_code_confirmed_in_amazon_search")

    def test_title_similarity_rejects_unrelated_candidate(self) -> None:
        self.assertGreater(title_similarity("お薬カレンダー 壁掛け ポケット付き", "お薬カレンダー 壁掛け 1ヶ月 ポケット"), 0.5)
        self.assertIsNone(
            choose_amazon_candidate(
                "お薬カレンダー 壁掛け ポケット付き",
                [{"asin": "B000OTHER1", "title": "電気ケトル ステンレス", "url": ""}],
            )
        )


if __name__ == "__main__":
    unittest.main()
