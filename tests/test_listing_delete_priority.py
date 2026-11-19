"""No live DB/API: deterministic competing sessions exercise item boundaries."""
import asyncio
import threading
import time
import unittest
from unittest.mock import Mock

from scripts.listing.delete_priority import (
    listing_item_turn, deletion_turn, ListingPriorityStopped, ordered_prepared_items,
)


class Database:
    def __init__(self):
        self.mutex = threading.RLock()
        self.jobs = {'listing': ['running', 'running', 'rakuten_2']}
        self.deletes = []
        self.deleted = set()
        self.readers = {}
        self.writers = {}
        self.sessions = []
        self.fail_query = False

    def connect(self):
        session = Session(self)
        self.sessions.append(session)
        return session

    def request_delete(self, rid='delete', store='rakuten_2', state='ready', desired='running'):
        with self.mutex:
            self.jobs[rid] = [state, desired, store]
            self.deletes.append(rid)

    def finish(self, rid, state='succeeded'):
        with self.mutex:
            self.jobs[rid][0:2] = [state, 'stopped']


class Session:
    def __init__(self, db):
        self.db, self.result, self.closed = db, None, False

    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def fetchone(self): return self.result

    def execute(self, sql, params):
        db = self.db
        with db.mutex:
            if db.fail_query:
                raise ConnectionError('fixture DB unavailable')
            if 'SELECT status, desired_state, store_code' in sql:
                self.result = db.jobs.get(params[0])
            elif 'SELECT run_id FROM job_runs' in sql:
                self.result = next(((rid,) for rid in db.deletes
                    if db.jobs[rid][2] == params[0] and (
                        db.jobs[rid][0:2] in (['ready', 'running'], ['queued', 'queued']) or
                        db.jobs[rid][0] in {'running', 'stop_requested'})), None)
            elif 'SELECT EXISTS' in sql:
                self.result = (tuple(params) in db.deleted,)
            elif 'pg_' in sql:
                key = params[0]
                readers = db.readers.setdefault(key, set())
                if 'pg_advisory_unlock_shared' in sql:
                    readers.discard(self)
                    self.result = (True,)
                elif 'pg_try_advisory_lock_shared' in sql:
                    acquired = key not in db.writers
                    if acquired: readers.add(self)
                    self.result = (acquired,)
                else:
                    acquired = key not in db.writers and not readers
                    if acquired: db.writers[key] = self
                    self.result = (acquired,)
            else:
                raise AssertionError(sql)

    def close(self):
        with self.db.mutex:
            self.closed = True
            self.db.writers = {key: session for key, session in self.db.writers.items() if session is not self}
            for readers in self.db.readers.values(): readers.discard(self)


class DeletePriorityTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.errors = []
        self.threads = []
        self.addCleanup(self.join_threads)

    def join_threads(self):
        for thread in self.threads: thread.join(3)
        self.assertFalse(any(t.is_alive() for t in self.threads))

    def start(self, action):
        def run():
            try: action()
            except BaseException as exc: self.errors.append(exc)
        thread = threading.Thread(target=run, daemon=True)
        self.threads.append(thread)
        thread.start()

    def options(self):
        return {'connect': self.db.connect, 'sleep': lambda _: time.sleep(.002)}

    def test_current_item_db_and_result_finish_then_delete_then_original_remainder(self):
        started, finish_item, delete_entered, release_delete, paused = [threading.Event() for _ in range(5)]
        events, options = [], {'rules': ['past_ng'], 'workers': 2}
        self.addCleanup(finish_item.set)
        self.addCleanup(release_delete.set)
        def listing():
            for asin in ('A', 'B', 'C'):
                with listing_item_turn('rakuten_2', 'listing', asin,
                        on_stage=lambda stage, _: paused.set() if stage == 'waiting' else None, **self.options()):
                    self.assertEqual(options, {'rules': ['past_ng'], 'workers': 2})
                    events.append(asin + ':API')
                    if asin == 'A':
                        started.set()
                        self.assertTrue(finish_item.wait(2))
                    events.extend((asin + ':DB', asin + ':result'))
        def delete():
            self.db.jobs['delete'][0] = 'running'
            with deletion_turn('rakuten_2', 'delete', **self.options()) as check:
                check(); events.append('delete'); delete_entered.set()
                self.assertTrue(release_delete.wait(2))
            self.db.finish('delete')
        self.start(listing)
        self.assertTrue(started.wait(2))
        self.db.request_delete()
        self.start(delete)
        self.assertFalse(delete_entered.is_set())
        finish_item.set()
        self.assertTrue(delete_entered.wait(2))
        self.assertTrue(paused.wait(2))
        self.assertNotIn('B:API', events)
        release_delete.set()
        self.join_threads()
        self.assertEqual(self.errors, [])
        self.assertEqual(events, ['A:API', 'A:DB', 'A:result', 'delete',
                                  'B:API', 'B:DB', 'B:result', 'C:API', 'C:DB', 'C:result'])
        self.assertTrue(all(s.closed for s in self.db.sessions))

    def test_all_requested_deletes_finish_before_resume_including_failure(self):
        self.db.request_delete('d1')
        self.db.request_delete('d2')
        steps = []
        def advance(_):
            if not steps:
                self.db.finish('d1', 'failed')
            else:
                self.db.finish('d2', 'canceled')
            steps.append('poll')
        with listing_item_turn('rakuten_2', 'listing', 'A', connect=self.db.connect, sleep=advance):
            self.assertEqual(steps, ['poll', 'poll'])

    def test_operator_stop_during_wait_never_resumes(self):
        self.db.request_delete()
        def stop(_):
            self.db.finish('listing', 'canceled')
            self.db.finish('delete')
        with self.assertRaises(ListingPriorityStopped):
            with listing_item_turn('rakuten_2', 'listing', 'A', connect=self.db.connect, sleep=stop):
                self.fail('Stopped listing resumed')

    def test_other_store_and_unrequested_delete_are_ignored(self):
        self.db.request_delete('other', store='rakuten_1')
        self.db.request_delete('plan', desired='ready')
        sleep = Mock(side_effect=AssertionError('Must not wait'))
        with listing_item_turn('rakuten_2', 'listing', 'A', connect=self.db.connect, sleep=sleep): pass
        sleep.assert_not_called()

    def test_deleted_target_is_not_recreated_in_same_run(self):
        self.db.deleted.add(('listing', 'rakuten_2', 'B'))
        for asin, expected in [('A', False), ('B', True), ('C', False)]:
            with listing_item_turn('rakuten_2', 'listing', asin, **self.options()) as deleted:
                self.assertEqual(deleted, expected)

    def test_db_failure_and_store_mismatch_fail_before_any_action(self):
        for fail in (False, True):
            self.db.fail_query = fail
            with self.assertRaises((ValueError, ConnectionError)):
                with listing_item_turn('wrong', 'listing', 'A', **self.options()):
                    self.fail('Must not execute')
        self.assertTrue(all(s.closed for s in self.db.sessions))

    def test_stopped_delete_never_performs_next_item_and_releases_lease(self):
        self.db.request_delete(state='running')
        with self.assertRaises(ListingPriorityStopped):
            with deletion_turn('rakuten_2', 'delete', **self.options()) as check:
                self.db.jobs['delete'][0:2] = ['stop_requested', 'stopped']
                check()
        self.db.finish('delete', 'canceled')
        with listing_item_turn('rakuten_2', 'listing', 'A', **self.options()): pass
        self.assertEqual(self.db.writers, {})


class OrderedPreparationTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_preparation_is_consumed_in_original_order(self):
        queue = asyncio.Queue()
        for item in [(3, 'C', {}), (2, 'B', {}), (1, 'A', {}), None]:
            queue.put_nowait(item)
        self.assertEqual([item[1] async for item in ordered_prepared_items(queue, 3)], ['A', 'B', 'C'])

    async def test_missing_preparation_does_not_silently_skip_an_asin(self):
        queue = asyncio.Queue()
        queue.put_nowait((2, 'B', {})); queue.put_nowait(None)
        with self.assertRaises(RuntimeError):
            [item async for item in ordered_prepared_items(queue, 2)]


if __name__ == '__main__': unittest.main()
