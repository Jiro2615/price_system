import argparse
import asyncio
import builtins

from collections import Counter
import os
from pathlib import Path
import re
import socket
import sys
import time
from datetime import datetime, timedelta
from typing import Any

from calc_store_targets import recalc_targets_for_asins
from db_config import connect_db
from db_retry import DB_RETRY_EXIT_CODE, TemporaryDbError, run_with_db_retry
from price_check_one_asin_db import check_amazon_one, close_amazon_page, create_amazon_page, save_to_db


def configure_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def safe_print(*args, **kwargs) -> None:
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        file = kwargs.get("file", sys.stdout)
        flush = kwargs.get("flush", False)
        text = sep.join(str(arg) for arg in args)
        encoding = getattr(file, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        builtins.print(safe_text, end=end, file=file, flush=flush)


ASIN_SPLIT_RE = re.compile(r"[\s,]+")


def load_asins_from_file(path_text: str, max_count: int = 5000) -> list[str]:
    path = Path(path_text).expanduser()
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    asins: list[str] = []
    seen: set[str] = set()

    for raw_value in ASIN_SPLIT_RE.split(text):
        asin = raw_value.strip().upper()
        if not asin or asin in seen:
            continue
        seen.add(asin)
        asins.append(asin)
        if len(asins) > max_count:
            raise ValueError(f"asin file has more than {max_count} ASINs")

    return asins


configure_output()
print = safe_print

configure_output()

print = safe_print

_connect_db_without_retry = connect_db


def connect_db(**kwargs):

    return run_with_db_retry(
        lambda: _connect_db_without_retry(**kwargs),
        description="connect_db",
        logger=print,
    )


def get_target_asins(limit: int, hours: int) -> list[str]:
    """
    未チェック、または指定時間以上チェックしていないASINをDBから取得する。
    """

    sql = """
        SELECT asin
        FROM amazon_products
        WHERE checked_at IS NULL
           OR checked_at < NOW() - (%s || ' hours')::interval
        ORDER BY checked_at NULLS FIRST, asin
        LIMIT %s;
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (hours, limit))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    finally:
        conn.close()


def ensure_amazon_check_stats_schema() -> None:
    sql = """
        ALTER TABLE amazon_check_stats
        ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending',
        ADD COLUMN IF NOT EXISTS worker_id TEXT,
        ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS lock_expires_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS consecutive_system_error_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_system_error_reason TEXT NOT NULL DEFAULT '';
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def ensure_amazon_check_stats_rows() -> None:
    sql = """
        INSERT INTO amazon_check_stats (
            asin,
            last_checked_at,
            next_check_at,
            check_interval_hours,
            priority_score,
            status,
            updated_at
        )
        SELECT
            ap.asin,
            ap.checked_at,
            ap.checked_at,
            24,
            100,
            'pending',
            CURRENT_TIMESTAMP
        FROM amazon_products ap
        ON CONFLICT (asin) DO NOTHING;
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def release_expired_processing_locks() -> int:
    sql = """
        UPDATE amazon_check_stats
        SET
            status = 'pending',
            worker_id = NULL,
            locked_at = NULL,
            lock_expires_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'processing'
          AND lock_expires_at < CURRENT_TIMESTAMP
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            released = cur.rowcount or 0
        conn.commit()
        return int(released)
    finally:
        conn.close()


def ensure_amazon_check_worker_runs_schema() -> None:
    create_sql = """
        CREATE TABLE IF NOT EXISTS amazon_check_worker_runs (
            id BIGSERIAL PRIMARY KEY,
            worker_id TEXT,
            claimed_count INTEGER NOT NULL DEFAULT 0,
            checked_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            changed_count INTEGER NOT NULL DEFAULT 0,
            stable_count INTEGER NOT NULL DEFAULT 0,
            system_error_count INTEGER NOT NULL DEFAULT 0,
            business_ng_count INTEGER NOT NULL DEFAULT 0,
            page_reset_count INTEGER NOT NULL DEFAULT 0,
            elapsed_seconds NUMERIC(12,3),
            avg_seconds_per_item NUMERIC(12,3),
            returncode INTEGER,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """
    alter_sql = """
        ALTER TABLE amazon_check_worker_runs
        ADD COLUMN IF NOT EXISTS worker_id TEXT,
        ADD COLUMN IF NOT EXISTS claimed_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS checked_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS success_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS changed_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS stable_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS system_error_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS business_ng_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS page_reset_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS elapsed_seconds NUMERIC(12,3),
        ADD COLUMN IF NOT EXISTS avg_seconds_per_item NUMERIC(12,3),
        ADD COLUMN IF NOT EXISTS returncode INTEGER,
        ADD COLUMN IF NOT EXISTS started_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS finished_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            cur.execute(alter_sql)
        conn.commit()
    finally:
        conn.close()


def claim_target_asins_by_stats(
    limit: int,
    worker_id: str,
    lock_minutes: int = 30,
    system_error_only: bool = False,
    reason_contains: str = "",
) -> list[dict[str, Any]]:
    """
    due な ASIN をまとめて claim/lock し、この実行で処理する固定リストを返す。
    """

    sql = """
        WITH target_rows AS (
            SELECT
                s.asin,
                s.status AS old_status,
                s.next_check_at AS old_next_check_at,
                ap.ng_reason AS current_ng_reason,
                ap.checked_at AS old_checked_at
            FROM amazon_check_stats s
            JOIN amazon_products ap ON ap.asin = s.asin
            WHERE
                (
                    %(system_error_only)s = TRUE
                    OR s.next_check_at IS NULL
                    OR s.next_check_at <= CURRENT_TIMESTAMP
                )
                AND
                (
                    s.status IN ('pending', 'done')
                    OR (s.status = 'processing' AND s.lock_expires_at < CURRENT_TIMESTAMP)
                )
                AND
                (
                    %(system_error_only)s = FALSE
                    OR COALESCE(ap.system_error, FALSE) = TRUE
                )
            ORDER BY
                s.last_checked_at ASC NULLS FIRST,
                s.next_check_at ASC NULLS FIRST,
                s.priority_score DESC,
                s.asin
            FOR UPDATE OF s SKIP LOCKED
            LIMIT %(limit)s
        )
        UPDATE amazon_check_stats s
        SET
            status = 'processing',
            worker_id = %(worker_id)s,
            locked_at = CURRENT_TIMESTAMP,
            lock_expires_at = CURRENT_TIMESTAMP + (%(lock_minutes)s || ' minutes')::interval,
            updated_at = CURRENT_TIMESTAMP
        FROM target_rows t
        WHERE s.asin = t.asin
        RETURNING
            s.asin,
            s.status,
            t.old_status,
            t.old_next_check_at,
            s.worker_id
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "limit": limit,
                    "worker_id": worker_id,
                    "lock_minutes": lock_minutes,
                    "system_error_only": system_error_only,
                },
            )
            rows = cur.fetchall()
        conn.commit()
        return [
            {
                "asin": row[0],
                "status": row[1],
                "old_status": row[2],
                "old_next_check_at": row[3],
                "worker_id": row[4],
            }
            for row in rows
        ]
    finally:
        conn.close()


def print_claimed_asins(claimed_rows: list[dict[str, Any]], max_rows: int = 20) -> None:
    if not claimed_rows:
        print("claim結果: 0件")
        return

    print("")
    print("===== 今回claimしたASIN =====")
    for row in claimed_rows[:max_rows]:
        print(
            f"asin={row.get('asin')} "
            f"status={row.get('status')} "
            f"old_next_check_at={row.get('old_next_check_at')} "
            f"ng_reason={row.get('current_ng_reason', '')} "
            f"checked_at={row.get('old_checked_at', '')} "
            f"worker_id={row.get('worker_id')}"
        )

    if len(claimed_rows) > max_rows:
        print(f"... 他 {len(claimed_rows) - max_rows} 件")
    print("")


def get_amazon_product_states(asins: list[str]) -> dict[str, dict[str, Any]]:

    if not asins:

        return {}

    sql = """

        SELECT asin, checked_at, system_error, ng_reason

        FROM amazon_products

        WHERE asin = ANY(%s)

    """

    conn = connect_db()

    try:

        with conn.cursor() as cur:

            cur.execute(sql, (asins,))

            rows = cur.fetchall()

        return {

            row[0]: {

                "asin": row[0],

                "checked_at": row[1],

                "system_error": row[2],

                "ng_reason": row[3] or "",

            }

            for row in rows

        }

    finally:

        conn.close()


def release_claimed_asins(asins: list[str]) -> int:

    if not asins:

        return 0

    sql = """

        UPDATE amazon_check_stats

        SET

            status = 'done',

            worker_id = NULL,

            locked_at = NULL,

            lock_expires_at = NULL,

            updated_at = CURRENT_TIMESTAMP

        WHERE asin = ANY(%s)

    """

    conn = connect_db()

    try:

        with conn.cursor() as cur:

            cur.execute(sql, (asins,))

            released = cur.rowcount

        conn.commit()

        return released

    finally:

        conn.close()


def filter_claimed_rows_by_reason(claimed_rows: list[dict[str, Any]], reason_contains: str) -> list[dict[str, Any]]:

    if not claimed_rows:

        return []

    states = get_amazon_product_states([row["asin"] for row in claimed_rows])

    for row in claimed_rows:

        state = states.get(row["asin"], {})

        row["current_ng_reason"] = state.get("ng_reason", "")

        row["old_checked_at"] = state.get("checked_at")

    if not reason_contains:

        return claimed_rows

    needle = reason_contains.casefold()

    matched_rows = [

        row for row in claimed_rows

        if needle in str(row.get("current_ng_reason", "")).casefold()

    ]

    excluded_asins = [

        row["asin"] for row in claimed_rows

        if needle not in str(row.get("current_ng_reason", "")).casefold()

    ]

    if excluded_asins:

        released_count = release_claimed_asins(excluded_asins)

        print(f"reason_filter_release count={released_count} reason_contains={reason_contains}")

    return matched_rows


def preview_system_error_targets(limit: int, reason_contains: str = "") -> list[dict[str, Any]]:

    sql = """

        SELECT asin, ng_reason, checked_at

        FROM amazon_products

        WHERE COALESCE(system_error, FALSE) = TRUE

          AND (

              %s = ''

              OR COALESCE(ng_reason, '') ILIKE %s

          )

        ORDER BY checked_at NULLS FIRST, asin

        LIMIT %s

    """

    conn = connect_db()

    try:

        with conn.cursor() as cur:

            cur.execute(sql, (reason_contains, f"%{reason_contains}%", limit))

            rows = cur.fetchall()

        return [

            {

                "asin": row[0],

                "current_ng_reason": row[1] or "",

                "old_checked_at": row[2],

            }

            for row in rows

        ]

    finally:

        conn.close()


def claim_target_asins_by_stats_v2(

    limit: int,

    worker_id: str,

    lock_minutes: int = 30,

    system_error_only: bool = False,

    reason_contains: str = "",

) -> list[dict[str, Any]]:

    sql = """

        WITH target_rows AS (

            SELECT

                s.asin,

                s.status AS old_status,

                s.next_check_at AS old_next_check_at,

                ap.ng_reason AS current_ng_reason,

                ap.checked_at AS old_checked_at

            FROM amazon_check_stats s

            JOIN amazon_products ap ON ap.asin = s.asin

            WHERE

                (

                    %(system_error_only)s = TRUE

                    AND COALESCE(ap.system_error, FALSE) = TRUE

                    AND (

                        %(reason_contains)s = ''

                        OR COALESCE(ap.ng_reason, '') ILIKE %(reason_pattern)s

                    )

                )

                OR

                (

                    %(system_error_only)s = FALSE

                    AND (

                        s.next_check_at IS NULL

                        OR s.next_check_at <= CURRENT_TIMESTAMP

                    )

                    AND (

                        s.status IN ('pending', 'done')

                        OR (s.status = 'processing' AND s.lock_expires_at < CURRENT_TIMESTAMP)

                    )

                )

            ORDER BY

                ap.checked_at ASC NULLS FIRST,

                s.last_checked_at ASC NULLS FIRST,

                s.next_check_at ASC NULLS FIRST,

                s.priority_score DESC,

                s.asin

            FOR UPDATE OF s SKIP LOCKED

            LIMIT %(limit)s

        )

        UPDATE amazon_check_stats s

        SET

            status = 'processing',

            worker_id = %(worker_id)s,

            locked_at = CURRENT_TIMESTAMP,

            lock_expires_at = CURRENT_TIMESTAMP + (%(lock_minutes)s || ' minutes')::interval,

            updated_at = CURRENT_TIMESTAMP

        FROM target_rows t

        WHERE s.asin = t.asin

        RETURNING

            s.asin,

            s.status,

            t.old_status,

            t.old_next_check_at,

            s.worker_id,

            t.current_ng_reason,

            t.old_checked_at

    """

    conn = connect_db()

    try:

        with conn.cursor() as cur:

            cur.execute(

                sql,

                {

                    "limit": limit,

                    "worker_id": worker_id,

                    "lock_minutes": lock_minutes,

                    "system_error_only": system_error_only,

                    "reason_contains": reason_contains,

                    "reason_pattern": f"%{reason_contains}%",

                },

            )

            rows = cur.fetchall()

        conn.commit()

        return [

            {

                "asin": row[0],

                "status": row[1],

                "old_status": row[2],

                "old_next_check_at": row[3],

                "worker_id": row[4],

                "current_ng_reason": row[5],

                "old_checked_at": row[6],

            }

            for row in rows

        ]

    finally:

        conn.close()


claim_target_asins_by_stats = claim_target_asins_by_stats_v2


_claim_target_asins_by_stats_unfiltered = claim_target_asins_by_stats


def _claim_active_listed_store_asins_without_retry(
    limit: int,
    worker_id: str,
    lock_minutes: int,
    system_error_only: bool,
    reason_contains: str,
    store_code: str,
) -> list[dict[str, Any]]:
    """Claim due ASINs that still have an active item in the selected store."""
    sql = """
        WITH target_rows AS (
            SELECT s.asin, s.status AS old_status, s.next_check_at AS old_next_check_at,
                   ap.ng_reason AS current_ng_reason, ap.checked_at AS old_checked_at
            FROM amazon_check_stats s
            JOIN amazon_products ap ON ap.asin = s.asin
            WHERE EXISTS (
                SELECT 1
                FROM store_products sp
                JOIN stores st ON st.id = sp.store_id
                WHERE sp.asin = s.asin
                  AND LOWER(st.store_code) = LOWER(%(store_code)s)
                  AND COALESCE(sp.enabled, FALSE) = TRUE
                  AND COALESCE(sp.force_stop, FALSE) = FALSE
                  AND COALESCE(sp.current_status, '') NOT IN ('', 'delete_pending', 'deleted')
            )
            AND (
                (%(system_error_only)s = TRUE
                 AND COALESCE(ap.system_error, FALSE) = TRUE
                 AND (%(reason_contains)s = '' OR COALESCE(ap.ng_reason, '') ILIKE %(reason_pattern)s))
                OR
                (%(system_error_only)s = FALSE
                 AND (s.next_check_at IS NULL OR s.next_check_at <= CURRENT_TIMESTAMP)
                 AND (s.status IN ('pending', 'done')
                      OR (s.status = 'processing' AND s.lock_expires_at < CURRENT_TIMESTAMP)))
            )
            ORDER BY ap.checked_at ASC NULLS FIRST, s.last_checked_at ASC NULLS FIRST,
                     s.next_check_at ASC NULLS FIRST, s.priority_score DESC, s.asin
            FOR UPDATE OF s SKIP LOCKED
            LIMIT %(limit)s
        )
        UPDATE amazon_check_stats s
        SET status = 'processing', worker_id = %(worker_id)s,
            locked_at = CURRENT_TIMESTAMP,
            lock_expires_at = CURRENT_TIMESTAMP + (%(lock_minutes)s || ' minutes')::interval,
            updated_at = CURRENT_TIMESTAMP
        FROM target_rows t
        WHERE s.asin = t.asin
        RETURNING s.asin, s.status, t.old_status, t.old_next_check_at, s.worker_id,
                  t.current_ng_reason, t.old_checked_at
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "limit": limit,
                "worker_id": worker_id,
                "lock_minutes": lock_minutes,
                "system_error_only": system_error_only,
                "reason_contains": reason_contains,
                "reason_pattern": f"%{reason_contains}%",
                "store_code": store_code,
            })
            rows = cur.fetchall()
        conn.commit()
        return [{
            "asin": row[0], "status": row[1], "old_status": row[2],
            "old_next_check_at": row[3], "worker_id": row[4],
            "current_ng_reason": row[5], "old_checked_at": row[6],
        } for row in rows]
    finally:
        conn.close()


def _claim_next_scheduled_active_listed_store_asins_without_retry(
    limit: int,
    worker_id: str,
    lock_minutes: int,
    store_code: str,
) -> list[dict[str, Any]]:
    """Claim the nearest future checks to fill a partly due worker batch.

    Due ASINs are claimed first.  When they do not fill the requested worker
    limit, this query supplies the nearest scheduled rows.  The row locks still
    prevent another PC or worker from taking the same ASIN.
    """
    sql = """
        WITH target_rows AS (
            SELECT s.asin, s.status AS old_status, s.next_check_at AS old_next_check_at,
                   ap.ng_reason AS current_ng_reason, ap.checked_at AS old_checked_at
            FROM amazon_check_stats s
            JOIN amazon_products ap ON ap.asin = s.asin
            WHERE EXISTS (
                SELECT 1
                FROM store_products sp
                JOIN stores st ON st.id = sp.store_id
                WHERE sp.asin = s.asin
                  AND LOWER(st.store_code) = LOWER(%(store_code)s)
                  AND COALESCE(sp.enabled, FALSE) = TRUE
                  AND COALESCE(sp.force_stop, FALSE) = FALSE
                  AND COALESCE(sp.current_status, '') NOT IN ('', 'delete_pending', 'deleted')
            )
            AND s.next_check_at > CURRENT_TIMESTAMP
            AND s.status IN ('pending', 'done')
            ORDER BY s.next_check_at ASC, s.priority_score DESC, ap.checked_at ASC NULLS FIRST, s.asin
            FOR UPDATE OF s SKIP LOCKED
            LIMIT %(limit)s
        )
        UPDATE amazon_check_stats s
        SET status = 'processing', worker_id = %(worker_id)s,
            locked_at = CURRENT_TIMESTAMP,
            lock_expires_at = CURRENT_TIMESTAMP + (%(lock_minutes)s || ' minutes')::interval,
            updated_at = CURRENT_TIMESTAMP
        FROM target_rows t
        WHERE s.asin = t.asin
        RETURNING s.asin, s.status, t.old_status, t.old_next_check_at, s.worker_id,
                  t.current_ng_reason, t.old_checked_at
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "limit": limit,
                "worker_id": worker_id,
                "lock_minutes": lock_minutes,
                "store_code": store_code,
            })
            rows = cur.fetchall()
        conn.commit()
        return [{
            "asin": row[0], "status": row[1], "old_status": row[2],
            "old_next_check_at": row[3], "worker_id": row[4],
            "current_ng_reason": row[5], "old_checked_at": row[6],
        } for row in rows]
    finally:
        conn.close()


def claim_target_asins_by_stats(
    limit: int,
    worker_id: str,
    lock_minutes: int = 30,
    system_error_only: bool = False,
    reason_contains: str = "",
    store_code: str = "",
    listed_only: bool = False,
) -> list[dict[str, Any]]:
    if not listed_only:
        return _claim_target_asins_by_stats_unfiltered(
            limit, worker_id, lock_minutes=lock_minutes,
            system_error_only=system_error_only, reason_contains=reason_contains,
        )
    due_rows = run_with_db_retry(
        lambda: _claim_active_listed_store_asins_without_retry(
            limit, worker_id, lock_minutes, system_error_only, reason_contains, store_code,
        ),
        description=f"claim listed store ASINs limit={limit} worker_id={worker_id} store={store_code}",
        logger=print,
    )
    if system_error_only:
        return due_rows

    remaining = max(0, limit - len(due_rows))
    if remaining == 0:
        return due_rows

    scheduled_rows = run_with_db_retry(
        lambda: _claim_next_scheduled_active_listed_store_asins_without_retry(
            remaining, worker_id, lock_minutes, store_code,
        ),
        description=f"claim next scheduled listed ASINs limit={remaining} worker_id={worker_id} store={store_code}",
        logger=print,
    )
    if scheduled_rows:
        print(
            "期限到来済みASINに次回予定が近いASINを補充して取得: "
            f"due={len(due_rows)} scheduled={len(scheduled_rows)} "
            f"total={len(due_rows) + len(scheduled_rows)} worker_id={worker_id}"
        )
    return due_rows + scheduled_rows


def claim_explicit_asins_by_stats(
    asins: list[str],
    worker_id: str,
    lock_minutes: int = 30,
) -> list[dict[str, Any]]:
    """Claim explicitly requested ASINs without duplicating another worker.

    Direct ASIN batches used to skip ``amazon_check_stats`` completely.  That
    was safe only while one PC ran checks.  Use the same row-level lock as the
    scheduled queue so multiple execution PCs can safely process separate
    ASINs from one shared input list.
    """
    requested = list(dict.fromkeys(str(asin or "").strip() for asin in asins if str(asin or "").strip()))
    if not requested:
        return []
    sql = """
        WITH requested AS (
            SELECT asin, MIN(position) AS position
            FROM unnest(%(asins)s::text[]) WITH ORDINALITY AS source(asin, position)
            GROUP BY asin
        ),
        target_rows AS (
            SELECT s.asin, s.status AS old_status, s.next_check_at AS old_next_check_at,
                   COALESCE(ap.ng_reason, '') AS current_ng_reason, ap.checked_at AS old_checked_at
            FROM requested r
            JOIN amazon_check_stats s ON s.asin = r.asin
            LEFT JOIN amazon_products ap ON ap.asin = s.asin
            WHERE s.status IN ('pending', 'done')
               OR (s.status = 'processing' AND s.lock_expires_at < CURRENT_TIMESTAMP)
            ORDER BY r.position
            FOR UPDATE OF s SKIP LOCKED
        )
        UPDATE amazon_check_stats s
        SET status = 'processing', worker_id = %(worker_id)s,
            locked_at = CURRENT_TIMESTAMP,
            lock_expires_at = CURRENT_TIMESTAMP + (%(lock_minutes)s || ' minutes')::interval,
            updated_at = CURRENT_TIMESTAMP
        FROM target_rows t
        WHERE s.asin = t.asin
        RETURNING s.asin, s.status, t.old_status, t.old_next_check_at, s.worker_id,
                  t.current_ng_reason, t.old_checked_at
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, {"asins": requested, "worker_id": worker_id, "lock_minutes": lock_minutes})
            rows = cur.fetchall()
        conn.commit()
        return [{
            "asin": row[0], "status": row[1], "old_status": row[2],
            "old_next_check_at": row[3], "worker_id": row[4],
            "current_ng_reason": row[5], "old_checked_at": row[6],
        } for row in rows]
    finally:
        conn.close()


def get_previous_amazon_state(asin: str) -> dict[str, Any] | None:
    sql = """
        SELECT
            asin,
            amazon_price,
            amazon_point,
            available_qty,
            business_ng,
            system_error,
            ng_reason
        FROM amazon_products
        WHERE asin = %s
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (asin,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "asin": row[0],
                "amazon_price": row[1],
                "amazon_point": row[2],
                "available_qty": row[3],
                "business_ng": row[4],
                "system_error": row[5],
                "ng_reason": row[6],
            }
    finally:
        conn.close()


def get_existing_stats(asin: str) -> dict[str, Any] | None:
    sql = """
        SELECT
            check_count,
            price_change_count,
            stock_change_count,
            ng_change_count,
            error_count,
            stable_count,
            status,
            worker_id,
            locked_at,
            lock_expires_at,
            consecutive_system_error_count,
            last_system_error_reason
        FROM amazon_check_stats
        WHERE asin = %s
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (asin,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "check_count": int(row[0] or 0),
                "price_change_count": int(row[1] or 0),
                "stock_change_count": int(row[2] or 0),
                "ng_change_count": int(row[3] or 0),
                "error_count": int(row[4] or 0),
                "stable_count": int(row[5] or 0),
                "status": row[6],
                "worker_id": row[7],
                "locked_at": row[8],
                "lock_expires_at": row[9],
                "consecutive_system_error_count": int(row[10] or 0),
                "last_system_error_reason": row[11] or "",
            }
    finally:
        conn.close()


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def system_error_reason(data: dict[str, Any]) -> str:
    """Keep the raw reason stable even when the UI adds a stock-stop note."""
    return normalize_text(data.get("system_error_reason") or data.get("ng_reason"))


def consecutive_system_error_count(current: dict[str, Any], existing: dict[str, Any] | None) -> int:
    if not current.get("system_error"):
        return 0
    reason = system_error_reason(current)
    if not reason:
        return 0
    stats = existing or {}
    if normalize_text(stats.get("last_system_error_reason")) == reason:
        return int(stats.get("consecutive_system_error_count") or 0) + 1
    return 1


def apply_repeated_system_error_stock_stop(
    current: dict[str, Any],
    existing: dict[str, Any] | None,
    *,
    threshold: int = 3,
) -> int:
    """Turn a repeated, same-reason fetch error into a stock-stop signal.

    The original ``system_error`` remains true for diagnostics and retry
    priority.  ``business_ng`` makes target calculation set RMS stock to zero.
    """
    streak = consecutive_system_error_count(current, existing)
    if streak < threshold:
        return streak
    raw_reason = system_error_reason(current)
    if not raw_reason:
        return streak
    current["system_error_reason"] = raw_reason
    current["business_ng"] = True
    current["available_qty"] = 0
    current["ng_reason"] = f"system_error repeated {streak} times: {raw_reason}"
    current["shipping_status"] = "NG"
    return streak


def determine_stats_update(previous: dict[str, Any] | None, current: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    stats = existing or {
        "check_count": 0,
        "price_change_count": 0,
        "stock_change_count": 0,
        "ng_change_count": 0,
        "error_count": 0,
        "stable_count": 0,
        "consecutive_system_error_count": 0,
        "last_system_error_reason": "",
    }

    previous = previous or {}
    now = current.get("checked_at") or datetime.now()

    price_changed = (
        previous.get("amazon_price") != current.get("amazon_price")
        or previous.get("amazon_point") != current.get("amazon_point")
    )
    stock_changed = previous.get("available_qty") != current.get("available_qty")
    ng_changed = (
        previous.get("business_ng") != current.get("business_ng")
        or previous.get("system_error") != current.get("system_error")
        or normalize_text(previous.get("ng_reason")) != normalize_text(current.get("ng_reason"))
    )

    result = {
        "check_count": stats["check_count"] + 1,
        "price_change_count": stats["price_change_count"],
        "stock_change_count": stats["stock_change_count"],
        "ng_change_count": stats["ng_change_count"],
        "error_count": stats["error_count"],
        "stable_count": stats["stable_count"],
        "last_checked_at": now,
        "next_check_at": now,
        "check_interval_hours": 24,
        "priority_score": 100,
        "status": "done",
        "worker_id": None,
        "locked_at": None,
        "lock_expires_at": None,
        "change_detected": False,
        "system_error_detected": False,
        "stable_detected": False,
        "consecutive_system_error_count": consecutive_system_error_count(current, stats),
        "last_system_error_reason": system_error_reason(current) if current.get("system_error") else "",
    }

    if current.get("system_error"):
        result["error_count"] += 1
        result["stable_count"] = 0
        result["check_interval_hours"] = 1
        result["priority_score"] = 200
        result["system_error_detected"] = True
    elif price_changed or stock_changed or ng_changed:
        if price_changed:
            result["price_change_count"] += 1
        if stock_changed:
            result["stock_change_count"] += 1
        if ng_changed:
            result["ng_change_count"] += 1
        result["stable_count"] = 0
        result["check_interval_hours"] = 6
        result["priority_score"] = 150
        result["change_detected"] = True
    else:
        result["stable_count"] = stats["stable_count"] + 1
        if result["stable_count"] >= 3:
            interval_hours = 24
        else:
            interval_hours = 12
        result["check_interval_hours"] = interval_hours
        result["priority_score"] = max(10, 100 - result["stable_count"] * 5)
        result["stable_detected"] = True

    result["next_check_at"] = now + timedelta(hours=result["check_interval_hours"])
    return result


def update_amazon_check_stats(asin: str, update: dict[str, Any]) -> None:
    sql = """
        INSERT INTO amazon_check_stats (
            asin,
            check_count,
            price_change_count,
            stock_change_count,
            ng_change_count,
            error_count,
            stable_count,
            last_checked_at,
            next_check_at,
            check_interval_hours,
            priority_score,
            status,
            worker_id,
            locked_at,
            lock_expires_at,
            consecutive_system_error_count,
            last_system_error_reason,
            updated_at
        )
        VALUES (
            %(asin)s,
            %(check_count)s,
            %(price_change_count)s,
            %(stock_change_count)s,
            %(ng_change_count)s,
            %(error_count)s,
            %(stable_count)s,
            %(last_checked_at)s,
            %(next_check_at)s,
            %(check_interval_hours)s,
            %(priority_score)s,
            %(status)s,
            %(worker_id)s,
            %(locked_at)s,
            %(lock_expires_at)s,
            %(consecutive_system_error_count)s,
            %(last_system_error_reason)s,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (asin) DO UPDATE SET
            check_count = EXCLUDED.check_count,
            price_change_count = EXCLUDED.price_change_count,
            stock_change_count = EXCLUDED.stock_change_count,
            ng_change_count = EXCLUDED.ng_change_count,
            error_count = EXCLUDED.error_count,
            stable_count = EXCLUDED.stable_count,
            last_checked_at = EXCLUDED.last_checked_at,
            next_check_at = EXCLUDED.next_check_at,
            check_interval_hours = EXCLUDED.check_interval_hours,
            priority_score = EXCLUDED.priority_score,
            status = EXCLUDED.status,
            worker_id = EXCLUDED.worker_id,
            locked_at = EXCLUDED.locked_at,
            lock_expires_at = EXCLUDED.lock_expires_at,
            consecutive_system_error_count = EXCLUDED.consecutive_system_error_count,
            last_system_error_reason = EXCLUDED.last_system_error_reason,
            updated_at = CURRENT_TIMESTAMP
    """

    payload = {"asin": asin, **update}
    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, payload)
        conn.commit()
    finally:
        conn.close()


def build_error_stats_update(existing: dict[str, Any] | None) -> dict[str, Any]:
    stats = existing or {
        "check_count": 0,
        "price_change_count": 0,
        "stock_change_count": 0,
        "ng_change_count": 0,
        "error_count": 0,
        "stable_count": 0,
        "consecutive_system_error_count": 0,
        "last_system_error_reason": "",
    }
    now = datetime.now()
    return {
        "check_count": stats["check_count"] + 1,
        "price_change_count": stats["price_change_count"],
        "stock_change_count": stats["stock_change_count"],
        "ng_change_count": stats["ng_change_count"],
        "error_count": stats["error_count"] + 1,
        "stable_count": 0,
        "last_checked_at": now,
        "next_check_at": now + timedelta(hours=1),
        "check_interval_hours": 1,
        "priority_score": 200,
        "status": "done",
        "worker_id": None,
        "locked_at": None,
        "lock_expires_at": None,
        "change_detected": False,
        "system_error_detected": True,
        "stable_detected": False,
        "consecutive_system_error_count": int(stats.get("consecutive_system_error_count") or 0),
        "last_system_error_reason": normalize_text(stats.get("last_system_error_reason")),
    }


def build_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def needs_retry_after_page_closed(data: dict[str, Any]) -> bool:
    reason = str(data.get("ng_reason") or "")
    return (
        bool(data.get("system_error"))
        and bool(data.get("page_needs_reset"))
        and "Target page, context or browser has been closed" in reason
    )


def asin_result_label(data: dict[str, Any]) -> str:
    if data.get("system_error"):
        return "system_error"
    if data.get("business_ng"):
        return "business_ng"
    return "success"


def build_worker_run_summary(metrics: dict[str, Any]) -> str:
    keys = [
        "worker_id",
        "claimed_count",
        "checked_count",
        "success_count",
        "system_error_count",
        "business_ng_count",
        "changed_count",
        "stable_count",
        "page_reset_count",
        "elapsed_seconds",
        "avg_seconds_per_item",
        "started_at",
        "finished_at",
        "returncode",
    ]
    return "WORKER_RUN_SUMMARY " + " ".join(f"{key}={metrics.get(key)}" for key in keys)


def save_worker_run_summary(metrics: dict[str, Any]) -> None:
    sql = """
        INSERT INTO amazon_check_worker_runs (
            worker_id,
            claimed_count,
            checked_count,
            success_count,
            changed_count,
            stable_count,
            system_error_count,
            business_ng_count,
            page_reset_count,
            elapsed_seconds,
            avg_seconds_per_item,
            returncode,
            started_at,
            finished_at
        )
        VALUES (
            %(worker_id)s,
            %(claimed_count)s,
            %(checked_count)s,
            %(success_count)s,
            %(changed_count)s,
            %(stable_count)s,
            %(system_error_count)s,
            %(business_ng_count)s,
            %(page_reset_count)s,
            %(elapsed_seconds)s,
            %(avg_seconds_per_item)s,
            %(returncode)s,
            %(started_at)s,
            %(finished_at)s
        )
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, metrics)
        conn.commit()
    finally:
        conn.close()


def fetch_store_codes_for_asin(asin: str, mall: str = "rakuten") -> list[str]:
    sql = """
        SELECT DISTINCT s.store_code
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        WHERE sp.asin = %s
          AND s.mall = %s
          AND s.store_code LIKE 'rakuten_%%'
        ORDER BY s.store_code
    """

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (asin, mall))
            return [str(row[0]).strip() for row in cur.fetchall() if str(row[0]).strip()]
    finally:
        conn.close()


def run_target_recalc_for_asin(asin: str, store_code: str) -> dict[str, Any]:
    conn = connect_db()
    try:
        result = recalc_targets_for_asins(
            conn,
            store_code=store_code,
            asins=[asin],
            dry_run=False,
            verbose=False,
        )
        verify_target_recalc_persisted(conn, asin=asin, store_code=store_code, result=result)
        return result
    finally:
        conn.close()


def verify_target_recalc_persisted(
    conn,
    *,
    asin: str,
    store_code: str,
    result: dict[str, Any],
) -> None:
    """Confirm the just-calculated target values are actually stored.

    The Amazon worker writes its source result first and then calculates targets
    for every mapped Rakuten store.  A successful calculation without a stored
    target would otherwise leave the price/inventory API with no candidate while
    the worker log still looks successful.
    """
    targets = result.get("targets") or []
    expected_targets = [
        target
        for target in targets
        if str(target.get("asin") or "").upper() == asin.upper()
        and str(target.get("store_code") or "").casefold() == store_code.casefold()
    ]
    if not expected_targets:
        if int(result.get("rows") or 0) == 0:
            # A stale or disabled store mapping has no active target row to save.
            return
        raise RuntimeError(
            "target recalc returned no calculated row: "
            f"asin={asin} store={store_code} rows={result.get('rows')}"
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sp.target_price, sp.target_stock
            FROM store_products sp
            JOIN stores s ON s.id = sp.store_id
            WHERE sp.asin = %s
              AND s.store_code = %s
              AND sp.enabled = TRUE
            """,
            (asin, store_code),
        )
        rows = cur.fetchall()

    if len(rows) != len(expected_targets):
        raise RuntimeError(
            "target recalc persistence row mismatch: "
            f"asin={asin} store={store_code} "
            f"expected_rows={len(expected_targets)} actual_rows={len(rows)}"
        )

    actual_values = Counter((price, stock) for price, stock in rows)
    expected_values = Counter(
        (target.get("target_price"), target.get("target_stock"))
        for target in expected_targets
    )
    if actual_values != expected_values:
        raise RuntimeError(
            "target recalc was not persisted: "
            f"asin={asin} store={store_code} "
            f"expected={dict(expected_values)} actual={dict(actual_values)}"
        )


def print_db_summary() -> None:
    """
    簡単な件数確認。
    """

    sql = """
        SELECT
            COUNT(*) AS total_count,
            COUNT(*) FILTER (WHERE checked_at IS NOT NULL) AS checked_count,
            COUNT(*) FILTER (WHERE checked_at IS NULL) AS unchecked_count,
            COUNT(*) FILTER (WHERE business_ng = TRUE) AS business_ng_count,
            COUNT(*) FILTER (WHERE system_error = TRUE) AS system_error_count
        FROM amazon_products;
    """

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

        print("")
        print("===== DB状況 =====")
        print(f"総件数          : {row[0]}")
        print(f"チェック済み    : {row[1]}")
        print(f"未チェック      : {row[2]}")
        print(f"業務NG          : {row[3]}")
        print(f"システムエラー  : {row[4]}")
        print("==================")
        print("")

    finally:
        conn.close()


_get_target_asins_without_retry = get_target_asins
_ensure_amazon_check_stats_schema_without_retry = ensure_amazon_check_stats_schema
_ensure_amazon_check_stats_rows_without_retry = ensure_amazon_check_stats_rows
_release_expired_processing_locks_without_retry = release_expired_processing_locks
_ensure_amazon_check_worker_runs_schema_without_retry = ensure_amazon_check_worker_runs_schema
_get_amazon_product_states_without_retry = get_amazon_product_states
_release_claimed_asins_without_retry = release_claimed_asins
_preview_system_error_targets_without_retry = preview_system_error_targets
_claim_target_asins_by_stats_without_retry = claim_target_asins_by_stats
_get_previous_amazon_state_without_retry = get_previous_amazon_state
_get_existing_stats_without_retry = get_existing_stats
_update_amazon_check_stats_without_retry = update_amazon_check_stats
_save_worker_run_summary_without_retry = save_worker_run_summary
_fetch_store_codes_for_asin_without_retry = fetch_store_codes_for_asin
_run_target_recalc_for_asin_without_retry = run_target_recalc_for_asin
_print_db_summary_without_retry = print_db_summary


def get_target_asins(limit: int, hours: int) -> list[str]:

    return run_with_db_retry(
        lambda: _get_target_asins_without_retry(limit, hours),
        description=f"get_target_asins limit={limit} hours={hours}",
        logger=print,
    )


def ensure_amazon_check_stats_schema() -> None:

    run_with_db_retry(
        _ensure_amazon_check_stats_schema_without_retry,
        description="ensure_amazon_check_stats_schema",
        logger=print,
    )


def ensure_amazon_check_stats_rows() -> None:

    run_with_db_retry(
        _ensure_amazon_check_stats_rows_without_retry,
        description="ensure_amazon_check_stats_rows",
        logger=print,
    )


def release_expired_processing_locks() -> int:

    return run_with_db_retry(
        _release_expired_processing_locks_without_retry,
        description="release_expired_processing_locks",
        logger=print,
    )


def ensure_amazon_check_worker_runs_schema() -> None:

    run_with_db_retry(
        _ensure_amazon_check_worker_runs_schema_without_retry,
        description="ensure_amazon_check_worker_runs_schema",
        logger=print,
    )


def get_amazon_product_states(asins: list[str]) -> dict[str, dict[str, Any]]:

    return run_with_db_retry(
        lambda: _get_amazon_product_states_without_retry(asins),
        description=f"get_amazon_product_states count={len(asins)}",
        logger=print,
    )


def release_claimed_asins(asins: list[str]) -> int:

    return run_with_db_retry(
        lambda: _release_claimed_asins_without_retry(asins),
        description=f"release_claimed_asins count={len(asins)}",
        logger=print,
    )


def preview_system_error_targets(limit: int, reason_contains: str = "") -> list[dict[str, Any]]:

    return run_with_db_retry(
        lambda: _preview_system_error_targets_without_retry(limit, reason_contains),
        description=f"preview_system_error_targets limit={limit}",
        logger=print,
    )


def claim_target_asins_by_stats_v2(
    limit: int,
    worker_id: str,
    lock_minutes: int = 30,
    system_error_only: bool = False,
    reason_contains: str = "",
    store_code: str = "",
    listed_only: bool = False,
) -> list[dict[str, Any]]:

    return run_with_db_retry(
        lambda: _claim_target_asins_by_stats_without_retry(
            limit,
            worker_id,
            lock_minutes=lock_minutes,
            system_error_only=system_error_only,
            reason_contains=reason_contains,
            store_code=store_code,
            listed_only=listed_only,
        ),
        description=f"claim_target_asins_by_stats limit={limit} worker_id={worker_id}",
        logger=print,
    )


claim_target_asins_by_stats = claim_target_asins_by_stats_v2


def get_previous_amazon_state(asin: str) -> dict[str, Any] | None:

    return run_with_db_retry(
        lambda: _get_previous_amazon_state_without_retry(asin),
        description=f"get_previous_amazon_state asin={asin}",
        logger=print,
    )


def get_existing_stats(asin: str) -> dict[str, Any] | None:

    return run_with_db_retry(
        lambda: _get_existing_stats_without_retry(asin),
        description=f"get_existing_stats asin={asin}",
        logger=print,
    )


def update_amazon_check_stats(asin: str, update: dict[str, Any]) -> None:

    run_with_db_retry(
        lambda: _update_amazon_check_stats_without_retry(asin, update),
        description=f"update_amazon_check_stats asin={asin}",
        logger=print,
    )


def save_worker_run_summary(metrics: dict[str, Any]) -> None:

    run_with_db_retry(
        lambda: _save_worker_run_summary_without_retry(metrics),
        description=f"save_worker_run_summary worker_id={metrics.get('worker_id')}",
        logger=print,
    )


def fetch_store_codes_for_asin(asin: str, mall: str = "rakuten") -> list[str]:

    return run_with_db_retry(
        lambda: _fetch_store_codes_for_asin_without_retry(asin, mall),
        description=f"fetch_store_codes_for_asin asin={asin} mall={mall}",
        logger=print,
    )


def run_target_recalc_for_asin(asin: str, store_code: str) -> dict[str, Any]:

    return run_with_db_retry(
        lambda: _run_target_recalc_for_asin_without_retry(asin, store_code),
        description=f"run_target_recalc_for_asin asin={asin} store={store_code}",
        logger=print,
    )


def print_db_summary() -> None:

    run_with_db_retry(
        _print_db_summary_without_retry,
        description="print_db_summary",
        logger=print,
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="DBからASINを取得してAmazon価格チェックを実行します。")
    parser.add_argument("--limit", type=int, default=10, help="今回チェックする最大件数")
    parser.add_argument("--hours", type=int, default=6, help="何時間以上前のチェック結果を再チェック対象にするか")
    parser.add_argument("--summary", action="store_true", help="実行前後にDB件数サマリを表示する")
    parser.add_argument(
        "--use-stats",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="amazon_check_stats.next_check_at ??????ASIN???",
    )
    parser.add_argument("--system-error-only", action="store_true", help="amazon_products.system_error = TRUE のASINだけを再チェックする")
    parser.add_argument("--reason-contains", default="", help="system_error再チェック時に ng_reason の部分一致で絞る")
    parser.add_argument("--dry-run", action="store_true", help="対象ASIN一覧だけ表示し、ブラウザ起動やDB更新を行わない")
    parser.add_argument("--worker-id", default="", help="stats方式で使うワーカーID。未指定なら自動生成")
    parser.add_argument("--asin-file", default="", help="explicit ASIN target file. accepts newline, comma, or whitespace separated values")
    parser.add_argument("--store-code", default="", help="Rakuten store_code used with --listed-only")
    parser.add_argument("--listed-only", action="store_true", help="only active listed products mapped to --store-code")
    parser.add_argument("--page-timeout", type=int, default=60000, help="page.goto の timeout(ms)")
    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit は 1以上にしてください。")
        return 2
    if args.system_error_only and not args.use_stats:
        print("--system-error-only は --use-stats と一緒に指定してください。")
        return 2

    print("DBから対象ASINを取得します。")
    if args.reason_contains and not args.system_error_only:

        print("--reason-contains は --system-error-only と一緒に指定してください。")

        return 2

    if args.asin_file and (args.system_error_only or args.reason_contains):
        print("--asin-file cannot be combined with system-error target options")
        return 2
    if args.listed_only and not args.store_code.strip():
        print("--listed-only requires --store-code")
        return 2
    if args.listed_only and not args.use_stats:
        print("--listed-only requires --use-stats")
        return 2

    print(f"limit={args.limit}, hours={args.hours}")
    print(f"use_stats={args.use_stats}")
    print(f"system_error_only={args.system_error_only}")
    print(f"reason_contains={args.reason_contains}")
    print(f"dry_run={args.dry_run}")
    print(f"asin_file={args.asin_file}")
    print(f"store_code={args.store_code}")
    print(f"listed_only={args.listed_only}")
    print(f"page_timeout={args.page_timeout}")
    worker_id = args.worker_id.strip() or build_worker_id()
    started_at_dt = datetime.now()
    started_at_text = started_at_dt.strftime("%Y/%m/%d %H:%M:%S")
    started_at_iso = started_at_dt.isoformat(timespec="seconds")
    started_perf = time.perf_counter()
    metrics: dict[str, Any] = {
        "worker_id": worker_id,
        "claimed_count": 0,
        "checked_count": 0,
        "success_count": 0,
        "system_error_count": 0,
        "business_ng_count": 0,
        "changed_count": 0,
        "stable_count": 0,
        "page_reset_count": 0,
        "elapsed_seconds": 0.0,
        "avg_seconds_per_item": 0.0,
        "returncode": 0,
        "started_at": started_at_dt,
        "finished_at": started_at_dt,
        "started_at_text": started_at_text,
        "finished_at_text": started_at_text,
        "started_at_iso": started_at_iso,
        "finished_at_iso": started_at_iso,
    }
    def try_save_run_summary() -> None:

        if not args.use_stats or args.dry_run:
            return

        try:
            save_worker_run_summary(metrics)
        except TemporaryDbError as e:
            print(f"worker run summary save failed: {e}")
        except Exception as e:
            print(f"worker run summary save failed: {e}")

    if args.dry_run and args.system_error_only:

        claimed_rows = preview_system_error_targets(args.limit, args.reason_contains)

        asins = [row["asin"] for row in claimed_rows]

    elif args.use_stats:
        print(f"worker_id={worker_id}")

    if args.summary:
        print_db_summary()

    claimed_rows: list[dict[str, Any]] = []

    if args.asin_file:
        requested_asins = load_asins_from_file(args.asin_file)
        if args.use_stats and not args.dry_run:
            ensure_amazon_check_stats_schema()
            ensure_amazon_check_stats_rows()
            ensure_amazon_check_worker_runs_schema()
            released_count = release_expired_processing_locks()
            if released_count > 0:
                print(f"期限切れprocessingを自動解除しました: {released_count}件")
            claimed_rows = claim_explicit_asins_by_stats(requested_asins, worker_id)
            asins = [row["asin"] for row in claimed_rows]
            skipped_count = len(requested_asins) - len(asins)
            if skipped_count > 0:
                print(f"他ワーカーが処理中・未登録のため今回見送ったASIN: {skipped_count}件")
        else:
            asins = requested_asins
            claimed_rows = [{"asin": asin, "current_ng_reason": "", "old_checked_at": ""} for asin in asins]
    elif args.dry_run and args.system_error_only:

        claimed_rows = preview_system_error_targets(args.limit, args.reason_contains)

        asins = [row["asin"] for row in claimed_rows]

    elif args.use_stats:
        ensure_amazon_check_stats_schema()
        ensure_amazon_check_stats_rows()
        ensure_amazon_check_worker_runs_schema()
        released_count = release_expired_processing_locks()
        if released_count > 0:
            print(f"期限切れprocessingを自動解除しました: {released_count}件")
        claimed_rows = claim_target_asins_by_stats(
            args.limit,
            worker_id,
            system_error_only=args.system_error_only,
            reason_contains=args.reason_contains,
            store_code=args.store_code.strip(),
            listed_only=args.listed_only,
        )
        asins = [row["asin"] for row in claimed_rows]
    else:
        asins = get_target_asins(args.limit, args.hours)

    metrics["claimed_count"] = len(claimed_rows) if args.use_stats else len(asins)

    if not asins:
        print("対象ASINがありません。")
        finished_at_dt = datetime.now()
        metrics["finished_at"] = finished_at_dt
        metrics["finished_at_text"] = finished_at_dt.strftime("%Y/%m/%d %H:%M:%S")
        metrics["finished_at_iso"] = finished_at_dt.isoformat(timespec="seconds")
        metrics["elapsed_seconds"] = round(time.perf_counter() - started_perf, 3)
        if args.summary and args.use_stats:
            print("")
            print("===== Worker Run Summary =====")
            print(f"worker_id            : {metrics['worker_id']}")
            print(f"claimed_count        : {metrics['claimed_count']}")
            print(f"checked_count        : {metrics['checked_count']}")
            print(f"success_count        : {metrics['success_count']}")
            print(f"system_error_count   : {metrics['system_error_count']}")
            print(f"business_ng_count    : {metrics['business_ng_count']}")
            print(f"changed_count        : {metrics['changed_count']}")
            print(f"stable_count         : {metrics['stable_count']}")
            print(f"page_reset_count     : {metrics['page_reset_count']}")
            print(f"elapsed_seconds      : {metrics['elapsed_seconds']:.3f}")
            print(f"avg_seconds_per_item : {metrics['avg_seconds_per_item']:.3f}")
            print(f"started_at           : {metrics['started_at_text']}")
            print(f"finished_at          : {metrics['finished_at_text']}")
            print(f"returncode           : {metrics['returncode']}")
            print(build_worker_run_summary(metrics | {"started_at": metrics["started_at_iso"], "finished_at": metrics["finished_at_iso"]}))
            try_save_run_summary()
        return 0

    if args.summary and args.use_stats:
        print_claimed_asins(claimed_rows)

    print("")
    print("対象ASIN:")
    for asin in asins:
        print(f"  {asin}")

    if args.dry_run:

        reason_counter = Counter(str(row.get("current_ng_reason") or "") for row in claimed_rows)

        print("")

        print("===== Dry Run Targets =====")

        for row in claimed_rows:

            print(

                f"asin={row.get('asin')} "

                f"ng_reason={row.get('current_ng_reason', '')} "

                f"checked_at={row.get('old_checked_at', '')}"

            )

        print("")

        print(f"target_count={len(claimed_rows)}")

        for reason, count in sorted(reason_counter.items(), key=lambda item: (-item[1], item[0])):

            print(f"reason_count[{reason}]={count}")

        finished_at_dt = datetime.now()

        metrics["finished_at"] = finished_at_dt

        metrics["finished_at_text"] = finished_at_dt.strftime("%Y/%m/%d %H:%M:%S")

        metrics["finished_at_iso"] = finished_at_dt.isoformat(timespec="seconds")

        metrics["elapsed_seconds"] = round(time.perf_counter() - started_perf, 3)

        print(f"finished_at    : {metrics['finished_at_text']}")

        return 0

    print("")
    print("Amazonチェック開始")
    print("")

    success_count = 0
    error_count = 0
    changed_count = 0
    stable_count = 0
    system_error_count = 0
    business_ng_count = 0
    normalized_count = 0
    business_ng_changed_count = 0
    system_error_continued_count = 0
    page_reset_count = 0
    stats_updated_count = 0
    final_reason_counter: Counter[str] = Counter()
    result_asins: list[str] = []

    playwright = None
    browser = None
    context = None
    shared_page = None

    try:
        print("共有Chrome/pageを起動します。")
        playwright, browser, context, shared_page = await create_amazon_page()
        print("共有Chrome/page起動完了")

        for idx, asin in enumerate(asins, start=1):
            metrics["checked_count"] += 1
            asin_started_perf = time.perf_counter()
            print(f"===== {idx}/{len(asins)} {asin} =====")
            existing_stats: dict[str, Any] | None = None
            data: dict[str, Any] | None = None

            try:
                previous = get_previous_amazon_state(asin) if args.use_stats else None
                existing_stats = get_existing_stats(asin) if args.use_stats else None
                data = await check_amazon_one(asin, page=shared_page, page_timeout_ms=args.page_timeout)

                if needs_retry_after_page_closed(data):
                    print("page/context/browser closed を検知したため、共有page再作成後に同じASINを1回だけ再試行します。")
                    page_reset_count += 1
                    await close_amazon_page(playwright, browser, context, shared_page)
                    playwright, browser, context, shared_page = await create_amazon_page()
                    print("共有Chrome/page再初期化完了")
                    data = await check_amazon_one(asin, page=shared_page, page_timeout_ms=args.page_timeout)

                repeated_error_streak = apply_repeated_system_error_stock_stop(data, existing_stats)
                if data.get("system_error") and data.get("business_ng"):
                    print(
                        "repeated_system_error_stock_stop "
                        f"asin={asin} streak={repeated_error_streak} "
                        f"reason={data.get('system_error_reason') or data.get('ng_reason')}"
                    )

                print("取得結果:")
                print(f"  asin           : {data.get('asin')}")
                print(f"  title          : {data.get('title')}")
                print(f"  amazon_price   : {data.get('amazon_price')}")
                print(f"  amazon_point   : {data.get('amazon_point')}")
                print(f"  available_qty  : {data.get('available_qty')}")
                print(f"  gift_available : {data.get('gift_available')}")
                print(f"  shipping_status: {data.get('shipping_status')}")
                print(f"  business_ng    : {data.get('business_ng')}")
                print(f"  system_error   : {data.get('system_error')}")
                print(f"  ng_reason      : {data.get('ng_reason')}")

                save_to_db(data)
                print("amazon_products save: OK")

                if data.get("system_error") and not data.get("business_ng"):
                    print(f"target recalc skipped: asin={asin} reason=system_error")
                else:
                    recalc_store_codes = fetch_store_codes_for_asin(asin)
                    if not recalc_store_codes:
                        print(f"target recalc: skip asin={asin} stores=0")
                    else:
                        for recalc_store_code in recalc_store_codes:
                            try:
                                recalc_result = run_target_recalc_for_asin(asin, recalc_store_code)
                                print(
                                    "target recalc: "
                                    f"store={recalc_store_code} "
                                    f"asin={asin} "
                                    f"rows={recalc_result.get('rows', 0)} "
                                    f"updated={recalc_result.get('updated', 0)} "
                                    f"errors={recalc_result.get('errors', 0)}"
                                )
                            except Exception as recalc_error:
                                print(
                                    "target recalc error: "
                                    f"store={recalc_store_code} asin={asin} error={recalc_error}"
                                )

                if data.get("business_ng"):
                    business_ng_count += 1

                if args.use_stats:
                    stats_update = determine_stats_update(previous, data, existing_stats)
                    update_amazon_check_stats(asin, stats_update)
                    stats_updated_count += 1

                    if stats_update["system_error_detected"]:
                        system_error_count += 1
                    elif stats_update["change_detected"]:
                        changed_count += 1
                    elif stats_update["stable_detected"]:
                        stable_count += 1

                if data.get("system_error"):
                    error_count += 1
                else:
                    success_count += 1

                if data.get("system_error"):
                    system_error_continued_count += 1
                elif data.get("business_ng"):
                    business_ng_changed_count += 1
                else:
                    normalized_count += 1

                final_reason_counter[str(data.get("ng_reason") or "")] += 1
                result_asins.append(asin)

                print("DB保存OK")

                if data.get("page_needs_reset"):
                    print("共有pageの再作成が必要なため、次の商品に進む前にChrome/pageを再初期化します。")
                    page_reset_count += 1
                    await close_amazon_page(playwright, browser, context, shared_page)
                    playwright, browser, context, shared_page = await create_amazon_page()
                    print("共有Chrome/page再初期化完了")

            except TemporaryDbError as e:

                print(f"temporary DB error: asin={asin} error={e}")
                return DB_RETRY_EXIT_CODE

            except Exception as e:
                error_count += 1
                if args.use_stats:
                    try:
                        existing_stats = get_existing_stats(asin)
                        stats_update = build_error_stats_update(existing_stats)
                        update_amazon_check_stats(asin, stats_update)
                        system_error_count += 1
                        stats_updated_count += 1
                    except TemporaryDbError as db_error:
                        print(f"temporary DB error while handling asin={asin}: {db_error}")
                        return DB_RETRY_EXIT_CODE
                print(f"エラー: {e}")

                try:
                    print("エラー後の共有Chrome/page再初期化を試みます。")
                    page_reset_count += 1
                    await close_amazon_page(playwright, browser, context, shared_page)
                    playwright, browser, context, shared_page = await create_amazon_page()
                    print("共有Chrome/page再初期化完了")
                except Exception as reset_error:
                    print(f"共有Chrome/page再初期化エラー: {reset_error}")
                    shared_page = None

            asin_elapsed = time.perf_counter() - asin_started_perf
            print(f"asin={asin} elapsed={asin_elapsed:.1f}s result={asin_result_label(data) if 'data' in locals() and isinstance(data, dict) else 'error'}")
            print("")

    finally:
        await close_amazon_page(playwright, browser, context, shared_page)

    finished_at_dt = datetime.now()
    elapsed_seconds = round(time.perf_counter() - started_perf, 3)
    avg_seconds_per_item = round(elapsed_seconds / metrics["checked_count"], 3) if metrics["checked_count"] else 0.0
    metrics["success_count"] = success_count
    metrics["system_error_count"] = system_error_count
    metrics["business_ng_count"] = business_ng_count
    metrics["changed_count"] = changed_count
    metrics["stable_count"] = stable_count
    metrics["page_reset_count"] = page_reset_count
    metrics["elapsed_seconds"] = elapsed_seconds
    metrics["avg_seconds_per_item"] = avg_seconds_per_item
    metrics["finished_at"] = finished_at_dt
    metrics["finished_at_text"] = finished_at_dt.strftime("%Y/%m/%d %H:%M:%S")
    metrics["finished_at_iso"] = finished_at_dt.isoformat(timespec="seconds")

    print("完了")
    print(f"成功扱い      : {success_count}")
    print(f"エラー扱い    : {error_count}")
    if args.summary:
        print(f"stats方式      : {'ON' if args.use_stats else 'OFF'}")
        if args.use_stats:
            print(f"worker_id      : {worker_id}")
            print(f"claimed_count    : {metrics['claimed_count']}")
            print(f"checked_count    : {metrics['checked_count']}")
            print(f"success_count    : {metrics['success_count']}")
        print(f"今回チェック件数: {len(asins)}")
        print(f"変化あり件数  : {changed_count}")
        print(f"安定件数      : {stable_count}")
        print(f"システムエラー件数: {system_error_count}")
        print(f"business_ng件数: {business_ng_count}")
        print(f"page_reset件数 : {page_reset_count}")
        print(f"elapsed_seconds: {elapsed_seconds:.3f}")
        print(f"avg_seconds/item: {avg_seconds_per_item:.3f}")
        print(f"started_at     : {metrics['started_at_text']}")
        print(f"next_check更新件数: {stats_updated_count}")
        print(f"finished_at    : {metrics['finished_at_text']}")
        print(f"returncode     : {metrics['returncode']}")

        if args.system_error_only:
            print(f"normalized_count            : {normalized_count}")
            print(f"business_ng_changed_count   : {business_ng_changed_count}")
            print(f"system_error_continued_count: {system_error_continued_count}")
            for reason, count in sorted(final_reason_counter.items(), key=lambda item: (-item[1], item[0])):
                print(f"reason_count[{reason}]={count}")
            print("result_asins:")
            for asin in result_asins:
                print(f"  {asin}")
        if args.use_stats:
            print(build_worker_run_summary(metrics | {"started_at": metrics["started_at_iso"], "finished_at": metrics["finished_at_iso"]}))
            try_save_run_summary()
    print(f"終了時刻      : {metrics['finished_at_text']}")

    if args.summary:
        print_db_summary()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except TemporaryDbError as e:
        print(f"temporary DB error: {e}")
        raise SystemExit(DB_RETRY_EXIT_CODE)
