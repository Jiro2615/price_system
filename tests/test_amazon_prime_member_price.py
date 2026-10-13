"""Mocked Prime-price regressions: no DB, network, browser, or purchase."""
from contextlib import ExitStack
import unittest
from unittest.mock import AsyncMock, Mock, patch

from scripts import price_check_one_asin_db as checker


class Element:
    def __init__(self, text="", *, attrs=None, visible=True, exists=True, selectors=None, content_text=None):
        self.text, self.attrs = text, attrs or {}
        self.visible, self.exists = visible, exists
        self.selectors = selectors or {}
        self.content_text = text if content_text is None else content_text
        self.requests = []

    @property
    def first(self):
        return self

    async def count(self):
        return int(self.exists)

    def nth(self, index):
        if index != 0:
            raise AssertionError(index)
        return self

    async def inner_text(self, **_kwargs):
        return self.text

    async def text_content(self, **_kwargs):
        return self.content_text

    async def is_visible(self, **_kwargs):
        return self.visible

    async def get_attribute(self, name):
        return self.attrs.get(name)

    def locator(self, selector):
        self.requests.append(selector)
        return self.selectors.get(selector, Element(exists=False))


class Rows:
    def __init__(self, rows):
        self.rows = rows

    async def count(self):
        return len(self.rows)

    def nth(self, index):
        return self.rows[index]


def offer(*, seller="A22191R8FLMIML", ship="Amazon", price="1,260", prime=True,
          visible=True, condition="新品", point=None, header_text=None):
    header = Element(header_text or f"{condition} 取引価格 ￥{price}", visible=visible)
    return Element(f"{condition} ギフト 出荷元 {ship} 販売元 店舗 無料配送 明日お届け 在庫あり",
                   attrs={"data-a-accordion-row-name": "primeSavingsUpsellAccordionRow" if prime else "newAccordionRow"},
                   selectors={
        ".a-accordion-row-a11y": header,
        "#sellerProfileTriggerId": Element(attrs={"href": f"https://www.amazon.co.jp/sp?seller={seller}"}),
        "#fulfillerInfoFeature_feature_div": Element(f"出荷元 {ship}"),
        ".apex-pricetopay-value .a-price-whole": Element(price, exists=bool(price) and prime),
        ".a-price-whole": Element(price),
        "#pointsInsideBuyBox_feature_div": Element(f"{point}pt", exists=point is not None),
    })


def page_for(rows):
    page = Mock()
    page.url = "https://www.amazon.co.jp/dp/B0G6ZHBKHH?th=1"
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.locator.side_effect = lambda selector: (
        Rows(rows) if "primeSavingsUpsellAccordionRow" in selector
        else Element("商品ページ") if selector == "body"
        else Element("17pt") if selector == "#pointsInsideBuyBox_feature_div"
        else Element(exists=False)
    )
    return page


class PrimePriceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.regular = offer(prime=False, price="1,680", point=17)
        self.guard = patch.object(checker, "connect_db", side_effect=AssertionError("DB forbidden"))
        self.guard.start()
        self.addCleanup(self.guard.stop)

    async def test_same_seller_prime_price_and_its_own_points(self):
        result = await checker.read_matching_prime_buybox_price(page_for([offer(point=13)]), self.regular)
        self.assertEqual(result, {"price": 1260, "point": 13})

    async def test_absent_member_points_are_not_non_sale_points(self):
        result = await checker.read_matching_prime_buybox_price(page_for([offer()]), self.regular)
        self.assertEqual(result, {"price": 1260, "point": 0})

    async def test_no_prime_row_does_not_read_regular_metadata(self):
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([]), self.regular))
        self.assertEqual(self.regular.requests, [])

    async def test_missing_regular_row_is_not_an_unverified_discount(self):
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([offer()]), None))

    async def test_generic_parent_or_subscription_cannot_self_match_prime_offer(self):
        for name in (None, "snsAccordionRowMiddle", "usedAccordionRow", "primeSavingsUpsellAccordionRow"):
            with self.subTest(name=name):
                self.regular.attrs["data-a-accordion-row-name"] = name
                self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([offer()]), self.regular))

    async def test_different_seller_or_missing_identity_is_rejected(self):
        for seller in ("A_OTHER_SELLER", "A123456789", "", "A22191R8FLMIML&seller=A99999"):
            with self.subTest(seller=seller):
                self.assertIsNone(await checker.read_matching_prime_buybox_price(
                    page_for([offer(seller=seller)]), self.regular))
        self.regular.selectors["#sellerProfileTriggerId"] = Element(exists=False)
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([offer()]), self.regular))

    async def test_both_offers_must_be_amazon_shipped(self):
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([offer(ship="店舗")]), self.regular))
        self.regular.selectors["#fulfillerInfoFeature_feature_div"] = Element("出荷元 店舗")
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([offer()]), self.regular))
        self.regular.selectors["#fulfillerInfoFeature_feature_div"] = Element(exists=False)
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([offer()]), self.regular))

    async def test_collapsed_prime_fulfiller_uses_only_its_dedicated_field(self):
        prime = offer()
        prime.selectors["#fulfillerInfoFeature_feature_div"] = Element("", content_text="出荷元 Amazon")
        self.assertEqual(await checker.read_matching_prime_buybox_price(page_for([prime]), self.regular),
                         {"price": 1260, "point": 0})
        prime.selectors["#fulfillerInfoFeature_feature_div"] = Element("", content_text="出荷元 店舗")
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([prime]), self.regular))

    async def test_dedicated_shipper_is_exact_amazon_not_an_amazon_prefixed_name(self):
        for text in ("Amazon", "Amazon.co.jp", "出荷元 Amazon Amazon 出荷元 Amazon"):
            with self.subTest(text=text):
                root = offer()
                root.selectors["#fulfillerInfoFeature_feature_div"] = Element(text)
                self.assertTrue(await checker.buybox_has_amazon_fulfiller(root))
        for text in ("出荷元 Amazon配送代行", "発送元 Amazon", "出荷元 Amazon.com", "Amazonマーケットプレイス"):
            with self.subTest(text=text):
                root = offer()
                root.selectors["#fulfillerInfoFeature_feature_div"] = Element(text)
                self.assertFalse(await checker.buybox_has_amazon_fulfiller(root))

    async def test_hidden_empty_and_non_new_prime_rows_are_rejected(self):
        for prime in (offer(visible=False), offer(price=""), offer(condition="中古"), offer(condition="整備済み")):
            with self.subTest(text=prime.text):
                self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([prime]), self.regular))
        self.regular.text = "中古 ギフト 出荷元 Amazon"
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([offer()]), self.regular))

    async def test_accessibility_price_does_not_take_discount_percentage(self):
        prime = offer(price="")
        prime.selectors[".apex-pricetopay-accessibility-label"] = Element("25パーセントの割引で￥1,260")
        self.assertEqual(await checker.read_matching_prime_buybox_price(page_for([prime]), self.regular),
                         {"price": 1260, "point": 0})

    async def test_unit_reference_and_subscription_prices_are_not_candidates(self):
        prime = offer(price="")
        prime.selectors.update({".a-price-whole": Element("400"), ".a-offscreen": Element("￥1,680"),
                                ".apex-priceperunit-value": Element("￥400 / 100g")})
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page_for([prime]), self.regular))
        # Selection is restricted to the explicit Prime accordion, never a
        # subscription/used/card outside it or an arbitrary page-wide price.
        page = page_for([])
        await checker.read_matching_prime_buybox_price(page, self.regular)
        selector = page.locator.call_args.args[0]
        self.assertNotIn("snsAccordionRow", selector)
        self.assertNotIn("usedAccordionRow", selector)

    async def test_changed_markup_keeps_regular_price_without_throwing(self):
        page = page_for([offer()])
        page.locator.side_effect = RuntimeError("DOM changed")
        self.assertIsNone(await checker.read_matching_prime_buybox_price(page, self.regular))

    async def test_buybox_keeps_normal_shipping_and_stock_text_but_uses_prime_price(self):
        page = page_for([offer()])
        with patch.object(checker, "get_selected_new_buybox_row", new=AsyncMock(return_value=self.regular)), \
             patch.object(checker, "expand_see_more", new=AsyncMock()):
            info = await checker.read_buybox_info(page)
        self.assertEqual(info["in_text"], self.regular.text)
        self.assertEqual(info["price"], 1260)
        self.assertEqual(info["price_source"], "prime_member")
        self.assertEqual(info["prime_point"], 0)

    async def check(self, *, prime=True):
        page = page_for([offer()] if prime else [])
        alt = AsyncMock(return_value=1680)
        all_offers = AsyncMock(return_value=None)
        with ExitStack() as stack:
            for name, replacement in {
                "select_one_time_purchase": AsyncMock(return_value=False),
                "get_selected_new_buybox_row": AsyncMock(return_value=self.regular),
                "expand_see_more": AsyncMock(),
                "get_title": AsyncMock(return_value="Test product"),
                "detect_unsupported_direct_purchase_ui": AsyncMock(return_value=""),
                "get_quantity_dropdown_details": AsyncMock(return_value=(30, None)),
                "get_alt_price_from_buybox": alt,
                "read_lowest_amazon_fulfilled_offer": all_offers,
                "log_shipping_evidence": Mock(),
            }.items():
                stack.enter_context(patch.object(checker, name, new=replacement))
            result = await checker.check_amazon_one("B0G6ZHBKHH", page=page, settle_timeout_ms=0)
        return result, alt, all_offers

    async def test_final_result_does_not_overwrite_prime_with_regular_alt_price(self):
        result, alt, all_offers = await self.check()
        self.assertFalse(result["system_error"], result)
        self.assertFalse(result["business_ng"], result)
        self.assertEqual(result["amazon_price"], 1260)
        self.assertEqual(result["amazon_point"], 0)
        self.assertEqual(result["available_qty"], 30)
        self.assertEqual(result["price_source"], "prime_member")
        alt.assert_not_awaited()
        all_offers.assert_not_awaited()

    async def test_no_prime_preserves_normal_result_and_alt_price_path(self):
        result, alt, _ = await self.check(prime=False)
        self.assertEqual(result["amazon_price"], 1680)
        self.assertEqual(result["amazon_point"], 17)
        self.assertNotIn("price_source", result)
        alt.assert_awaited_once()

    async def test_prime_does_not_bypass_delivery_and_gift_blocks(self):
        for text in ("新品 ギフト 出荷元 Amazon 無料配送 30日以内にお届け 在庫あり",
                     "新品 出荷元 Amazon 無料配送 明日お届け 在庫あり"):
            with self.subTest(text=text):
                self.regular.text = text
                result, _, _ = await self.check()
                self.assertTrue(result["business_ng"], result)
                self.assertFalse(result["system_error"], result)


if __name__ == "__main__":
    unittest.main()
