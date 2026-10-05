"""Offline session-lock simulation: no PostgreSQL or external API access."""
import threading
import time
import unittest
from unittest.mock import Mock, patch

from scripts.listing.write_coordination import listing_write_slot, run_with_listing_write_slot


class LockServer:
    def __init__(self):
        self.mutex = threading.Lock()
        self.exclusive = {}
        self.shared = {}
        self.priority_acquired = threading.Event()
        self.connections = []

    def connect(self):
        connection = Session(self)
        self.connections.append(connection)
        return connection


class Session:
    def __init__(self, server):
        self.server = server
        self.closed = False
        self.result = False

    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def fetchone(self): return (self.result,)

    def execute(self, sql, params):
        key = params[0]
        server = self.server
        with server.mutex:
            owner = server.exclusive.get(key)
            readers = server.shared.setdefault(key, set())
            if "pg_advisory_unlock_shared" in sql:
                readers.discard(self)
                self.result = True
            elif "pg_try_advisory_lock_shared" in sql:
                self.result = owner is None
                if self.result: readers.add(self)
            elif "pg_try_advisory_lock" in sql:
                self.result = owner is None and not readers
                if self.result:
                    server.exclusive[key] = self
                    if "priority" in key: server.priority_acquired.set()
            else:
                raise AssertionError(sql)

    def close(self):
        with self.server.mutex:
            self.closed = True
            self.server.exclusive = {k: v for k, v in self.server.exclusive.items() if v is not self}
            for readers in self.server.shared.values(): readers.discard(self)


class WriteSlotTests(unittest.TestCase):
    def test_current_item_finishes_then_priority_then_bulk_continues(self):
        server = LockServer()
        current_entered, release_current = threading.Event(), threading.Event()
        priority_entered, release_priority = threading.Event(), threading.Event()
        bulk_entered = threading.Event()
        sequence, errors = [], []
        def run(name, priority, entered, release=None):
            try:
                with listing_write_slot("rakuten_2", priority=priority, connect=server.connect, timeout=3):
                    sequence.append(name)
                    entered.set()
                    if release and not release.wait(3): raise TimeoutError(name)
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=run, args=("current", False, current_entered, release_current)),
                   threading.Thread(target=run, args=("refresh", True, priority_entered, release_priority)),
                   threading.Thread(target=run, args=("next_bulk", False, bulk_entered))]
        try:
            threads[0].start(); self.assertTrue(current_entered.wait(2))
            threads[1].start(); self.assertTrue(server.priority_acquired.wait(2))
            threads[2].start()
            self.assertFalse(priority_entered.is_set()); self.assertFalse(bulk_entered.is_set())
            release_current.set(); self.assertTrue(priority_entered.wait(2))
            self.assertFalse(bulk_entered.is_set())
            release_priority.set(); self.assertTrue(bulk_entered.wait(2))
        finally:
            release_current.set(); release_priority.set()
            for thread in threads:
                if thread.ident: thread.join(4)
        self.assertEqual(errors, [])
        self.assertEqual(sequence, ["current", "refresh", "next_bulk"])
        self.assertTrue(all(c.closed for c in server.connections))

    def test_other_store_does_not_wait_and_exception_releases_locks(self):
        server = LockServer()
        with self.assertRaisesRegex(RuntimeError, "API failed"):
            with listing_write_slot("rakuten_2", priority=True, connect=server.connect):
                with listing_write_slot("rakuten_1", connect=server.connect): pass
                raise RuntimeError("API failed")
        with listing_write_slot("rakuten_2", connect=server.connect): pass
        self.assertTrue(all(c.closed for c in server.connections))
        self.assertEqual(server.exclusive, {})

    def test_timeout_releases_priority_gate(self):
        server = LockServer()
        with listing_write_slot("rakuten_2", connect=server.connect):
            with self.assertRaises(TimeoutError):
                with listing_write_slot("rakuten_2", priority=True, connect=server.connect,
                                        clock=Mock(side_effect=[0, 0, 2]), timeout=1, sleep=lambda _: None):
                    self.fail("Must never enter")
        with listing_write_slot("rakuten_2", connect=server.connect): pass
        self.assertTrue(all(c.closed for c in server.connections))

    def test_db_error_never_calls_action(self):
        action = Mock()
        with patch("scripts.listing.write_coordination.listing_write_slot", side_effect=RuntimeError("DB failed")):
            with self.assertRaises(RuntimeError): run_with_listing_write_slot("shop", action, priority=True)
        action.assert_not_called()

    def test_cooldown_runs_inside_slot_even_after_api_failure(self):
        from contextlib import contextmanager
        events = []
        @contextmanager
        def slot(*_, **kwargs):
            events.append("acquire")
            try: yield
            finally: events.append("release")
        def action():
            events.append("API")
            raise RuntimeError("API failure")
        with patch("scripts.listing.write_coordination.listing_write_slot", slot), \
             patch("scripts.listing.write_coordination.time.sleep", side_effect=lambda seconds: events.append(seconds)):
            with self.assertRaises(RuntimeError):
                run_with_listing_write_slot("shop", action, priority=True)
        self.assertEqual(events, ["acquire", "API", 1.0, "release"])

    def test_empty_store_rejected_before_connection(self):
        connect = Mock()
        with self.assertRaises(ValueError):
            with listing_write_slot(" ", connect=connect): pass
        connect.assert_not_called()


if __name__ == "__main__": unittest.main()
