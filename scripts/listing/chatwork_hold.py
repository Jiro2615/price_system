"""Keep the challenged listing tab open only for an acknowledged notification."""
import asyncio
import os
import re
import time
import uuid


def request_notice(store, run, asin):
    from scripts.db_config import connect_db
    key = uuid.uuid4().hex
    with connect_db(autocommit=True, connect_timeout=3,
                    options="-c statement_timeout=3000 -c lock_timeout=1000") as conn, conn.cursor() as cur:
        cur.execute("""SELECT 1 FROM stores s JOIN store_settings ss ON ss.store_id=s.id
            JOIN job_runs j ON j.store_code=s.store_code
            WHERE s.store_code=%s AND j.run_id=%s AND j.status='running'
              AND j.job_type IN ('listing_bulk_execute','listing_forced_word_execute','listing_forced_word_db_execute')
              AND ss.order_fulfillment_settings_json #>> '{listing_chatwork,enabled}'='true'""", (store, run))
        if not cur.fetchone():
            return False
        cur.execute("""INSERT INTO listing_chatwork_pulse AS p
            (store_code, request_key, run_id, asin, requested_at, state)
            VALUES (%s,%s,%s,%s,clock_timestamp(),'pending')
            ON CONFLICT (store_code) DO UPDATE SET request_key=EXCLUDED.request_key,
                run_id=EXCLUDED.run_id, asin=EXCLUDED.asin, requested_at=clock_timestamp(), state='pending'
            WHERE (p.sent_at IS NULL OR p.sent_at <= clock_timestamp()-interval '10 minutes')
              AND (p.state='sent' OR p.requested_at < clock_timestamp()-interval '30 seconds')
            RETURNING request_key""", (store, key, run, asin))
        if not cur.fetchone():
            return False
        # The central relay may only START a post within 12s of the request.
        # No DB transaction is held during either the acknowledgement or UI pause.
        deadline = time.monotonic() + 26
        while time.monotonic() < deadline:
            cur.execute("SELECT state FROM listing_chatwork_pulse WHERE store_code=%s AND request_key=%s", (store,key))
            row = cur.fetchone()
            if not row or row[0] != 'pending':
                return bool(row and row[0] == 'sent')
            time.sleep(.7)
    return False


class ListingTabHold:
    def __init__(self, store, active, *, notify=request_notice, sleep=asyncio.sleep, clock=time.monotonic):
        self.store = store
        self.run = os.getenv("WEB_ORCHESTRATOR_MANAGED_RUN_ID", "") if active else ""
        self.notify, self.sleep, self.clock = notify, sleep, clock
        self.next_check = 0.
        self.gate = asyncio.Event()
        self.gate.set()

    async def after_result(self, asin, result):
        if (not self.run or not re.fullmatch(r"[A-Z0-9]{10}", asin)
                or result.get("listing_status") != "amazon_confirmation_waiting"
                or result.get("listing_reason") != "Amazon認証待ち: 商品情報・在庫は更新していません"):
            return
        if not self.gate.is_set():
            await self.gate.wait()
            return
        if self.clock() < self.next_check:
            return
        self.gate.clear()
        try:
            if await asyncio.to_thread(self.notify, self.store, self.run, asin):
                # The DB enforces the store-wide 10-minute interval. Don't mirror
                # it here: this PC can receive the acknowledgement slightly later.
                print(f"CHATWORK_SENT: {asin} 認証画面のまま60秒待機します", flush=True)
                await self.sleep(60)
        except Exception as exc:
            print(f"CHATWORK_NOTICE_UNAVAILABLE: {type(exc).__name__}", flush=True)
            self.next_check = self.clock() + 10
        finally:
            self.gate.set()
