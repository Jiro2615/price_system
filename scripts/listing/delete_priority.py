"""Cooperative item boundaries for managed listings and store-scoped deletion.

No process is restarted and no ASIN list is rebuilt. The listing keeps its
cursor/configuration in memory. A shared session lock covers the entire item
(including RMS writes, DB sync and result persistence); deletion takes the
exclusive version. Database errors fail closed. No schema changes are needed.
"""
from contextlib import contextmanager
import time

LISTING_DELETE_PROTOCOL_VERSION = 1


class ListingPriorityStopped(RuntimeError):
    """An explicit stop must never become an automatic resume."""


def connect_priority_db():
    from scripts.db_config import connect_db
    return connect_db(autocommit=True, connect_timeout=10,
                      options="-c statement_timeout=10000", keepalives=1,
                      keepalives_idle=30, keepalives_interval=10, keepalives_count=3)


def assert_active(cur, run_id, store):
    cur.execute("""SELECT status, desired_state, store_code FROM job_runs
        WHERE run_id=%s AND finished_at IS NULL""", (run_id,))
    row = cur.fetchone()
    if not row or row[0] != 'running' or row[1] != 'running':
        raise ListingPriorityStopped('停止要求のため、次の商品へ進まず終了します')
    if str(row[2] or '').lower() != store:
        raise ValueError('削除優先制御の店舗が実行ジョブと一致しません')


def pending_delete(cur, store):
    # Untouched plans (ready/ready) and canceled requests must not pause work.
    # stop_requested stays blocking until the deletion thread actually exits.
    cur.execute("""SELECT run_id FROM job_runs
        WHERE LOWER(store_code)=%s AND job_type='listing_delete_execute'
          AND finished_at IS NULL
          AND ((status='ready' AND desired_state='running')
               OR (status='queued' AND desired_state='queued')
               OR status IN ('running','stop_requested'))
        ORDER BY created_at,run_id LIMIT 1""", (store,))
    row = cur.fetchone()
    return str(row[0]) if row else ''


def deleted_during_run(cur, run_id, store, asin):
    # Only this run's lifetime is considered: a later explicit new listing is
    # not globally blacklisted. Save deletion intent before any external call,
    # so partial API/DB failures cannot recreate a product on resume either.
    cur.execute("""SELECT EXISTS (
        SELECT 1 FROM job_runs d JOIN job_runs owner ON owner.run_id=%s
        WHERE LOWER(d.store_code)=%s AND d.job_type='listing_delete_execute'
          AND d.started_at >= owner.started_at
          AND COALESCE(d.payload_json->'_delete_priority_asins','[]'::jsonb) ? %s
    )""", (run_id, store, asin.upper()))
    return bool(cur.fetchone()[0])


@contextmanager
def listing_item_turn(store, run_id, asin, *, connect=connect_priority_db,
                      on_stage=lambda *_: None, sleep=time.sleep):
    """Yield whether this ASIN was deleted; hold the item lease until persisted."""
    store = str(store).strip().lower()
    if not store or not run_id:
        raise ValueError('Managed listing run and store are required')
    conn = connect()
    key = f'listing-delete-item-v1:{store}'
    waiting = False
    try:
        with conn.cursor() as cur:
            while True:
                assert_active(cur, run_id, store)
                blocker = pending_delete(cur, store)
                if not blocker:
                    cur.execute('SELECT pg_try_advisory_lock_shared(hashtextextended(%s,0))', (key,))
                    if cur.fetchone()[0]:
                        # Close the race between checking the queue and taking
                        # the lease. A request just after this check may only
                        # wait for this one item; it cannot overlap its writes.
                        blocker = pending_delete(cur, store)
                        if not blocker:
                            assert_active(cur, run_id, store)
                            if waiting:
                                on_stage('resuming', '')
                            yield deleted_during_run(cur, run_id, store, asin)
                            return
                        cur.execute('SELECT pg_advisory_unlock_shared(hashtextextended(%s,0))', (key,))
                if not waiting:
                    waiting = True
                    on_stage('waiting', blocker)
                sleep(1.0)
    finally:
        conn.close()


@contextmanager
def deletion_turn(store, run_id, *, connect=connect_priority_db,
                  on_wait=lambda: None, sleep=time.sleep):
    """Wait for the in-flight item, then guard the whole deletion batch."""
    store = str(store).strip().lower()
    if not store or not run_id:
        raise ValueError('Managed deletion run and store are required')
    conn = connect()
    announced = False
    try:
        with conn.cursor() as cur:
            def check():
                # Also proves the lock-owning session is still alive before
                # each destructive item. Never reconnect without its lease.
                assert_active(cur, run_id, store)
            while True:
                check()
                cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0))',
                            (f'listing-delete-item-v1:{store}',))
                if cur.fetchone()[0]:
                    break
                if not announced:
                    announced = True
                    on_wait()
                sleep(0.25)
            check()
            yield check
    finally:
        conn.close()


async def ordered_prepared_items(queue, count):
    """Drain out-of-order preparations but execute in the input ASIN order."""
    buffered = {}
    expected = 1
    while expected <= count:
        if expected not in buffered:
            item = await queue.get()
            if item is None:
                raise RuntimeError('出品の準備結果が不足しています。未処理を飛ばさず停止しました')
            index = item[0]
            if not expected <= index <= count or index in buffered:
                raise RuntimeError('出品の準備結果が重複または順序不正です')
            buffered[index] = item
            continue
        yield buffered.pop(expected)
        expected += 1
