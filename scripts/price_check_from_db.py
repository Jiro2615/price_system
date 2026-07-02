import argparse
import asyncio
import os
import socket
from datetime import datetime, timedelta
from typing import Any

from db_config import connect_db
from price_check_one_asin_db import check_amazon_one, close_amazon_page, create_amazon_page, save_to_db


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


def claim_target_asins_by_stats(limit: int, worker_id: str, lock_minutes: int = 30) -> list[dict[str, Any]]:
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
                    s.next_check_at IS NULL
                    OR s.next_check_at <= CURRENT_TIMESTAMP
                )
                AND
                (
                    s.status IN ('pending', 'done')
                    OR (s.status = 'processing' AND s.lock_expires_at < CURRENT_TIMESTAMP)
                )
            ORDER BY
                s.last_checked_at ASC NULLS FIRST,
                s.next_check_at ASC NULLS FIRST,
                s.priority_score DESC,
                s.asin
            FOR UPDATE OF s SKIP LOCKED
            LIMIT %s
        )
        UPDATE amazon_check_stats s
        SET
            status = 'processing',
            worker_id = %s,
            locked_at = CURRENT_TIMESTAMP,
            lock_expires_at = CURRENT_TIMESTAMP + (%s || ' minutes')::interval,
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
            cur.execute(sql, (limit, worker_id, lock_minutes))
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
    parser.add_argument("--worker-id", default="", help="stats方式で使うワーカーID。未指定なら自動生成")
    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit は 1以上にしてください。")
        return 2

    print("DBから対象ASINを取得します。")
    print(f"limit={args.limit}, hours={args.hours}")
    print(f"use_stats={args.use_stats}")
    worker_id = args.worker_id.strip() or build_worker_id()
    if args.use_stats:
        print(f"worker_id={worker_id}")

    if args.summary:
        print_db_summary()

    claimed_rows: list[dict[str, Any]] = []

    if args.use_stats:
        ensure_amazon_check_stats_schema()
        ensure_amazon_check_stats_rows()
        released_count = release_expired_processing_locks()
        if released_count > 0:
            print(f"期限切れprocessingを自動解除しました: {released_count}件")
        claimed_rows = claim_target_asins_by_stats(args.limit, worker_id)
        asins = [row["asin"] for row in claimed_rows]
    else:
        asins = get_target_asins(args.limit, args.hours)

    if not asins:
        print("対象ASINがありません。")
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
            print(f"===== {idx}/{len(asins)} {asin} =====")
            existing_stats: dict[str, Any] | None = None

            try:
                previous = get_previous_amazon_state(asin) if args.use_stats else None
                existing_stats = get_existing_stats(asin) if args.use_stats else None
                data = await check_amazon_one(asin, page=shared_page)

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
                    await close_amazon_page(playwright, browser, context, shared_page)
                    playwright, browser, context, shared_page = await create_amazon_page()
                    print("共有Chrome/page再初期化完了")
                except Exception as reset_error:
                    print(f"共有Chrome/page再初期化エラー: {reset_error}")
                    shared_page = None

            print("")

    finally:
        await close_amazon_page(playwright, browser, context, shared_page)

    print("完了")
    print(f"成功扱い      : {success_count}")
    print(f"エラー扱い    : {error_count}")
    if args.summary:
        print(f"stats方式      : {'ON' if args.use_stats else 'OFF'}")
        if args.use_stats:
            print(f"worker_id      : {worker_id}")
        print(f"今回チェック件数: {len(asins)}")
        print(f"変化あり件数  : {changed_count}")
        print(f"安定件数      : {stable_count}")
        print(f"システムエラー件数: {system_error_count}")
        print(f"next_check更新件数: {stats_updated_count}")
    print(f"終了時刻      : {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

    if args.summary:
        print_db_summary()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
