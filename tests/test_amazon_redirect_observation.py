"""Offline page snapshots; no navigation, network, orders or persistence."""
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from scripts import price_check_one_asin_db as c

OLD,NEW,OTHER = 'B000OLD001','B000NEW001','B000NEW002'
URL = 'https://www.amazon.co.jp/dp/'
IMAGE = 'https://m.media-amazon.com/images/I/new.jpg'


class RedirectTests(unittest.IsolatedAsyncioTestCase):
    def page(self, url=OLD, **changes):
        snapshot = {'url':URL+url,'identity':{'selected_asin':NEW,'canonical_url':URL+NEW},
                    'title':' New title ', 'images':[None,IMAGE]}
        snapshot.update(changes)
        return SimpleNamespace(url=URL+url,evaluate=AsyncMock(return_value=snapshot))

    async def test_old_url_or_redirected_url_can_capture_coherent_target(self):
        for url in (OLD,NEW):
            page=self.page(url)
            result=await c.capture_redirect_observation(page,OLD,{'selected_asin':NEW})
            self.assertEqual(result['target_asin'],NEW)
            self.assertEqual(result['title'],'New title')
            self.assertEqual(result['image_url'],IMAGE)
            self.assertFalse(result['error'])
            page.evaluate.assert_awaited_once()

    async def test_conflicting_dom_url_only_or_foreign_host_cannot_label_image(self):
        for evidence in ({}, {'selected_asin':OLD,'canonical_url':URL+NEW},
                         {'selected_asin':NEW,'detail_asins':[OTHER]}):
            page=self.page()
            result=await c.capture_redirect_observation(page,OLD,evidence)
            self.assertFalse(result['target_asin'])
            page.evaluate.assert_not_awaited()
        page=self.page();page.url='https://evil.invalid/dp/'+NEW
        result=await c.capture_redirect_observation(page,OLD,{'selected_asin':NEW})
        self.assertFalse(result['image_url'])

    async def test_identity_changes_during_read_are_not_cached(self):
        for changes in ({'identity':{'selected_asin':OTHER}}, {'identity':{'selected_asin':OLD}},
                        {'url':URL+OTHER}):
            result=await c.capture_redirect_observation(self.page(**changes),OLD,{'selected_asin':NEW})
            self.assertEqual(result['error'],'identity_unconfirmed')
            self.assertFalse(result['image_url'])

    async def test_error_and_missing_image_never_affect_business_result(self):
        page=self.page(images=['https://evil.invalid/image.jpg'])
        result=await c.capture_redirect_observation(page,OLD,{'selected_asin':NEW})
        self.assertEqual(result['error'],'metadata_unavailable')
        self.assertFalse(result['image_url'])
        page.evaluate.side_effect=RuntimeError('detached')
        result=await c.capture_redirect_observation(page,OLD,{'selected_asin':NEW})
        self.assertEqual(result['error'],'metadata_read_failed')

    async def test_real_guard_keeps_source_ng_and_image_empty_with_separate_preview(self):
        page=self.page();snapshot=page.evaluate.return_value
        page.evaluate.side_effect=[{'selected_asin':NEW},snapshot]
        result={'asin':OLD,'title':''}
        self.assertFalse(await c.verify_product_identity(page,OLD,result))
        self.assertTrue(result['business_ng']);self.assertEqual(result['available_qty'],0)
        self.assertIsNone(result['amazon_price']);self.assertEqual(result['title'],'')
        self.assertEqual(result['amazon_main_image_url'],'')
        self.assertEqual(result['amazon_redirect_observation']['target_asin'],NEW)

    async def test_normal_identity_clears_stale_redirect_without_extra_snapshot(self):
        page=self.page();page.evaluate.return_value={'selected_asin':OLD}
        result={}
        self.assertTrue(await c.verify_product_identity(page,OLD,result))
        self.assertIsNone(result['amazon_redirect_observation'])
        page.evaluate.assert_awaited_once()
