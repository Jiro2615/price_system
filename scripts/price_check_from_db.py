import argparse
import asyncio
import builtins
import os
import socket
import sys
import time
from datetime import datetime, timedelta
from typing import Any

from db_config import connect_db
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


configure_output()
print = safe_print


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
        ADD COLUMN IF NOT EXISTS lock_expires_at TIMESTAMP;
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
) -> list[dict[str, Any]]:
    """
    due な ASIN をまとめて claim/lock し、この実行で処理する固定リストを返す。
    """

    sql = """
        WITH target_rows AS (
            SELECT
                s.asin,
                s.status AS old_status,
                s.next_check_at AS old_next_check_at
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
            f"worker_id={row.get('worker_id')}"
        )

    if len(claimed_rows) > max_rows:
        print(f"... 他 {len(claimed_rows) - max_rows} 件")
    print("")


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
            lock_expires_at
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
            }
    finally:
        conn.close()


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def determine_stats_update(previous: dict[str, Any] | None, current: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    stats = existing or {
        "check_count": 0,
        "price_change_count": 0,
        "stock_change_count": 0,
        "ng_change_count": 0,
        "error_count": 0,
        "stable_count": 0,
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


async def main() -> int:
    parser = argparse.ArgumentParser(description="DBからASINを取得してAmazon価格チェックを実行します。")
    parser.add_argument("--limit", type=int, default=10, help="今回チェックする最大件数")
    parser.add_argument("--hours", type=int, default=6, help="何時間以上前のチェック結果を再チェック対象にするか")
    parser.add_argument("--summary", action="store_true", help="実行前後にDB件数サマリを表示する")
    parser.add_argument("--use-stats", action="store_true", help="amazon_check_stats.next_check_at を使って対象ASINを選ぶ")
    parser.add_argument("--system-error-only", action="store_true", help="amazon_products.system_error = TRUE のASINだけを再チェックする")
    parser.add_argument("--worker-id", default="", help="stats方式で使うワーカーID。未指定なら自動生成")
    parser.add_argument("--page-timeout", type=int, default=60000, help="page.goto の timeout(ms)")
    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit は 1以上にしてください。")
        return 2
    if args.system_error_only and not args.use_stats:
        print("--system-error-only は --use-stats と一緒に指定してください。")
        return 2

    print("DBから対象ASINを取得します。")
    print(f"limit={args.limit}, hours={args.hours}")
    print(f"use_stats={args.use_stats}")
    print(f"system_error_only={args.system_error_only}")
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
    if args.use_stats:
        print(f"worker_id={worker_id}")

    if args.summary:
        print_db_summary()

    claimed_rows: list[dict[str, Any]] = []

    if args.use_stats:
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
            save_worker_run_summary(metrics)
        return 0

    if args.summary and args.use_stats:
        print_claimed_asins(claimed_rows)

    print("")
    print("対象ASIN:")
    for asin in asins:
        print(f"  {asin}")

    print("")
    print("Amazonチェック開始")
    print("")

    success_count = 0
    error_count = 0
    changed_count = 0
    stable_count = 0
    system_error_count = 0
    business_ng_count = 0
    page_reset_count = 0
    stats_updated_count = 0

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

                print("DB保存OK")

                if data.get("page_needs_reset"):
                    print("共有pageの再作成が必要なため、次の商品に進む前にChrome/pageを再初期化します。")
                    page_reset_count += 1
                    await close_amazon_page(playwright, browser, context, shared_page)
                    playwright, browser, context, shared_page = await create_amazon_page()
                    print("共有Chrome/page再初期化完了")

            except Exception as e:
                error_count += 1
                if args.use_stats:
                    existing_stats = get_existing_stats(asin)
                    stats_update = build_error_stats_update(existing_stats)
                    update_amazon_check_stats(asin, stats_update)
                    system_error_count += 1
                    stats_updated_count += 1
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
        if args.use_stats:
            print(build_worker_run_summary(metrics | {"started_at": metrics["started_at_iso"], "finished_at": metrics["finished_at_iso"]}))
            save_worker_run_summary(metrics)
    print(f"終了時刻      : {metrics['finished_at_text']}")

    if args.summary:
        print_db_summary()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
