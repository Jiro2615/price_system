"""Optional real-lock tests. Explicit localhost-only disposable database."""
import os
import ast
from pathlib import Path
import threading
import time
import unittest
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from scripts.listing.delete_priority import listing_item_turn, deletion_turn, ListingPriorityStopped

DSN = os.getenv('LISTING_DELETE_TEST_DSN', '')


@unittest.skipUnless(DSN, 'Set an explicit disposable localhost test DSN')
class PostgresDeletePriorityTests(unittest.TestCase):
    def setUp(self):
        settings = conninfo_to_dict(DSN)
        if settings.get('host') != '127.0.0.1' or settings.get('dbname') != 'listing_delete_priority_test':
            self.fail('Only the isolated localhost listing_delete_priority_test DB is allowed')
        self.schema = 'delete_priority_' + uuid.uuid4().hex
        with psycopg.connect(DSN) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.cleanup_schema)
        with self.connect() as conn:
            conn.execute('''CREATE TABLE job_runs(run_id text primary key, job_type text, store_code text,
                status text, desired_state text, created_at timestamptz default now(), started_at timestamptz,
                finished_at timestamptz, payload_json jsonb default '{}',
                approval_required boolean default false, approved_at timestamptz);
                INSERT INTO job_runs(run_id,job_type,store_code,status,desired_state,started_at)
                VALUES('listing','listing_bulk_execute','fixture_store','running','running',now()-interval '10 seconds')''')

    def connect(self):
        return psycopg.connect(DSN, autocommit=True, options=f'-c search_path={self.schema},pg_catalog -c statement_timeout=3000')

    def readonly(self):
        conn = self.connect()
        conn.execute('SET default_transaction_read_only=on')
        return conn

    def cleanup_schema(self):
        with psycopg.connect(DSN) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def add_delete(self, status='running', desired='running'):
        with self.connect() as conn:
            conn.execute('''INSERT INTO job_runs(run_id,job_type,store_code,status,desired_state,started_at)
                VALUES('delete','listing_delete_execute','fixture_store',%s,%s,now())''', (status, desired))

    def test_real_sessions_finish_current_item_before_delete_and_resume(self):
        current, allow_finish, deleted, allow_delete_finish, resumed = [threading.Event() for _ in range(5)]
        sequence, errors = [], []
        def listing():
            try:
                with listing_item_turn('fixture_store', 'listing', 'B000000001', connect=self.connect):
                    sequence.append('item1'); current.set(); allow_finish.wait(3)
                    sequence.append('persist1')
                with listing_item_turn('fixture_store', 'listing', 'B000000002', connect=self.connect, sleep=lambda _: time.sleep(.01)):
                    sequence.append('item2'); resumed.set()
            except BaseException as exc: errors.append(exc)
        def delete():
            try:
                with deletion_turn('fixture_store', 'delete', connect=self.readonly, sleep=lambda _: time.sleep(.01)):
                    sequence.append('delete'); deleted.set(); allow_delete_finish.wait(3)
                with self.connect() as conn:
                    conn.execute("UPDATE job_runs SET status='succeeded',desired_state='stopped',finished_at=now() WHERE run_id='delete'")
            except BaseException as exc: errors.append(exc)
        threads = [threading.Thread(target=listing), threading.Thread(target=delete)]
        try:
            threads[0].start(); self.assertTrue(current.wait(2))
            self.add_delete(); threads[1].start()
            self.assertFalse(deleted.is_set())
            allow_finish.set(); self.assertTrue(deleted.wait(2)); self.assertFalse(resumed.is_set())
            allow_delete_finish.set(); self.assertTrue(resumed.wait(2))
        finally:
            allow_finish.set(); allow_delete_finish.set()
            for thread in threads:
                if thread.ident: thread.join(4)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sequence, ['item1', 'persist1', 'delete', 'item2'])

    def test_json_intent_blocks_only_current_run_not_later_explicit_relisting(self):
        self.add_delete()
        with self.connect() as conn:
            conn.execute('''UPDATE job_runs SET status='failed',desired_state='stopped',finished_at=now(),
                payload_json='{"_delete_priority_asins":["B000000001"]}' WHERE run_id='delete' ''')
            conn.execute('''INSERT INTO job_runs(run_id,job_type,store_code,status,desired_state,started_at)
                VALUES('new','listing_bulk_execute','fixture_store','running','running',now()+interval '10 seconds')''')
        with listing_item_turn('fixture_store', 'listing', 'B000000001', connect=self.connect) as skip:
            self.assertTrue(skip)
        with listing_item_turn('fixture_store', 'new', 'B000000001', connect=self.connect) as skip:
            self.assertFalse(skip)

    def test_unrequested_plan_does_not_hold_and_operator_stop_wins(self):
        self.add_delete('ready', 'ready')
        with listing_item_turn('fixture_store', 'listing', 'B000000001', connect=self.connect): pass
        with self.connect() as conn:
            conn.execute("UPDATE job_runs SET desired_state='running' WHERE run_id='delete'")
        def stop(_):
            with self.connect() as conn:
                conn.execute("UPDATE job_runs SET status='stop_requested',desired_state='stopped' WHERE run_id='listing'")
        with self.assertRaises(ListingPriorityStopped):
            with listing_item_turn('fixture_store', 'listing', 'B000000001', connect=self.connect, sleep=stop):
                self.fail('Manual stop was ignored')

    def test_queued_delete_can_be_promoted_despite_running_listing(self):
        source = Path(__file__).resolve().parents[2] / 'web_orchestrator/scripts/orchestrator_server.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start_next_queued_listing_run')
        guard_sql = next(n.value for n in ast.walk(function)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and 'SELECT 1' in n.value and 'NOT EXISTS' in n.value)
        self.add_delete('queued', 'queued')
        with self.connect() as conn:
            self.assertIsNone(conn.execute(guard_sql, ('fixture_store',)).fetchone())
        def finish_queued(_):
            with self.connect() as conn:
                conn.execute("UPDATE job_runs SET status='canceled',desired_state='stopped',finished_at=now() WHERE run_id='delete'")
        with listing_item_turn('fixture_store', 'listing', 'B000000001', connect=self.connect, sleep=finish_queued): pass
        with self.connect() as conn:
            self.assertEqual(conn.execute(guard_sql, ('fixture_store',)).fetchone(), (1,))


if __name__ == '__main__': unittest.main()
