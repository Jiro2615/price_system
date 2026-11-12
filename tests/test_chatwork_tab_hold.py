import asyncio
import os
import unittest
from unittest.mock import patch, Mock

from scripts.listing.chatwork_hold import ListingTabHold

HIT = dict(listing_status="amazon_confirmation_waiting", listing_reason="Amazon認証待ち: 商品情報・在庫は更新していません")


class HoldTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_acknowledged_post_holds_exactly_60_seconds_and_other_tabs_wait(self):
        entered, release, navigated = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def sleep(seconds):
            self.assertEqual(seconds, 60)
            self.assertFalse(hold.gate.is_set())
            entered.set()
            await release.wait()
        with patch.dict(os.environ, WEB_ORCHESTRATOR_MANAGED_RUN_ID="run_one"):
            notify = Mock(return_value=True)
            hold = ListingTabHold("rakuten_1", True, notify=notify, sleep=sleep)
        async def next_tab():
            await hold.gate.wait()
            navigated.set()
        first = asyncio.create_task(hold.after_result("B000000001", HIT))
        await asyncio.wait_for(entered.wait(), 2)
        second = asyncio.create_task(hold.after_result("B000000002", HIT))
        next_page = asyncio.create_task(next_tab())
        await asyncio.sleep(0)
        self.assertFalse(navigated.is_set())
        release.set()
        await asyncio.gather(first, second, next_page)
        notify.assert_called_once_with("rakuten_1", "run_one", "B000000001")
        self.assertTrue(navigated.is_set())

    async def test_no_pause_for_refresh_other_wait_suppression_or_delivery_failure(self):
        for active, result, outcome, calls in [
            (False, HIT, True, 0), (True, dict(HIT,listing_reason="ショッピング継続確認"), True, 0),
            (True,HIT,False,1), (True,HIT,OSError(),1),
        ]:
            with patch.dict(os.environ, WEB_ORCHESTRATOR_MANAGED_RUN_ID="run_one"):
                notify = Mock(side_effect=[outcome])
                hold = ListingTabHold("rakuten_1",active,notify=notify,sleep=Mock(side_effect=AssertionError))
            await hold.after_result("B000000001",result)
            self.assertEqual(calls, notify.call_count)
            self.assertEqual(hold.sleep.call_count, 0)
            self.assertTrue(hold.gate.is_set())
