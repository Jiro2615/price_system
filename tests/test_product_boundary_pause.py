"""No browser or production DB: exercise the real per-product control flow."""
import asyncio
import io
import sys
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch
from test_amazon_db_resilience import price_check_from_db as worker


class ProductPauseTests(unittest.TestCase):
    def run_batch(self, signals, failure=False):
        events=[]
        asins=['B000000001','B000000002','B000000003']
        async def check(asin, **kwargs):
            events.append(('check',asin))
            if failure:
                raise RuntimeError('sample page error')
            return {'asin':asin,'system_error':False,'business_ng':False}
        def save(data): events.append(('save',data['asin']))
        def stats(asin,data): events.append(('stats',asin))
        def release(remaining,worker_id=None): events.append(('release',remaining,worker_id))
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            stack.enter_context(patch.object(sys,'argv',['check','--use-stats','--worker-id','worker-test','--summary']))
            for name in ['ensure_amazon_check_stats_schema','ensure_amazon_check_stats_rows',
                         'ensure_amazon_check_worker_runs_schema','save_worker_run_summary','print_db_summary',
                         'print_claimed_asins','DesktopCheckStatus']:
                stack.enter_context(patch.object(worker,name))
            for name,value in [('release_expired_processing_locks',0),
                               ('claim_target_asins_by_stats',[{'asin':a} for a in asins]),
                               ('get_previous_amazon_state',{}),('get_existing_stats',{}),
                               ('fetch_store_codes_for_asin',[]),('is_long_zero_stock_for_active_listings',False),
                               ('determine_stats_update',{'system_error_detected':False,'change_detected':False,'stable_detected':True})]:
                stack.enter_context(patch.object(worker,name,return_value=value))
            stack.enter_context(patch.object(worker,'maintenance_pause_requested',side_effect=signals))
            stack.enter_context(patch.object(worker,'check_amazon_one',side_effect=check))
            stack.enter_context(patch.object(worker,'create_amazon_page',new=AsyncMock(return_value=(None,None,None,None))))
            close=stack.enter_context(patch.object(worker,'close_amazon_page',new=AsyncMock()))
            stack.enter_context(patch.object(worker,'save_to_db',side_effect=save))
            stack.enter_context(patch.object(worker,'update_amazon_check_stats',side_effect=stats))
            stack.enter_context(patch.object(worker,'release_claimed_asins',side_effect=release))
            summary=stack.enter_context(patch.object(worker,'build_worker_run_summary',return_value='summary'))
            self.assertEqual(asyncio.run(worker.main()),0)
            self.assertGreaterEqual(close.await_count,1)
            count=summary.call_args.args[0]['checked_count']
        return events,count

    def test_pause_after_product_commits_before_releasing_remainder(self):
        events,count=self.run_batch([False,True])
        self.assertEqual(events,[('check','B000000001'),('save','B000000001'),('stats','B000000001'),
                                 ('release',['B000000002','B000000003'],'worker-test')])
        self.assertEqual(count,1)

    def test_pause_before_first_product(self):
        events,count=self.run_batch([True])
        self.assertEqual(events,[('release',['B000000001','B000000002','B000000003'],'worker-test')])
        self.assertEqual(count,0)

    def test_no_pause_checks_all_products(self):
        events,count=self.run_batch([False]*3)
        self.assertEqual(count,3)
        self.assertFalse(any(e[0]=='release' for e in events))

    def test_page_error_is_saved_before_pause(self):
        events,count=self.run_batch([False,True],failure=True)
        self.assertEqual(count,1)
        self.assertEqual(events[1],('stats','B000000001'))
        self.assertEqual(events[-1][0],'release')

    def test_release_only_our_processing_rows(self):
        conn=MagicMock()
        cur=conn.cursor.return_value.__enter__.return_value
        with patch.object(worker,'connect_db',return_value=conn):
            worker._release_claimed_asins_without_retry(['B000000002'],'worker-test')
        sql,params=cur.execute.call_args.args
        self.assertIn("status = 'processing' AND worker_id = %s",sql)
        self.assertEqual(params,(['B000000002'],'worker-test'))
        self.assertNotIn('next_check_at',sql)
        conn.commit.assert_called_once()


if __name__=='__main__': unittest.main()
