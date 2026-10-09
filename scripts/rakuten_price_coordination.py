"""Per-item price/attribute write slots. Session locks, no schema or data writes."""
from contextlib import contextmanager
from db_config import connect_db

RAKUTEN_PRICE_ITEM_LOCK_PROTOCOL = 1


@contextmanager
def price_item_write_slot(store, manage_number, *, connect=connect_db):
    key = "rakuten-price-item:" + str(store).strip().lower() + ":" + str(manage_number).strip().lower()
    conn = connect(connect_timeout=10)
    conn.autocommit = True
    acquired = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))",(key,))
            acquired = bool(cur.fetchone()[0])
        yield acquired
    finally:
        try:
            if acquired:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))",(key,))
        finally:
            conn.close()
