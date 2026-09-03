import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from db_config import connect_db
from rakuten_auth import build_rakuten_auth_header


BASE_DIR = Path(__file__).resolve().parents[1]
BULK_GET_URL = "https://api.rms.rakuten.co.jp/es/2.0/items/bulk-get"
DEFAULT_API_INTERVAL_SECONDS = 1.1
DEFAULT_RETRY_COUNT = 5
DEFAULT_RETRY_WAIT_SECONDS = 5.0


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def chunks(values: list[str], size: int = 50):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def fetch_db_rows(conn, store_code: str, limit: int) -> list[dict[str, Any]]:
    sql = """
        SELECT
            sp.id AS store_product_id,
            sp.asin,
            sp.mall_item_code,
            COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) AS sku_code,
            sp.current_price
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        WHERE s.mall = 'rakuten'
          AND s.store_code = %s
          AND sp.enabled = TRUE
          AND COALESCE(sp.mall_item_code, '') <> ''
          AND COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) <> ''
        ORDER BY sp.id
    """
    params: list[Any] = [store_code]
    if limit > 0:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [column.name for column in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def request_bulk_get(store_code: str, manage_numbers: list[str]) -> list[dict[str, Any]]:
    response = requests.post(
        BULK_GET_URL,
        headers=build_rakuten_auth_header(store_code),
        json={"manageNumbers": manage_numbers},
        timeout=60,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:1000]}
    if not response.ok:
        raise RuntimeError(f"items.bulk.get status={response.status_code}: {json.dumps(payload, ensure_ascii=False)[:1000]}")
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise RuntimeError("items.bulk.get response does not contain results")
    return [item for item in results if isinstance(item, dict)]


def is_qps_limit_error(error: Exception) -> bool:
    message = str(error).lower()
    return "status=429" in message or "exceeded qps limitation" in message


def preview(
    store_code: str,
    limit: int,
    api_interval_seconds: float = DEFAULT_API_INTERVAL_SECONDS,
    retry_count: int = DEFAULT_RETRY_COUNT,
    retry_wait_seconds: float = DEFAULT_RETRY_WAIT_SECONDS,
) -> dict[str, Any]:
    with connect_db() as conn:
        rows = fetch_db_rows(conn, store_code, limit)
    by_manage: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_manage.setdefault(str(row["mall_item_code"]), []).append(row)

    rms_items: dict[str, dict[str, Any]] = {}
    api_errors: list[dict[str, str]] = []
    api_request_count = 0
    api_retry_count = 0
    last_request_at: float | None = None
    for batch in chunks(list(by_manage), 50):
        for attempt in range(retry_count + 1):
            if last_request_at is not None:
                remaining = api_interval_seconds - (time.monotonic() - last_request_at)
                if remaining > 0:
                    time.sleep(remaining)
            last_request_at = time.monotonic()
            api_request_count += 1
            try:
                for item in request_bulk_get(store_code, batch):
                    manage_number = str(item.get("manageNumber") or "").strip()
                    if manage_number:
                        rms_items[manage_number] = item
                break
            except Exception as exc:
                if is_qps_limit_error(exc) and attempt < retry_count:
                    api_retry_count += 1
                    wait_seconds = retry_wait_seconds * (attempt + 1)
                    print(
                        f"RMS QPS制限のため再試行します: "
                        f"batch={','.join(batch[:2])}... attempt={attempt + 1}/{retry_count} wait={wait_seconds:.1f}s"
                    )
                    time.sleep(wait_seconds)
                    continue
                api_errors.append({"manage_numbers": ",".join(batch), "error": str(exc)})
                break

    differences: list[dict[str, Any]] = []
    genre_updates: list[dict[str, Any]] = []
    unchanged_count = 0
    unavailable: list[dict[str, Any]] = []
    for manage_number, db_rows in by_manage.items():
        item = rms_items.get(manage_number)
        if not item:
            unavailable.extend({**row, "reason": "RMS商品を取得できませんでした"} for row in db_rows)
            continue
        rms_genre_id = to_int(item.get("genreId"))
        variants = item.get("variants") if isinstance(item.get("variants"), dict) else {}
        for row in db_rows:
            variant = variants.get(str(row["sku_code"]))
            rms_price = to_int(variant.get("standardPrice")) if isinstance(variant, dict) else None
            if rms_price is None:
                unavailable.append({**row, "reason": "RMS販売価格を取得できませんでした"})
                continue
            entry = {
                "store_product_id": row["store_product_id"],
                "asin": row.get("asin") or "",
                "manage_number": manage_number,
                "sku_code": row["sku_code"],
                "db_price": to_int(row.get("current_price")),
                "rms_price": rms_price,
            }
            if rms_genre_id is not None:
                genre_updates.append({
                    "store_product_id": row["store_product_id"],
                    "rms_genre_id": rms_genre_id,
                })
            if entry["db_price"] == rms_price:
                unchanged_count += 1
            else:
                differences.append(entry)
    return {
        "store": store_code,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "db_row_count": len(rows),
        "manage_number_count": len(by_manage),
        "api_batch_count": (len(by_manage) + 49) // 50,
        "api_request_count": api_request_count,
        "api_interval_seconds": api_interval_seconds,
        "api_retry_count": api_retry_count,
        "difference_count": len(differences),
        "genre_update_candidate_count": len(genre_updates),
        "unchanged_count": unchanged_count,
        "unavailable_count": len(unavailable),
        "differences": differences,
        "genre_updates": genre_updates,
        "unavailable": unavailable,
        "api_errors": api_errors,
    }


def apply_preview(path: Path, store_code: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if str(data.get("store") or "") != store_code:
        raise RuntimeError("確認結果の店舗が一致しません")
    differences = data.get("differences") if isinstance(data.get("differences"), list) else []
    genre_updates = data.get("genre_updates") if isinstance(data.get("genre_updates"), list) else []
    updated = 0
    genre_updated = 0
    skipped_changed = 0
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE store_products ADD COLUMN IF NOT EXISTS rakuten_genre_id BIGINT")
            for row in differences:
                db_price = to_int(row.get("db_price"))
                rms_price = to_int(row.get("rms_price"))
                product_id = to_int(row.get("store_product_id"))
                if product_id is None or rms_price is None:
                    continue
                cur.execute(
                    """
                    UPDATE store_products
                    SET current_price = %s,
                        current_status = 'synced',
                        api_last_synced_at = CURRENT_TIMESTAMP,
                        api_last_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND current_price IS NOT DISTINCT FROM %s
                    """,
                    (rms_price, product_id, db_price),
                )
                if cur.rowcount:
                    updated += 1
                else:
                    skipped_changed += 1
            for row in genre_updates:
                product_id = to_int(row.get("store_product_id"))
                genre_id = to_int(row.get("rms_genre_id"))
                if product_id is None or genre_id is None or genre_id <= 0:
                    continue
                cur.execute(
                    """
                    UPDATE store_products
                    SET rakuten_genre_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND rakuten_genre_id IS DISTINCT FROM %s
                    """,
                    (genre_id, product_id, genre_id),
                )
                genre_updated += int(cur.rowcount or 0)
        conn.commit()
    return {
        "store": store_code,
        "source_preview": str(path),
        "difference_count": len(differences),
        "updated_count": updated,
        "genre_updated_count": genre_updated,
        "skipped_changed_count": skipped_changed,
        "applied_at": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RMS items.bulk.getで価格を確認し、必要ならDBへ反映します。")
    parser.add_argument("--store", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--api-interval", type=float, default=DEFAULT_API_INTERVAL_SECONDS)
    parser.add_argument("--retry-count", type=int, default=DEFAULT_RETRY_COUNT)
    parser.add_argument("--retry-wait", type=float, default=DEFAULT_RETRY_WAIT_SECONDS)
    args = parser.parse_args()
    if args.limit < 0:
        raise RuntimeError("--limit は0（全件）以上で指定してください")
    if args.api_interval < 1:
        raise RuntimeError("--api-interval はQPS制限回避のため1秒以上で指定してください")
    if args.retry_count < 0:
        raise RuntimeError("--retry-count は0以上で指定してください")
    if args.retry_wait < 0:
        raise RuntimeError("--retry-wait は0以上で指定してください")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.execute:
        if not args.input:
            raise RuntimeError("DB反映には --input で確認結果JSONが必要です")
        result = apply_preview(Path(args.input), args.store)
    else:
        result = preview(
            args.store,
            args.limit,
            api_interval_seconds=args.api_interval,
            retry_count=args.retry_count,
            retry_wait_seconds=args.retry_wait,
        )
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"differences", "unavailable"}}, ensure_ascii=False))
    print(f"RMS_PRICE_DB_SYNC_RESULT={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
