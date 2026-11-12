"""Pause new Amazon navigation on every human challenge, independently of notification."""
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
        self.active = active
        self.run = os.getenv("WEB_ORCHESTRATOR_MANAGED_RUN_ID", "")
        self.notify, self.sleep, self.clock = notify, sleep, clock
        self.next_check = 0.
        self.hold_until = 0.
        self.notice_task = None

    def observe(self, asin, result):
        if not self.active or getattr(result, "human_verification_required", False) is not True:
            return
        now = self.clock()
        self.hold_until = now + 60
        print(f"LISTING_HUMAN_VERIFICATION_HOLD: {asin} 検知から60秒、次のAmazonページへ進みません", flush=True)
        if (self.run and re.fullmatch(r"[A-Z0-9]{10}", asin) and now >= self.next_check
                and (self.notice_task is None or self.notice_task.done())):
            self.notice_task = asyncio.create_task(self._notify(asin))

    async def wait(self):
        # Another in-flight tab can detect a challenge during sleep. Its own
        # full minute must elapse before new navigations (or batch exit).
        while (remaining := self.hold_until - self.clock()) > 0:
            await self.sleep(remaining)

    async def _notify(self, asin):
        try:
            if await asyncio.to_thread(self.notify, self.store, self.run, asin):
                print(f"CHATWORK_SENT: {asin}", flush=True)
        except Exception as exc:
            print(f"CHATWORK_NOTICE_UNAVAILABLE: {type(exc).__name__}", flush=True)
            self.next_check = self.clock() + 10
