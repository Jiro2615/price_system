import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock, AsyncMock

from scripts.listing.chatwork_hold import ListingTabHold
from scripts.listing import amazon_bridge

HIT = SimpleNamespace(human_verification_required=True)


class HoldTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_detection_holds_regardless_of_notice_outcome_or_managed_run(self):
        for run, outcome in [("run_one", True), ("run_one", False), ("run_one", OSError()), ("", False)]:
            with self.subTest(run=run, outcome=outcome), patch.dict(os.environ, WEB_ORCHESTRATOR_MANAGED_RUN_ID=run):
                now=[1000.]
                async def advance(seconds): now[0]+=seconds
                notify=Mock(side_effect=[outcome,outcome])
                hold=ListingTabHold("rakuten_1",True,notify=notify,clock=lambda:now[0],sleep=AsyncMock(side_effect=advance))
                for asin in ["B000000001", "B000000002"]:
                    hold.observe(asin,HIT)
                    if run: await hold.notice_task
                    await hold.wait()
                self.assertEqual([c.args for c in hold.sleep.await_args_list],[(60.,),(60.,)])
                self.assertEqual(notify.call_count,2 if run else 0)

    async def test_second_in_flight_hit_extends_deadline_for_existing_waiter(self):
        now=[0.]
        delays=[]
        entered=asyncio.Queue()
        async def sleep(seconds):
            delays.append(seconds)
            wake=asyncio.Event()
            await entered.put(wake)
            await wake.wait()
        with patch.dict(os.environ,WEB_ORCHESTRATOR_MANAGED_RUN_ID=""):
            hold=ListingTabHold("rakuten_1",True,clock=lambda:now[0],sleep=sleep)
        hold.observe("B000000001",HIT)
        waiting=asyncio.create_task(hold.wait())
        wake=await asyncio.wait_for(entered.get(),1)
        now[0]=45
        hold.observe("B000000002",HIT)
        now[0]=60
        wake.set()
        wake=await asyncio.wait_for(entered.get(),1)
        self.assertFalse(waiting.done())
        self.assertEqual(delays,[60,45])
        now[0]=105
        wake.set()
        await asyncio.wait_for(waiting,1)

    async def test_refresh_and_non_human_confirmation_do_not_hold_or_notify(self):
        for active, result in [(False,HIT),(True,SimpleNamespace(amazon_confirmation_waiting=True))]:
            hold=ListingTabHold("rakuten_1",active,notify=Mock(),sleep=AsyncMock())
            hold.observe("B000000001",result)
            await hold.wait()
            hold.sleep.assert_not_awaited()
            hold.notify.assert_not_called()
            self.assertIsNone(hold.notice_task)

    async def test_bridge_preserves_only_explicit_checker_flag(self):
        for flag, expected in [(True,True),(False,False),(None,False)]:
            checker=SimpleNamespace(check_amazon_one=AsyncMock(return_value={
                "amazon_confirmation_waiting":True,"human_verification_required":flag}))
            with patch.object(amazon_bridge,"_load_amazon_module",return_value=checker):
                result=await amazon_bridge.fetch_amazon_result("B000000001")
            self.assertEqual(result.human_verification_required,expected)
