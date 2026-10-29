"""Identity regressions: no network, persistence, browser, or live worker."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from scripts import price_check_one_asin_db as checker

policy = checker._identity
EXPECTED = 'B08713SQHV'
OTHER = 'B0DXPWV7XS'
URL = f'https://www.amazon.co.jp/dp/{EXPECTED}?th=1&psc=1'
CHILD, PARENT = 'B0BNH43W1M', 'B0F42X5JXG'
CHILD_URL = f'https://www.amazon.co.jp/dp/{CHILD}?th=1&psc=1'
PARENT_URL = f'https://www.amazon.co.jp/dp/{PARENT}'


def parent_observation(**changes):
    data = {'selected_asin': CHILD, 'canonical_url': CHILD_URL,
            'detail_asins': [PARENT], 'purchase_asins': [CHILD],
            'parent_relationship': {'source': 'twister-js-init-dpx-data',
                                    'current_asin': CHILD, 'parent_asin': PARENT}}
    data.update(changes)
    return data


class IdentityTests(unittest.TestCase):
    def test_seven_observed_parent_canonicals_are_allowed(self):
        for child, parent, details in (
                ('B0CZNHXP5R', 'B0FJXY2CVX', ['B0CZNHXP5R']),
                ('B0CLNYSFZ6', 'B0GVJVQQRN', ['B0CLNYSFZ6']),
                ('B0CG16JCB1', 'B0HFZ9229L', ['B0HFZ9229L']),
                ('B0C7V45RFJ', 'B0C8124NKF', []),
                ('B0BWDTQBLX', 'B0F1MP36YG', ['B0F1MP36YG']),
                ('B0BSL7FJYT', 'B0FQJN1HKW', []),
                ('B0BG5SPV3Q', 'B0GC3S3JT2', ['B0GC3S3JT2'])):
            with self.subTest(asin=child):
                evidence = {'selected_asin':child,'canonical_url':'https://www.amazon.co.jp/dp/'+parent,
                            'purchase_asins':[child],'detail_asins':details,
                            'parent_relationship':{'source':'twister-js-init-dpx-data',
                                                   'current_asin':child,'parent_asin':parent}}
                self.assertEqual(policy.identity_error(child,'https://www.amazon.co.jp/dp/'+child,evidence),'')

    def test_parent_canonical_requires_child_purchase_and_unambiguous_relationship(self):
        baseline = parent_observation(canonical_url=PARENT_URL, detail_asins=[])
        for changes in ({'selected_asin':''}, {'selected_asin':OTHER}, {'selected_asin':PARENT},
                        {'purchase_asins':[]}, {'purchase_asins':None}, {'purchase_asins':CHILD},
                        {'purchase_asins':[CHILD,'']}, {'purchase_asins':[PARENT]},
                        {'purchase_asins':[CHILD,OTHER]}, {'parent_relationship':None},
                        {'parent_relationship':{}},
                        {'parent_relationship':{'source':'recommendations','current_asin':CHILD,'parent_asin':PARENT}},
                        {'parent_relationship':{'source':'twister-js-init-dpx-data','current_asin':OTHER,'parent_asin':PARENT}},
                        {'parent_relationship':{'source':'twister-js-init-dpx-data','current_asin':CHILD,'parent_asin':OTHER}}):
            with self.subTest(changes=changes):
                self.assertTrue(policy.identity_error(CHILD,CHILD_URL,{**baseline,**changes}).startswith('ASIN不一致'))

    def test_parent_canonical_does_not_allow_other_detail_or_browser_redirect(self):
        evidence = parent_observation(canonical_url=PARENT_URL)
        self.assertIn('商品詳細2='+OTHER,policy.identity_error(CHILD,CHILD_URL,
            {**evidence,'detail_asins':[PARENT,OTHER]}))
        for url in (PARENT_URL,URL,'https://evil.invalid/dp/'+CHILD):
            with self.subTest(url=url):
                self.assertTrue(policy.identity_error(CHILD,url,evidence).startswith('ASIN不一致'))
        self.assertIn('正規URL='+OTHER,policy.identity_error(CHILD,CHILD_URL,
            {**evidence,'canonical_url':'https://www.amazon.co.jp/dp/'+OTHER}))

    def test_verified_child_with_parent_only_in_details_is_accepted(self):
        for details in ([PARENT], [CHILD, PARENT], [PARENT, PARENT]):
            self.assertEqual(policy.identity_error(CHILD, CHILD_URL,
                parent_observation(detail_asins=details)), '')

    def test_parent_exception_requires_all_independent_identity_checks(self):
        for changes in ({'selected_asin': ''}, {'selected_asin': OTHER},
                        {'canonical_url': ''}, {'canonical_url': URL},
                        {'purchase_asins': None}, {'purchase_asins': []},
                        {'purchase_asins': [CHILD, '']}, {'purchase_asins': [OTHER]},
                        {'purchase_asins': [CHILD, OTHER]}, {'purchase_asins': CHILD},
                        {'parent_relationship': None}, {'parent_relationship': {}},
                        {'parent_relationship': {'source': 'recommendations', 'current_asin': CHILD, 'parent_asin': PARENT}},
                        {'parent_relationship': {'source': 'twister-js-init-dpx-data', 'current_asin': OTHER, 'parent_asin': PARENT}},
                        {'parent_relationship': {'source': 'twister-js-init-dpx-data', 'current_asin': CHILD, 'parent_asin': OTHER}}):
            with self.subTest(changes=changes):
                self.assertTrue(policy.identity_error(CHILD, CHILD_URL,
                    parent_observation(**changes)).startswith('ASIN不一致'))

    def test_parent_metadata_never_overrides_url_or_other_details(self):
        for url in (URL, 'https://evil.invalid/dp/'+CHILD):
            self.assertTrue(policy.identity_error(CHILD, url, parent_observation()).startswith('ASIN不一致'))
        self.assertIn('商品詳細2='+OTHER, policy.identity_error(CHILD, CHILD_URL,
            parent_observation(detail_asins=[PARENT, OTHER])))

    def test_purchase_conflict_is_rejected_even_without_detail_asin(self):
        self.assertIn('購入対象1='+OTHER, policy.identity_error(CHILD, CHILD_URL,
            parent_observation(detail_asins=[], purchase_asins=[OTHER])))

    def test_real_same_url_replacement_remains_blocked(self):
        source, replacement = 'B0CH9TX6XK', 'B0DNYN8VM3'
        result = policy.identity_error(source, 'https://www.amazon.co.jp/dp/'+source,
            {'selected_asin': replacement, 'canonical_url': 'https://www.amazon.co.jp/dp/'+replacement,
             'purchase_asins': [replacement], 'detail_asins': [],
             'parent_relationship': {'source': 'twister-js-init-dpx-data',
                                     'current_asin': replacement, 'parent_asin': 'B0CC1NGQRD'}})
        self.assertTrue(result.startswith('ASIN不一致'))
        self.assertIn('選択商品='+replacement, result)

    def test_same_url_but_different_selected_asin_is_ng(self):
        self.assertTrue(policy.identity_error(EXPECTED, URL, {'selected_asin': OTHER}).startswith('ASIN不一致'))

    def test_canonical_and_detail_conflicts_are_ng(self):
        for evidence in ({'canonical_url': f'https://www.amazon.co.jp/name/dp/{OTHER}'},
                         {'selected_asin': EXPECTED, 'detail_asins': [OTHER]},
                         {'selected_asin': EXPECTED, 'canonical_url': f'https://www.amazon.co.jp/dp/{OTHER}'}):
            self.assertTrue(policy.identity_error(EXPECTED, URL, evidence).startswith('ASIN不一致'))

    def test_url_redirect_is_ng_even_when_dom_matches(self):
        self.assertTrue(policy.identity_error(EXPECTED, URL.replace(EXPECTED, OTHER),
                                             {'selected_asin': EXPECTED}).startswith('ASIN不一致'))

    def test_url_only_missing_and_invalid_identity_fail_closed(self):
        for evidence in ({}, None, [], {'selected_asin': 'invalid'}, {'purchase_asins': [EXPECTED]}):
            self.assertTrue(policy.identity_error(EXPECTED, URL, evidence).startswith('ASIN未確認'))
        self.assertTrue(policy.identity_error(EXPECTED, 'https://evil.invalid/dp/'+EXPECTED,
                                             {'selected_asin': EXPECTED}).startswith('ASIN未確認'))

    def test_matching_page_and_canonical_are_accepted(self):
        self.assertEqual(policy.identity_error(EXPECTED, URL,
            {'selected_asin': EXPECTED.lower(), 'canonical_url': URL, 'detail_asins': [EXPECTED]}), '')
        self.assertEqual(policy.identity_error(EXPECTED, URL, {'canonical_url': URL}), '')

    def test_independent_order_policy_has_exact_same_content(self):
        other = Path(__file__).parents[2]/'Rakuten/python/amazon_product_identity.py'
        if other.exists():
            self.assertEqual(Path(policy.__file__).read_text(encoding='utf-8'), other.read_text(encoding='utf-8'))


class CheckerTests(unittest.IsolatedAsyncioTestCase):
    async def test_parent_details_pass_with_one_read_and_clear_stale_observation(self):
        for canonical in (CHILD_URL,PARENT_URL):
            page = SimpleNamespace(url=CHILD_URL, evaluate=AsyncMock(return_value=parent_observation(canonical_url=canonical)))
            result = {'asin': CHILD, 'amazon_redirect_observation': {'target_asin': PARENT}}
            self.assertTrue(await checker.verify_product_identity(page, CHILD, result))
            self.assertIsNone(result['amazon_redirect_observation'])
            self.assertNotIn('business_ng', result)
            page.evaluate.assert_awaited_once()

    async def test_listing_bridge_uses_same_guard_and_preserves_rejection(self):
        from scripts.listing import amazon_bridge
        from scripts.listing.prepare_service import _classify_amazon_result
        # Only the surrounding price/shipping fetch is simulated. The bridge,
        # identity guard and listing rejection classifier are production code.
        async def checked_page(asin, *, page, **kwargs):
            result = {'asin':asin,'amazon_price':1000,'available_qty':1,'gift_available':True}
            await checker.verify_product_identity(page,asin,result)
            return result
        with patch.object(amazon_bridge,'_amazon_module',None):
            self.assertIs(amazon_bridge._load_amazon_module(),checker)
            for purchases, accepted in (([CHILD],True),([OTHER],False)):
                page = SimpleNamespace(url=CHILD_URL, evaluate=AsyncMock(return_value=
                    parent_observation(canonical_url=PARENT_URL,purchase_asins=purchases)))
                with patch.object(checker,'check_amazon_one',side_effect=checked_page):
                    result = await amazon_bridge.fetch_amazon_result(CHILD,page=page)
                self.assertEqual(result.business_ng,not accepted)
                classified = _classify_amazon_result(CHILD,result)
                if accepted:
                    self.assertIsNone(classified)
                    self.assertEqual(result.page_asin,CHILD)
                else:
                    self.assertEqual(classified[0],'business_ng')
                    self.assertTrue(classified[1].startswith('ASIN不一致'))

    async def test_mismatch_returns_before_title_image_offer_or_price(self):
        for evidence in ({'selected_asin': OTHER}, {}):
            page = SimpleNamespace(url=URL, goto=AsyncMock(), wait_for_timeout=AsyncMock(),
                                   evaluate=AsyncMock(return_value=evidence))
            with patch.object(checker, 'get_first_text', AsyncMock(return_value='商品ページ')), \
                 patch.object(checker, 'select_one_time_purchase', AsyncMock()) as select, \
                 patch.object(checker, 'get_title', AsyncMock()) as title, \
                 patch.object(checker, 'capture_main_image', AsyncMock()) as image, \
                 patch.object(checker, 'read_buybox_info', AsyncMock()) as offer:
                result = await checker.check_amazon_one(EXPECTED, page=page)
                self.assertTrue(result['business_ng'])
                self.assertFalse(result['system_error'])
                self.assertEqual(result['available_qty'], 0)
                self.assertIsNone(result['amazon_price'])
                self.assertIn(result['amazon_main_image_error'], {'asin_mismatch', 'asin_unverified'})
                for call in (select, title, image, offer):
                    call.assert_not_awaited()

    async def test_identity_change_after_purchase_switch_is_blocked(self):
        page = SimpleNamespace(url=URL, goto=AsyncMock(), wait_for_timeout=AsyncMock(),
                               evaluate=AsyncMock(side_effect=[{'selected_asin': EXPECTED}, {'selected_asin': OTHER}]))
        with patch.object(checker, 'get_first_text', AsyncMock(return_value='商品ページ')), \
             patch.object(checker, 'select_one_time_purchase', AsyncMock(return_value=True)), \
             patch.object(checker, 'get_title', AsyncMock()) as title:
            result = await checker.check_amazon_one(EXPECTED, page=page)
            self.assertTrue(result['business_ng'])
            title.assert_not_awaited()

    async def test_unreadable_identity_is_not_allowed(self):
        page = SimpleNamespace(url=URL, evaluate=AsyncMock(side_effect=RuntimeError('detached')))
        result = {}
        self.assertFalse(await checker.verify_product_identity(page, EXPECTED, result))
        self.assertTrue(result['business_ng'])


if __name__ == '__main__':
    unittest.main()
