"""No-network regressions for faster reads without weaker sourcing decisions."""
import unittest
from unittest.mock import AsyncMock, patch

from scripts import price_check_one_asin_db as checker


class Element:
    def __init__(self, text='', *, exists=True, attrs=None, selectors=None):
        self.count = AsyncMock(return_value=int(exists))
        self.inner_text = AsyncMock(return_value=text)
        self.get_attribute = AsyncMock(side_effect=lambda name: (attrs or {}).get(name))
        self.selectors = selectors or {}

    @property
    def first(self):
        return self

    def locator(self, selector):
        return self.selectors.get(selector, Element(exists=False))


class Rows:
    def __init__(self, rows):
        self.rows = rows

    async def count(self):
        return len(self.rows)

    def nth(self, index):
        return self.rows[index]


class Options(Rows):
    def __init__(self, values):
        super().__init__([Element(text, attrs={'value': value}) for value, text in values])
        self.evaluate_all = AsyncMock(return_value=values)
        self.index_reads = 0

    def nth(self, index):
        self.index_reads += 1
        return super().nth(index)


def quantity_root(values, selector='#quantity select'):
    options = Options(values)
    root = Element(selectors={selector: Element(selectors={'option': options})})
    return root, options


class QuantityReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_fifty_options_and_minimum_are_read_in_one_snapshot(self):
        values = [(str(i), f' {i} ' + ('(最小注文個数)' if i == 2 else '')) for i in range(2, 52)]
        root, options = quantity_root(values)
        self.assertEqual(await checker.get_quantity_dropdown_details(root), (51, 2))
        options.evaluate_all.assert_awaited_once()
        self.assertEqual(options.index_reads, 0)
        for row in options.rows:
            row.get_attribute.assert_not_awaited()
            row.inner_text.assert_not_awaited()

    async def test_snapshot_matches_the_existing_parser_for_labels_and_non_numeric_values(self):
        for values in ([], [('x', '数量'), ('', '3 (最小注文個数)'), ('10+', '10+')],
                       [('9', '2'), ('1', '1')], [('1', '1'), ('50', '50')]):
            with self.subTest(values=values):
                root, _ = quantity_root(values)
                self.assertEqual(await checker.get_quantity_dropdown_details(root),
                                 checker.quantity_dropdown_details(values))

    async def test_selected_root_and_selector_priority_are_preserved(self):
        root, root_options = quantity_root([('2', '2 (最小注文個数)'), ('5', '5')])
        page, page_options = quantity_root([('50', '50')])
        self.assertEqual(await checker.get_quantity_dropdown_details(page, root=root), (5, 2))
        root_options.evaluate_all.assert_awaited_once()
        page_options.evaluate_all.assert_not_awaited()

    async def test_page_fallback_and_legacy_selector_are_preserved(self):
        page, options = quantity_root([('3', '3 (最小注文個数)'), ('7', '7')], selector='select#quantity')
        self.assertEqual(await checker.get_quantity_dropdown_details(page, root=Element()), (7, 3))
        options.evaluate_all.assert_awaited_once()

    async def test_snapshot_failure_retains_original_per_option_read(self):
        root, options = quantity_root([('2', '2 (最小注文個数)'), ('8', '8')])
        options.evaluate_all.side_effect = RuntimeError('detached snapshot')
        self.assertEqual(await checker.get_quantity_dropdown_details(root), (8, 2))
        self.assertEqual(options.index_reads, 2)

    async def test_missing_quantity_controls_remain_unknown(self):
        self.assertEqual(await checker.get_quantity_dropdown_details(Element()), (None, None))


WHOLE = '.apex-pricetopay-value .a-price-whole'
LABEL = '.apex-pricetopay-accessibility-label'
LEGACY = '#aod-offer-price'


class OfferPriceReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_absent_optional_prices_do_not_wait_when_legacy_price_is_ready(self):
        absent_whole, absent_label = Element(exists=False), Element(exists=False)
        root = Element(selectors={WHOLE: absent_whole, LABEL: absent_label, LEGACY: Element('￥1,200')})
        self.assertEqual(await checker.get_aod_offer_price(root), 1200)
        absent_whole.inner_text.assert_not_awaited()
        absent_label.inner_text.assert_not_awaited()

    async def test_price_priority_is_preserved(self):
        lower = Element('￥999')
        root = Element(selectors={WHOLE: Element('1,200'), LABEL: lower, LEGACY: lower})
        self.assertEqual(await checker.get_aod_offer_price(root), 1200)
        lower.inner_text.assert_not_awaited()

    async def test_discount_percentage_is_never_the_price(self):
        for selector in (LABEL, LEGACY):
            with self.subTest(selector=selector):
                root = Element(selectors={selector: Element('25パーセントの割引で￥1,260')})
                self.assertEqual(await checker.get_aod_offer_price(root), 1260)

    async def test_missing_prices_retain_the_waiting_path(self):
        # The primary price is absent during the quick presence check, then
        # appears when the original inner_text wait resolves.
        late = Element('1,400', exists=False)
        root = Element(selectors={WHOLE: late})
        self.assertEqual(await checker.get_aod_offer_price(root), 1400)
        late.inner_text.assert_awaited_once_with(timeout=2000)

    async def test_presence_check_failure_uses_original_read_path(self):
        field = Element('1,300')
        field.count.side_effect = RuntimeError('DOM changed')
        self.assertEqual(await checker.get_aod_offer_price(Element(selectors={WHOLE: field})), 1300)
        field.inner_text.assert_awaited_once_with(timeout=2000)

    async def test_no_price_does_not_create_an_offer_price(self):
        root = Element(selectors={WHOLE: Element(''), LABEL: Element('割引'), LEGACY: Element('価格なし')})
        self.assertEqual(await checker.get_aod_offer_price(root), 0)


def offer(price, *, ship='Amazon', condition='新品', delivery='明日お届け', postage='無料',
          quantity=5, minimum=None, can_add=True):
    action = Element(attrs={'data-aod-atc-action': '{"offerIndex":1,"maxQty":' + str(quantity) + '}'})
    button = Element(exists=can_add, selectors={'xpath=ancestor::*[@data-aod-atc-action][1]': action})
    return Element(condition + (f' 最小注文数: {minimum}' if minimum else ''), selectors={
        '#aod-offer-shipsFrom': Element('出荷元 ' + ship),
        LEGACY: Element('￥' + str(price)),
        '[data-csa-c-delivery-price]': Element(attrs={'data-csa-c-delivery-price': postage, 'data-csa-c-delivery-time': delivery}),
        "input[name='submit.addToCart']": button,
        '#aod-offer-soldBy': Element('販売元 Test seller'),
    })


class FullOfferDecisionTests(unittest.IsolatedAsyncioTestCase):
    async def inspect(self, offers, quantity=1):
        page = Element(selectors={'#aod-offer-list #aod-offer': Rows(offers)})
        with patch.object(checker, 'open_all_offers', new=AsyncMock()) as load:
            result = await checker.read_lowest_amazon_fulfilled_offer(page, quantity)
        load.assert_awaited_once_with(page)
        return result

    async def test_still_checks_all_offers_and_selects_lowest_not_first(self):
        result = await self.inspect([offer(1700), offer(1200), offer(1500)])
        self.assertEqual(result['price'], 1200)

    async def test_shipping_condition_and_stock_checks_are_not_bypassed(self):
        rejected = [offer(100, ship='Shop'), offer(100, condition='中古'),
                    offer(100, delivery='30日以内にお届け'), offer(100, postage='￥100'),
                    offer(100, quantity=1), offer(100, can_add=False)]
        result = await self.inspect(rejected + [offer(1600)], quantity=2)
        self.assertEqual(result['price'], 1600)
        self.assertIsNone(await self.inspect(rejected, quantity=2))

    async def test_minimum_order_restriction_still_reaches_the_final_block(self):
        result = await self.inspect([offer(1200, minimum=2)])
        self.assertEqual(result['minimum_order_quantity'], 2)
        final = {}
        checker.apply_minimum_order_block(final, result['minimum_order_quantity'])
        self.assertTrue(final['business_ng'])

    async def test_incomplete_offer_list_still_fails_instead_of_accepting_first_offer(self):
        page = Element(selectors={'#aod-offer-list #aod-offer': Rows([offer(1200)])})
        with patch.object(checker, 'open_all_offers', new=AsyncMock(side_effect=RuntimeError('incomplete'))):
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                await checker.read_lowest_amazon_fulfilled_offer(page)


if __name__ == '__main__':
    unittest.main()
