"""New/old BuyBox DOM regressions; no network, DB, worker or purchase."""
import os
import unittest
from datetime import date
from unittest.mock import patch

from playwright.async_api import async_playwright
from scripts import price_check_one_asin_db as checker


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 29)


def fixture(label='Amazon.co.jpによる発送と販売', *, delivery='無料配送 10月31日 土曜日 にお届け', condition=''):
    # Minimal, non-personal reproduction of the 2026-10-29 merchant DOM.
    return f'''<style>.a-popover-preload,.aok-hidden{{display:none}}</style>
    <div id="desktop_buybox"><div id="buybox">
      <div>{condition}</div>
      <div id="corePrice_feature_div"><span class="a-price-whole">2,536</span></div>
      <div id="deliveryBlockMessage">{delivery}</div><div id="availability">在庫あり。</div>
      <input id="add-to-cart-button" type="button" value="カートに入れる">
      <input id="buy-now-button" type="button" value="今すぐ買う">
      <div id="fulfillerInfoFeature_feature_div"></div>
      <div id="merchantInfoFeature_feature_div">
        <div class="offer-display-feature-text">
          <div class="aok-hidden"><span>{label}</span></div>
          <span class="a-declarative"><a role="button"><span>{label}</span></a></span>
          <div class="a-popover-preload"><div>出荷元 / 販売元</div><div>Amazon.co.jp</div></div>
        </div>
      </div>
      <div id="dynamicGiftWrapInfoFeature_feature_div">ギフトオプション レジでご利用いただけます</div>
    </div></div>'''


@unittest.skipUnless(os.environ.get('RUN_LOCAL_BROWSER_TESTS') == '1', 'opt-in local browser fixture')
class BuyboxMerchantBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = await async_playwright().start()
        self.browser = await self.engine.chromium.launch(headless=True)
        self.page = await self.browser.new_page()
        await self.page.route('**/*', lambda route: route.abort())
        self.clock = patch.object(checker, 'date', FixedDate)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    async def asyncTearDown(self):
        await self.browser.close()
        await self.engine.stop()

    async def test_new_visible_label_works_without_hidden_legacy_text(self):
        await self.page.set_content(fixture())
        for remove_hidden in (False, True):
            if remove_hidden:
                await self.page.locator('.a-popover-preload').evaluate('(el) => el.remove()')
            info = await checker.read_buybox_info(self.page)
            text = info['in_text']
            self.assertNotIn('出荷元', text)
            self.assertEqual(info['price'], 2536)
            self.assertTrue(checker.is_amazon_official_offer_text(text))
            self.assertTrue(checker.is_amazon_fulfilled_offer_text(text))
            self.assertTrue(checker.is_eligible_buybox_condition_text(text))
            self.assertEqual(checker.judge_basic_ng(text), '')
            self.assertEqual(checker.parse_shipping_status(text)[0], 'OK')

    async def test_old_visible_labels_still_work(self):
        for label in ('出荷元 / 販売元 Amazon.co.jp', '出荷元 Amazon.co.jp 販売元 他店'):
            with self.subTest(label=label):
                await self.page.set_content(fixture(label))
                info = await checker.read_buybox_info(self.page)
                self.assertTrue(checker.is_amazon_fulfilled_offer_text(info['in_text']))
                self.assertEqual(info['price'], 2536)

    async def test_service_label_cannot_use_hidden_old_label_as_shipping_evidence(self):
        await self.page.set_content(fixture('Amazon.co.jpによるカスタマーサービス'))
        info = await checker.read_buybox_info(self.page)
        self.assertFalse(checker.is_amazon_fulfilled_offer_text(info['in_text']))

    async def test_new_label_does_not_bypass_condition_or_delivery(self):
        for condition in ('中古', '整備済み'):
            await self.page.set_content(fixture(condition=condition))
            info = await checker.read_buybox_info(self.page)
            self.assertFalse(checker.is_eligible_buybox_condition_text(info['in_text']))
        await self.page.set_content(fixture(delivery='無料配送 11月10日 にお届け'))
        info = await checker.read_buybox_info(self.page)
        self.assertEqual(checker.parse_shipping_status(info['in_text'])[0], 'NG')


if __name__ == '__main__':
    unittest.main()
