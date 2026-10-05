"""Cross-process, per-store write slots with priority for a manual refresh.

No schema migration or persistent queue is needed. Session advisory locks are
released by PostgreSQL when the worker exits, including a forced stop. The
priority gate is held by a refresh while it waits for the current item; normal
items release that gate immediately after acquiring the writer slot.
"""
from __future__ import annotations

from contextlib import contextmanager
import time

LISTING_WRITE_PROTOCOL_VERSION = 1


def connect_lock_db():
    from scripts.db_config import connect_db
    return connect_db(autocommit=True, connect_timeout=10,
                      options="-c statement_timeout=10000", keepalives=1,
                      keepalives_idle=30, keepalives_interval=10, keepalives_count=3)


@contextmanager
def listing_write_slot(store: str, *, priority: bool = False,
                       connect=connect_lock_db, sleep=time.sleep,
                       clock=time.monotonic, timeout: float = 1800):
    """Fail closed on DB failure/timeout; never write without both guards."""
    store = str(store).strip().lower()
    if not store:
        raise ValueError("A store is required for the listing write slot")
    connection = connect()
    gate = f"listing-write-priority-v1:{store}"
    writer = f"listing-write-item-v1:{store}"
    deadline = clock() + timeout
    try:
        with connection.cursor() as cur:
            gate_held = False
            while True:
                if clock() >= deadline:
                    raise TimeoutError("商品更新の優先枠の待機がタイムアウトしました")
                if not gate_held:
                    function = "pg_try_advisory_lock" if priority else "pg_try_advisory_lock_shared"
                    cur.execute(f"SELECT {function}(hashtextextended(%s, 0))", (gate,))
                    gate_held = bool(cur.fetchone()[0])
                acquired = False
                if gate_held:
                    cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (writer,))
                    acquired = bool(cur.fetchone()[0])
                    if not priority:
                        cur.execute("SELECT pg_advisory_unlock_shared(hashtextextended(%s, 0))", (gate,))
                        gate_held = False
                if acquired:
                    break
                sleep(0.1)
            yield
    finally:
        # Closing the dedicated session releases *all* its locks, even when
        # acquisition or an API call raised. Do not reuse this connection.
        connection.close()


def run_with_listing_write_slot(store, action, *, priority=False, on_acquired=None):
    with listing_write_slot(store, priority=priority):
        if on_acquired is not None:
            on_acquired()
        try:
            return action()
        finally:
            # Keep a one-second separation even when the next writer lives in
            # another process. It must not immediately burst another Item API
            # update after this item's last request (also on partial failure).
            time.sleep(1.0)
