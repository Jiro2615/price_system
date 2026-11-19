"""Actual batch loop with fake observations, transports and job/lock database."""
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from scripts import rakuten_listing_batch_execute as batch
from scripts.listing.delete_priority import listing_item_turn, deletion_turn
from test_listing_batch_fast_pipeline import arguments
from test_listing_delete_priority import Database


class BatchDeletePriorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_wait_resume_keeps_original_order_conditions_and_skips_deleted_target(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as patches:
            db = Database()
            args = arguments(folder)
            args.store = 'rakuten_2'
            args.ignore_rules = 'past_ng,prohibited_words'
            args.minimum_rakuten_shops = 7
            ids = ['B000000001', 'B000000002', 'B000000003']
            calls, errors = [], []
            delete_thread = None
            patches.enter_context(patch.dict(os.environ, WEB_ORCHESTRATOR_MANAGED_RUN_ID='listing'))
            for target in ('psycopg.connect', 'requests.sessions.Session.request'):
                patches.enter_context(patch(target, side_effect=AssertionError('Live external action forbidden')))
            for name in ('BatchLocalData', 'build_preflight_result', 'build_mock_execute_result', 'build_real_readiness_result'):
                patches.enter_context(patch.object(batch, name, return_value={}))
            def dry(request, **_):
                if request.asin == ids[0]: time.sleep(.02)  # complete preparation out of order
                return {'asin': request.asin, 'management_number': 'item' + request.asin,
                        'listing_status': 'eligible', 'amazon_result': 'amazon', 'keepa_result': 'keepa'}
            patches.enter_context(patch.object(batch, 'precheck_local_listing_exclusion', side_effect=dry))
            def validate(current_args, asin, result):
                self.assertIs(current_args, args)
                self.assertEqual(args.bypass_rules, ('past_ng', 'prohibited_words'))
                self.assertEqual(args.minimum_rakuten_shops, 7)
                return result
            patches.enter_context(patch.object(batch, 'revalidate_prepared_listing', side_effect=validate))
            patches.enter_context(patch.object(batch, 'listing_item_turn', side_effect=lambda store, rid, asin, **kw:
                listing_item_turn(store, rid, asin, connect=db.connect, sleep=lambda _: time.sleep(.002), **kw)))
            patches.enter_context(patch.object(batch, 'load_company_brand_ng', return_value={}))
            patches.enter_context(patch('scripts.listing.listing_duplicate_check.find_existing_listing', return_value=None))
            patches.enter_context(patch.object(batch, 'run_with_listing_write_slot',
                side_effect=lambda store, action, **_: action()))
            def delete():
                try:
                    db.jobs['delete'][0] = 'running'
                    with deletion_turn('rakuten_2', 'delete', connect=db.connect, sleep=lambda _: time.sleep(.002)):
                        rows = (Path(folder) / 'results.jsonl').read_text(encoding='utf-8').splitlines()
                        self.assertEqual([json.loads(row)['asin'] for row in rows], [ids[0]])
                        calls.append('delete')
                        db.deleted.add(('listing', 'rakuten_2', ids[1]))
                    db.finish('delete')
                except BaseException as exc:
                    errors.append(exc); db.finish('delete', 'failed')
            def execute(request, **_):
                nonlocal delete_thread
                calls.append(request.asin)
                if request.asin == ids[0]:
                    db.request_delete()
                    delete_thread = threading.Thread(target=delete, daemon=True)
                    delete_thread.start()
                return {'asin': request.asin, 'final_status': 'completed'}
            patches.enter_context(patch.object(batch, 'build_real_execute_result', side_effect=execute))
            patches.enter_context(patch.object(batch, 'sync_listing_result_to_db',
                return_value={'external_db_writes_performed': True}))
            self.assertEqual(await asyncio.wait_for(batch.run_batch(args, ids), 5), 0)
            if delete_thread: delete_thread.join(2)
            self.assertEqual(errors, [])
            self.assertEqual(calls, [ids[0], 'delete', ids[2]])
            rows = [json.loads(row) for row in (Path(folder) / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([row['asin'] for row in rows], ids)
            self.assertEqual([row['batch_index'] for row in rows], [1, 2, 3])
            self.assertEqual(rows[1]['final_status'], 'deleted_during_run')
            self.assertTrue(all(session.closed for session in db.sessions))


if __name__ == '__main__': unittest.main()
