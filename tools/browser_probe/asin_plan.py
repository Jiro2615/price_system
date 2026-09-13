"""Offline ASIN input and paired turn control; no DB access."""
import asyncio
import csv
import html
import re
import time

CONTROLS = ["B07QP2L8LC", "B019SKZXV8", "B0F2HTH5H9"]


def from_db(limit=100, hours=6, use_stats=False):
    # Select like price_check_from_db, but NEVER claim jobs, initialize schema,
    # or update checked_at. Read-only is enforced by the server transaction.
    import sys
    from probe_support import REPO
    sys.path.insert(0, str(REPO))
    from scripts.db_config import connect_db
    sql = """
        SELECT asin FROM amazon_products
        WHERE checked_at IS NULL OR checked_at < NOW() - (%s || ' hours')::interval
        ORDER BY checked_at NULLS FIRST, asin LIMIT %s
    """
    params = (hours, limit)
    if use_stats:
        sql = """
            SELECT s.asin FROM amazon_check_stats s
            JOIN amazon_products ap ON ap.asin = s.asin
            WHERE (s.next_check_at IS NULL OR s.next_check_at <= CURRENT_TIMESTAMP)
              AND (s.status IN ('pending', 'done')
                OR (s.status = 'processing' AND s.lock_expires_at < CURRENT_TIMESTAMP))
            ORDER BY s.last_checked_at ASC NULLS FIRST,
                     s.next_check_at ASC NULLS FIRST, s.priority_score DESC, s.asin
            LIMIT %s
        """
        params = (limit,)
    with connect_db(options="-c default_transaction_read_only=on -c statement_timeout=15000",
                    connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            values = [str(row[0]).strip().upper() for row in cur.fetchall()]
    if any(not re.fullmatch(r"[A-Z0-9]{10}", a) for a in values):
        raise ValueError("Invalid ASIN returned from DB")
    if not values:
        raise ValueError("No due ASINs in DB; no fixed-three fallback. Change --hours or selection.")
    return values


def load_asins(path):
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        rows = csv.DictReader(text.splitlines())
        column = next((c for c in rows.fieldnames or [] if c.strip().lower() == "asin"), None)
        if not column:
            raise ValueError("CSV requires an ASIN column")
        values = [r[column] for r in rows]
    else:
        values = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    result = []
    for value in values:
        asin = html.unescape(value or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{10}", asin):
            raise ValueError("Invalid ASIN: " + repr(value))
        if asin not in result:
            result.append(asin)
    if not result:
        raise ValueError("ASIN list is empty")
    if len(result) > 1000:
        raise ValueError("At most 1000 distinct ASINs")
    return result


def make_plan(asins):
    others = [a for a in dict.fromkeys(asins) if a not in CONTROLS]
    plan = list(CONTROLS)
    for index in range(0, len(others), 10):
        plan.extend(others[index:index+10])
        if index + 10 < len(others):
            plan.extend(CONTROLS)
    return plan


async def wait_turn(folder, mode, first, index, timeout=600):
    other = "shell" if mode == "chrome" else "chrome"
    needed = index - 1 if mode == first else index
    deadline = time.monotonic() + timeout
    while True:
        if (folder / "STOP").exists():
            return False
        if needed < 0 or (folder / f"{other}_{needed}.done").exists():
            return True
        if (folder / f"{other}.finished").exists():
            return False
        if time.monotonic() >= deadline:
            raise TimeoutError("Paired browser did not complete its turn")
        await asyncio.sleep(0.2)
