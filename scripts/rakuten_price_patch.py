import argparse
import base64
import csv
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from db_config import connect_db
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from rakuten_auth import build_rakuten_auth_header, resolve_rakuten_store_code


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR.parent / ".env"
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_api"

RAKUTEN_ITEM_BASE_URL = "https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers"
RAKUTEN_ITEM_SEARCH_URL = "https://api.rms.rakuten.co.jp/es/2.0/items/search"
RETRY_STATE_TABLE = "rakuten_price_api_retry_state"
PENDING_STATE_TABLE = "rakuten_price_api_pending_state"


# =========================
# 共通ユーティリティ
# =========================

def now_text() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return default


def load_auth_header() -> dict[str, str]:
    load_dotenv(ENV_PATH)

    service_secret = os.getenv("RAKUTEN_1_SERVICE_SECRET", "").strip()
    license_key = os.getenv("RAKUTEN_1_LICENSE_KEY", "").strip()

    if not service_secret:
        raise RuntimeError(f"RAKUTEN_SERVICE_SECRET が空です: {ENV_PATH}")

    if not license_key:
        raise RuntimeError(f"RAKUTEN_LICENSE_KEY が空です: {ENV_PATH}")

    token_src = f"{service_secret}:{license_key}".encode("utf-8")
    token = base64.b64encode(token_src).decode("ascii")

    return {
        "Authorization": f"ESA {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def write_json_file(prefix: str, data: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{prefix}_{now_text()}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def item_url(manage_number: str) -> str:
    encoded = quote(str(manage_number), safe="")
    return f"{RAKUTEN_ITEM_BASE_URL}/{encoded}"


def item_search_url(manage_number: str) -> str:
    """Return an exact manage-number search URL for a 404 confirmation."""
    encoded = quote(str(manage_number), safe="")
    return f"{RAKUTEN_ITEM_SEARCH_URL}?manageNumber={encoded}&hits=1&cursorMark=%2A"


# =========================
# DB取得
# =========================

def normalize_csv_header(value: str) -> str:
    return re.sub(r"[\s_\-（）()\[\]【】/\\]+", "", str(value or "")).casefold()


def first_csv_value(row: dict[str, str], aliases: list[str]) -> str:
    normalized = {normalize_csv_header(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(normalize_csv_header(alias))
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def read_csv_targets(path: Path) -> list[dict[str, Any]]:
    encodings = ["utf-8-sig", "cp932"]
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                targets: list[dict[str, Any]] = []
                for row in reader:
                    manage_number = first_csv_value(row, [
                        "manage_number",
                        "managenumber",
                        "mall_item_code",
                        "item_code",
                        "item_url",
                        "item_url_code",
                        "rakuten_manage_number",
                        "rakuten_management_number",
                        "商品管理番号",
                        "商品番号",
                        "管理番号",
                        "楽天管理番号",
                        "商品URL",
                    ])
                    sku = first_csv_value(row, [
                        "sku",
                        "sku_code",
                        "variantid",
                        "variant_id",
                        "sku_management_number",
                        "sku_manage_number",
                        "SKU管理番号",
                        "SKU番号",
                        "システム連携用SKU番号",
                    ])
                    price_raw = first_csv_value(row, [
                        "price",
                        "target_price",
                        "standardprice",
                        "standard_price",
                        "update_price",
                        "販売価格",
                        "価格",
                        "更新価格",
                        "標準価格",
                    ])
                    price = to_int(price_raw)
                    if not manage_number and not sku:
                        continue
                    targets.append({
                        "manage_number": manage_number,
                        "sku": sku,
                        "target_price": price,
                    })
                return targets
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def fetch_price_targets(
    store_code: str | None,
    limit: int,
    manage_number: str | None = None,
    sku_code: str | None = None,
    blocked_only: bool = False,
    skip_deferred_retries: bool = False,
    retry_large_change_holds: bool = False,
    pending_queue: bool = False,
) -> list[dict[str, Any]]:
    where = [
        "s.mall = 'rakuten'",
        "sp.enabled = TRUE",
        "COALESCE(sp.no_price_change, FALSE) = FALSE",
        "sp.target_price IS NOT NULL",
        "COALESCE(sp.current_price, -1) <> sp.target_price",
        "sp.mall_item_code IS NOT NULL",
        "sp.mall_item_code <> ''",
    ]
    params: list[Any] = []

    if store_code:
        where.append("s.store_code = %s")
        params.append(store_code)

    if manage_number:
        where.append("sp.mall_item_code = %s")
        params.append(manage_number)

    if sku_code:
        where.append("COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) = %s")
        params.append(sku_code)

    if blocked_only:
        where.append("COALESCE(sp.rakuten_csv_update_blocked, FALSE) = TRUE")

    if skip_deferred_retries:
        permanent_hold_condition = "retry_state.state = 'permanent_hold'"
        if retry_large_change_holds:
            # An operator explicitly allowed large changes for this run. Keep
            # auth/validation holds manual, but let prior rate-only holds be
            # selected again so the override has an effect.
            # psycopg uses percent-style placeholders, so literal SQL
            # wildcards must be doubled at this layer.
            permanent_hold_condition += " AND retry_state.last_error NOT ILIKE '%%価格変更率が大きすぎます%%'"
        where.append(
            f"""
            NOT EXISTS (
                SELECT 1
                FROM {RETRY_STATE_TABLE} retry_state
                WHERE retry_state.store_product_id = sp.id
                  AND retry_state.target_price = sp.target_price
                  AND (
                    {permanent_hold_condition}
                    OR (retry_state.next_retry_at IS NOT NULL AND retry_state.next_retry_at > CURRENT_TIMESTAMP)
                  )
            )
            """
        )

    pending_join = ""
    order_by = "s.store_code, sp.id"
    if pending_queue:
        # Amazon checks update store_products.updated_at frequently.  Queue
        # order must instead remain tied to the first unresolved price change.
        pending_join = (
            f"LEFT JOIN {PENDING_STATE_TABLE} pending_state "
            "ON pending_state.store_product_id = sp.id"
        )
        order_by = "pending_state.pending_since ASC NULLS LAST, s.store_code, sp.id"

    sql = f"""
        SELECT
            s.id AS store_id,
            s.store_code,
            sp.id AS store_product_id,
            sp.asin,
            sp.mall_item_code,
            COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) AS sku_code,
            sp.item_name,
            sp.current_price,
            sp.target_price,
            sp.current_stock,
            sp.target_stock,
            sp.force_stop,
            sp.no_price_change,
            sp.current_status,
            ap.amazon_price,
            ap.amazon_point,
            ap.available_qty,
            ap.business_ng,
            ap.system_error,
            ap.ng_reason,
            ap.checked_at
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        LEFT JOIN amazon_products ap ON ap.asin = sp.asin
        {pending_join}
        WHERE {" AND ".join(where)}
        ORDER BY {order_by}
    """
    # ``0`` means every matching product.  Do not emulate this with a large
    # arbitrary value: a price-rule change must be able to reach the whole
    # selected store deterministically.
    if limit > 0:
        sql += " LIMIT %s"
        params.append(limit)

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            col_names = [desc.name for desc in cur.description]
            return [dict(zip(col_names, row)) for row in rows]
    finally:
        conn.close()


# =========================
# 楽天API payload
# =========================

def fetch_price_targets_from_csv(
    store_code: str | None,
    csv_targets: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if not csv_targets:
        return []
    rows: list[dict[str, Any]] = []
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            targets = csv_targets if limit == 0 else csv_targets[:limit]
            for target in targets:
                manage_number = str(target.get("manage_number") or "").strip()
                sku_code = str(target.get("sku") or "").strip()
                where = [
                    "s.mall = 'rakuten'",
                    "sp.enabled = TRUE",
                    "COALESCE(sp.no_price_change, FALSE) = FALSE",
                ]
                params: list[Any] = []
                if store_code:
                    where.append("s.store_code = %s")
                    params.append(store_code)
                if manage_number:
                    where.append("sp.mall_item_code = %s")
                    params.append(manage_number)
                if sku_code:
                    where.append("COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) = %s")
                    params.append(sku_code)
                if not manage_number and not sku_code:
                    continue
                sql = f"""
                    SELECT
                        s.id AS store_id,
                        s.store_code,
                        sp.id AS store_product_id,
                        sp.asin,
                        sp.mall_item_code,
                        COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) AS sku_code,
                        sp.item_name,
                        sp.current_price,
                        sp.target_price,
                        sp.current_stock,
                        sp.target_stock,
                        sp.force_stop,
                        sp.no_price_change,
                        sp.current_status,
                        ap.amazon_price,
                        ap.amazon_point,
                        ap.available_qty,
                        ap.business_ng,
                        ap.system_error,
                        ap.ng_reason,
                        ap.checked_at
                    FROM store_products sp
                    JOIN stores s ON s.id = sp.store_id
                    LEFT JOIN amazon_products ap ON ap.asin = sp.asin
                    WHERE {" AND ".join(where)}
                    ORDER BY s.store_code, sp.id
                    LIMIT 1;
                """
                cur.execute(sql, params)
                row = cur.fetchone()
                if not row:
                    continue
                col_names = [desc.name for desc in cur.description]
                data = dict(zip(col_names, row))
                if target.get("target_price") is not None:
                    data["target_price"] = target["target_price"]
                rows.append(data)
    finally:
        conn.close()
    return rows


def build_price_patch_payload(row: dict[str, Any]) -> dict[str, Any]:
    sku = str(row.get("sku_code") or row.get("mall_item_code") or "").strip()
    target_price = to_int(row.get("target_price"))

    if not sku:
        raise ValueError("sku_code が空です")

    if target_price is None:
        raise ValueError("target_price が空です")

    if target_price <= 0:
        raise ValueError(f"target_price が不正です: {target_price}")

    # items.get で variants.{sku}.standardPrice が文字列で返ってくるため、文字列で送る。
    return {
        "variants": {
            sku: {
                "standardPrice": str(target_price)
            }
        }
    }


def build_all_dry_run_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for row in rows:
        manage_number = str(row.get("mall_item_code") or "").strip()
        payload = build_price_patch_payload(row)
        items.append({
            "store_product_id": row.get("store_product_id"),
            "store_code": row.get("store_code"),
            "asin": row.get("asin"),
            "manageNumber": manage_number,
            "variantId": row.get("sku_code"),
            "current_price": row.get("current_price"),
            "target_price": row.get("target_price"),
            "request_url": item_url(manage_number),
            "request_method": "PATCH",
            "request_json": payload,
        })
    return {
        "api_name": "items.patch",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_targets": len(rows),
        "items": items,
    }


# =========================
# 安全チェック
# =========================

def validate_price_change(
    row: dict[str, Any],
    max_change_rate: float,
    allow_large_change: bool,
    allow_current_price_null: bool,
) -> None:
    current_price = to_int(row.get("current_price"))
    target_price = to_int(row.get("target_price"))

    if target_price is None or target_price <= 0:
        raise ValueError(f"target_price が不正です: {target_price}")

    if target_price > 99999999:
        raise ValueError(f"target_price が大きすぎます: {target_price}")

    if current_price is None:
        if allow_current_price_null:
            return
        raise ValueError("current_price がNULLです。--allow-current-price-null を付けない限り実更新しません。")

    if current_price <= 0:
        raise ValueError(f"current_price が不正です: {current_price}")

    if allow_large_change:
        return

    if max_change_rate > 0:
        diff_rate = abs(target_price - current_price) / current_price
        if diff_rate > max_change_rate:
            raise ValueError(
                f"価格変更率が大きすぎます: current={current_price}, target={target_price}, "
                f"diff_rate={diff_rate:.2%}, limit={max_change_rate:.2%}. "
                "実行するなら --allow-large-change を付けてください。"
            )


# =========================
# 楽天API実行
# =========================

def parse_response_json(res: requests.Response) -> dict[str, Any]:
    try:
        return res.json() if res.text else {}
    except Exception:
        return {"_raw_text": res.text}


def retry_wait_seconds(res: requests.Response, retry_wait: float, attempt: int) -> float:
    retry_after = res.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except Exception:
            pass

    # 429のときは少しずつ待ち時間を伸ばす。
    return max(retry_wait * attempt, 1.0)


def print_wait_log(action: str, reason: str, seconds: float, **extra: Any) -> None:
    parts = [f"next_action={action}", f"seconds={seconds:.1f}", f"reason={reason}"]
    for key, value in extra.items():
        parts.append(f"{key}={value}")
    print(" ".join(parts))


def call_rakuten_api_with_retry(
    method: str,
    url: str,
    *,
    store_code: str,
    payload: dict[str, Any] | None = None,
    api_label: str,
    max_retries: int,
    retry_wait: float,
) -> tuple[int, dict[str, Any]]:
    headers = build_rakuten_auth_header(store_code)
    retry_statuses = {429, 500, 502, 503, 504}

    for attempt in range(1, max_retries + 2):
        print(f"{method} {url}")

        if method.upper() == "PATCH":
            res = requests.patch(url, headers=headers, json=payload, timeout=60)
        elif method.upper() == "GET":
            res = requests.get(url, headers=headers, timeout=60)
        else:
            raise ValueError(f"未対応HTTPメソッドです: {method}")

        print(f"status_code={res.status_code}")
        data = parse_response_json(res)

        if 200 <= res.status_code < 300:
            return res.status_code, data

        if res.status_code in retry_statuses and attempt <= max_retries:
            wait_sec = retry_wait_seconds(res, retry_wait, attempt)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            print_wait_log("sleep_retry", "api_retry", wait_sec, status=res.status_code, attempt=attempt)
            print(f"  {api_label}: status={res.status_code} のため {wait_sec:.1f} 秒待って再試行します ({attempt}/{max_retries})")
            time.sleep(wait_sec)
            continue

        print(json.dumps(data, ensure_ascii=False, indent=2))
        raise RuntimeError(f"{api_label}エラー status={res.status_code}: {data}")

    raise RuntimeError(f"{api_label}エラー: retry exhausted")


def call_item_patch(
    manage_number: str,
    store_code: str,
    payload: dict[str, Any],
    max_retries: int,
    retry_wait: float,
) -> dict[str, Any]:
    url = item_url(manage_number)
    status_code, data = call_rakuten_api_with_retry(
        "PATCH",
        url,
        store_code=store_code,
        payload=payload,
        api_label="楽天価格更新API",
        max_retries=max_retries,
        retry_wait=retry_wait,
    )

    return {
        "status_code": status_code,
        "body": data,
    }


def call_item_get(
    manage_number: str,
    store_code: str,
    max_retries: int,
    retry_wait: float,
) -> dict[str, Any]:
    url = item_url(manage_number)
    _status_code, data = call_rakuten_api_with_retry(
        "GET",
        url,
        store_code=store_code,
        api_label="楽天items.get",
        max_retries=max_retries,
        retry_wait=retry_wait,
    )

    return data


def confirm_item_absent_in_search(
    manage_number: str,
    store_code: str,
    max_retries: int,
    retry_wait: float,
) -> tuple[bool, dict[str, Any]]:
    """Confirm that a price-patch 404 is a deleted Item API record.

    The inventory API can retain an orphaned inventory row after the Item API
    record has disappeared.  Do not disable a DB product merely because PATCH
    returned 404: require an exact Item API search with no item result too.
    """
    _status_code, data = call_rakuten_api_with_retry(
        "GET",
        item_search_url(manage_number),
        store_code=store_code,
        api_label="楽天items.search（404確認）",
        max_retries=max_retries,
        retry_wait=retry_wait,
    )
    results = data.get("results") if isinstance(data, dict) else None
    found = any(
        isinstance(result, dict)
        and isinstance(result.get("item"), dict)
        and str(result["item"].get("manageNumber") or "").strip() == str(manage_number).strip()
        for result in (results or [])
    )
    return (not found), data if isinstance(data, dict) else {}


def is_item_api_not_found(error_message: str) -> bool:
    message = str(error_message or "")
    return "status=404" in message and ("楽天価格更新API" in message or "楽天items.get" in message)


def extract_standard_price(item_data: dict[str, Any], sku_code: str) -> int | None:
    variants = item_data.get("variants") or {}
    variant = variants.get(sku_code)
    if not variant:
        return None

    value = variant.get("standardPrice")
    if value is None or value == "":
        return None

    return to_int(value)


# =========================
# DB更新・ログ
# =========================

def get_table_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


def ensure_retry_state_table(conn) -> None:
    """Create the small retry-state table on first continuous API use."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {RETRY_STATE_TABLE} (
                    store_product_id BIGINT PRIMARY KEY REFERENCES store_products(id) ON DELETE CASCADE,
                    store_code TEXT NOT NULL,
                    target_price INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('retry_scheduled', 'permanent_hold')),
                    failure_kind TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TIMESTAMPTZ,
                    last_error TEXT NOT NULL DEFAULT '',
                    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_rakuten_price_api_retry_state_due
                ON {RETRY_STATE_TABLE} (store_code, state, next_retry_at)
                """
            )


def ensure_pending_state_table(conn) -> None:
    """Create the durable queue used by the continuous price API worker."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {PENDING_STATE_TABLE} (
                    store_product_id BIGINT PRIMARY KEY REFERENCES store_products(id) ON DELETE CASCADE,
                    store_code TEXT NOT NULL,
                    target_price INTEGER NOT NULL,
                    pending_since TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_rakuten_price_api_pending_state_order
                ON {PENDING_STATE_TABLE} (store_code, pending_since, store_product_id)
                """
            )


def refresh_pending_price_queue(conn, store_code: str | None) -> None:
    """Keep the durable queue aligned with actual unresolved price changes.

    The timestamp changes only when target_price changes.  Successful updates
    and recalculations that remove the difference are immediately removed.
    """
    store_condition = ""
    params: list[Any] = []
    if store_code:
        store_condition = " AND s.store_code = %s"
        params.append(store_code)

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {PENDING_STATE_TABLE} (
                    store_product_id, store_code, target_price, pending_since, created_at, updated_at
                )
                SELECT sp.id, s.store_code, sp.target_price, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM store_products sp
                JOIN stores s ON s.id = sp.store_id
                WHERE s.mall = 'rakuten'
                  AND sp.enabled = TRUE
                  AND COALESCE(sp.no_price_change, FALSE) = FALSE
                  AND sp.target_price IS NOT NULL
                  AND COALESCE(sp.current_price, -1) <> sp.target_price
                  AND COALESCE(sp.mall_item_code, '') <> ''
                  {store_condition}
                ON CONFLICT (store_product_id) DO UPDATE SET
                    store_code = EXCLUDED.store_code,
                    target_price = EXCLUDED.target_price,
                    pending_since = CASE
                        WHEN {PENDING_STATE_TABLE}.target_price IS DISTINCT FROM EXCLUDED.target_price
                            THEN CURRENT_TIMESTAMP
                        ELSE {PENDING_STATE_TABLE}.pending_since
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                tuple(params),
            )
            cur.execute(
                f"""
                DELETE FROM {PENDING_STATE_TABLE} pending_state
                USING store_products sp
                JOIN stores s ON s.id = sp.store_id
                WHERE pending_state.store_product_id = sp.id
                  AND s.mall = 'rakuten'
                  AND (%s::text IS NULL OR s.store_code = %s)
                  AND (
                    sp.enabled IS NOT TRUE
                    OR COALESCE(sp.no_price_change, FALSE) = TRUE
                    OR sp.target_price IS NULL
                    OR COALESCE(sp.current_price, -1) = sp.target_price
                    OR COALESCE(sp.mall_item_code, '') = ''
                  )
                """,
                (store_code, store_code),
            )


def classify_retry_failure(error_message: str, previous_attempts: int, previous_kind: str) -> tuple[str, str, int | None]:
    """Return failure kind, persisted state, and retry delay in seconds."""
    normalized = str(error_message or "").lower()
    verification_mismatch = "価格不一致" in str(error_message or "") or "verified=" in normalized
    permanent_markers = (
        "価格変更率が大きすぎます",
        "current_price がnull",
        "current_price が不正",
        "target_price が不正",
        "sku_code が空",
        "managenumber が空",
        "status=400",
        "status=401",
        "status=403",
        "status=404",
        "認証",
        "unauthorized",
        "forbidden",
        "not found",
    )
    if verification_mismatch:
        if previous_kind == "verification_delay" and previous_attempts >= 1:
            return "verification_mismatch", "permanent_hold", None
        return "verification_delay", "retry_scheduled", 5 * 60
    if any(marker.lower() in normalized for marker in permanent_markers):
        return "permanent_error", "permanent_hold", None
    # The request function already retries 429 and transient 5xx responses in
    # the same cycle.  Persisted retries are deliberately slower.
    delay_schedule = (5 * 60, 15 * 60, 60 * 60)
    return "transient_error", "retry_scheduled", delay_schedule[min(previous_attempts, len(delay_schedule) - 1)]


def record_retry_state(cur, row: dict[str, Any], error_message: str) -> dict[str, Any]:
    target_price = int(to_int(row.get("target_price")) or 0)
    cur.execute(
        f"""
        SELECT target_price, failure_kind, attempt_count
        FROM {RETRY_STATE_TABLE}
        WHERE store_product_id = %s
        FOR UPDATE
        """,
        (row["store_product_id"],),
    )
    previous = cur.fetchone()
    previous_target, previous_kind, previous_attempts = previous if previous else (None, "", 0)
    if previous_target != target_price:
        previous_kind, previous_attempts = "", 0
    failure_kind, state, retry_delay = classify_retry_failure(error_message, int(previous_attempts or 0), str(previous_kind or ""))
    attempts = int(previous_attempts or 0) + 1
    next_retry_at = (
        datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
        if retry_delay is not None
        else None
    )
    cur.execute(
        f"""
        INSERT INTO {RETRY_STATE_TABLE} (
            store_product_id, store_code, target_price, state, failure_kind,
            attempt_count, next_retry_at, last_error, last_attempt_at, updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (store_product_id) DO UPDATE SET
            store_code = EXCLUDED.store_code,
            target_price = EXCLUDED.target_price,
            state = EXCLUDED.state,
            failure_kind = EXCLUDED.failure_kind,
            attempt_count = EXCLUDED.attempt_count,
            next_retry_at = EXCLUDED.next_retry_at,
            last_error = EXCLUDED.last_error,
            last_attempt_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            row["store_product_id"], str(row.get("store_code") or ""), target_price,
            state, failure_kind, attempts, next_retry_at,
            str(error_message or "")[:2000],
        ),
    )
    return {"state": state, "failure_kind": failure_kind, "attempt_count": attempts, "retry_delay_seconds": retry_delay}


def clear_retry_state(cur, row: dict[str, Any]) -> None:
    cur.execute(f"DELETE FROM {RETRY_STATE_TABLE} WHERE store_product_id = %s", (row["store_product_id"],))


def update_success(cur, row: dict[str, Any], verified_price: int | None) -> None:
    price_to_set = verified_price if verified_price is not None else to_int(row.get("target_price"))
    cur.execute(
        """
        UPDATE store_products
        SET
            current_price = %s,
            current_status = 'synced',
            api_last_synced_at = CURRENT_TIMESTAMP,
            api_last_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (price_to_set, row["store_product_id"]),
    )


def update_failed(cur, row: dict[str, Any], error_message: str) -> None:
    cur.execute(
        """
        UPDATE store_products
        SET
            api_last_error = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (error_message[:2000], row["store_product_id"]),
    )


def update_rms_deleted(cur, row: dict[str, Any], error_message: str) -> None:
    """Disable an orphaned DB row after Item PATCH 404 + search zero match."""
    cur.execute(
        """
        UPDATE store_products
        SET enabled = FALSE,
            force_stop = TRUE,
            current_status = 'rms_deleted',
            api_last_error = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (error_message[:2000], row["store_product_id"]),
    )


def insert_price_update_log(
    cur,
    row: dict[str, Any],
    status: str,
    message: str,
    request_payload: dict[str, Any] | None,
    response_payload: dict[str, Any] | None,
) -> None:
    """
    price_update_logs の列構成がまだ固定しきれていない前提で、
    存在する列だけに best-effort でINSERTする。
    """
    columns = get_table_columns(cur, "price_update_logs")
    if not columns:
        return

    url = item_url(str(row.get("mall_item_code") or ""))

    candidates: dict[str, Any] = {
        "store_product_id": row.get("store_product_id"),
        "store_id": row.get("store_id"),
        "store_code": row.get("store_code"),
        "asin": row.get("asin"),
        "mall_item_code": row.get("mall_item_code"),
        "sku_code": row.get("sku_code"),
        "api_name": "items.patch",
        "update_type": "price",
        "update_kind": "price",
        "kind": "price",
        "type": "price",
        "old_price": row.get("current_price"),
        "current_price": row.get("current_price"),
        "new_price": row.get("target_price"),
        "target_price": row.get("target_price"),
        "old_stock": row.get("current_stock"),
        "current_stock": row.get("current_stock"),
        "new_stock": row.get("target_stock"),
        "target_stock": row.get("target_stock"),
        "status": status,
        "result": status,
        "message": message[:2000],
        "error_message": message[:2000] if status != "success" else None,
        "request_url": url,
        "url": url,
        "request_json": Jsonb(request_payload or {}),
        "response_json": Jsonb(response_payload or {}),
    }

    insert_cols = [c for c in candidates.keys() if c in columns]
    if not insert_cols:
        return

    placeholders = ", ".join(["%s"] * len(insert_cols))
    col_sql = ", ".join(insert_cols)
    values = [candidates[c] for c in insert_cols]

    cur.execute(
        f"INSERT INTO price_update_logs ({col_sql}) VALUES ({placeholders})",
        values,
    )


def save_log_best_effort(
    conn,
    row: dict[str, Any],
    status: str,
    message: str,
    request_payload: dict[str, Any] | None,
    response_payload: dict[str, Any] | None,
) -> None:
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                insert_price_update_log(
                    cur,
                    row=row,
                    status=status,
                    message=message,
                    request_payload=request_payload,
                    response_payload=response_payload,
                )
    except Exception as e:
        print(f"  注意: price_update_logs への記録に失敗しました: {e}")


def mark_success(conn, row: dict[str, Any], verified_price: int | None, request_payload: dict[str, Any], response_payload: dict[str, Any], retry_policy: bool = False) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            update_success(cur, row, verified_price)
            if retry_policy:
                clear_retry_state(cur, row)
        msg = "価格更新成功"
        if verified_price is not None:
            msg += f" verified_price={verified_price}"
        save_log_best_effort(
            conn,
            row=row,
            status="success",
            message=msg,
            request_payload=request_payload,
            response_payload=response_payload,
        )


def mark_failed(conn, row: dict[str, Any], error_message: str, request_payload: dict[str, Any] | None, retry_policy: bool = False) -> dict[str, Any] | None:
    retry_state: dict[str, Any] | None = None
    with conn.transaction():
        with conn.cursor() as cur:
            update_failed(cur, row, error_message)
            if retry_policy:
                retry_state = record_retry_state(cur, row, error_message)
        save_log_best_effort(
            conn,
            row=row,
            status="failed",
            message=error_message,
            request_payload=request_payload,
            response_payload=None,
        )
    return retry_state


def mark_rms_deleted(
    conn,
    row: dict[str, Any],
    error_message: str,
    request_payload: dict[str, Any] | None,
    search_response: dict[str, Any],
    retry_policy: bool = False,
) -> None:
    """Persist a confirmed RMS Item deletion and retain an audit log."""
    confirmation = f"RMS商品API 404、items.search 0件のためRMS削除済み: {error_message}"
    with conn.transaction():
        with conn.cursor() as cur:
            update_rms_deleted(cur, row, confirmation)
            if retry_policy:
                clear_retry_state(cur, row)
        save_log_best_effort(
            conn,
            row=row,
            status="rms_deleted",
            message=confirmation,
            request_payload=request_payload,
            response_payload={"items_search": search_response},
        )


# =========================
# 表示
# =========================

def print_targets(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("楽天価格更新対象はありません。")
        return

    print("")
    print("===== 楽天価格更新対象 =====")
    print("")

    for row in rows:
        print(
            f"[{row.get('store_code')}] "
            f"id={row.get('store_product_id')} "
            f"ASIN={row.get('asin') or ''} "
            f"manageNumber={row.get('mall_item_code') or ''} "
            f"variantId={row.get('sku_code') or ''}"
        )
        print(f"  item_name: {(row.get('item_name') or '')[:80]}")
        print(f"  price: {row.get('current_price')} -> {row.get('target_price')}")
        print(f"  stock: {row.get('current_stock')} -> {row.get('target_stock')}")
        print(
            f"  amazon: price={row.get('amazon_price')}, "
            f"point={row.get('amazon_point')}, qty={row.get('available_qty')}"
        )
        print(
            f"  ng: business={row.get('business_ng')}, "
            f"system={row.get('system_error')}, reason={row.get('ng_reason') or ''}"
        )
        print("")


def print_summary(total_targets: int, success_count: int, failed_count: int, skipped_count: int) -> None:
    print("")
    print("===== 集計 =====")
    print(f"API更新対象件数: {total_targets}")
    print(f"成功件数: {success_count}")
    print(f"失敗件数: {failed_count}")
    print(f"スキップ件数: {skipped_count}")


# =========================
# main
# =========================

def main() -> int:
    parser = argparse.ArgumentParser(description="楽天商品API items.patch でSKU価格のdry-run/実更新を行います。")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code。空文字なら楽天全店舗")
    parser.add_argument("--limit", type=int, default=0, help="対象最大件数。0なら全件")
    parser.add_argument("--manage-number", default="", help="特定の商品管理番号だけに絞る")
    parser.add_argument("--sku", default="", help="特定のSKUだけに絞る")
    parser.add_argument("--csv", default="", help="CSV file containing manage_number, sku, and optional price")
    parser.add_argument("--blocked-only", action="store_true", help="rakuten_csv_update_blocked = TRUE の商品のみ対象にする")
    parser.add_argument("--output", default="", help="送信予定JSON/結果JSONの保存先。空なら自動")
    parser.add_argument("--max-change-rate", type=float, default=0.50, help="実更新時に許可する最大価格変更率。0.50=50%%。0なら無制限")
    parser.add_argument("--allow-large-change", action="store_true", help="価格変更率チェックを無視して実更新する")
    parser.add_argument("--allow-current-price-null", action="store_true", help="current_price がNULLでも実更新する")
    verify_group = parser.add_mutually_exclusive_group()
    verify_group.add_argument("--verify", action="store_true", help="PATCH後にitems.getで反映確認する")
    verify_group.add_argument("--no-verify", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api-interval", type=float, default=1.5, help="1商品処理ごとに待つ秒数。楽天APIのQPS制限対策")
    parser.add_argument("--verify-wait", type=float, default=1.5, help="PATCH成功後、items.get確認前に待つ秒数")
    parser.add_argument("--retry-count", type=int, default=5, help="429/一時エラー時の再試行回数")
    parser.add_argument("--retry-wait", type=float, default=5.0, help="429/一時エラー時の基本待機秒数。再試行ごとに少し伸ばす")
    parser.add_argument("--retry-policy", action="store_true", help="失敗理由別の再試行待機をDBへ記録し、待機中・恒久エラーを今回の対象から除外する")
    parser.add_argument("--retry-large-change-holds", action="store_true", help="--allow-large-change 時、過去の価格変更率だけの手動保留を再試行する")
    parser.add_argument("--pending-queue", action="store_true", help="価格差分を更新待ち時刻順に再取得する（常駐ワーカー向け）")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="API送信せずJSONだけ出力する")
    mode.add_argument("--execute", action="store_true", help="楽天APIへ実更新する")

    args = parser.parse_args()

    if args.limit < 0:
        print("--limit は0以上にしてください。0は全件です。")
        return 2

    store_code = args.store.strip() or None
    manage_number = args.manage_number.strip() or None
    sku_code = args.sku.strip() or None
    csv_path = Path(args.csv) if args.csv.strip() else None
    dry_run = not args.execute

    if args.retry_policy and dry_run:
        print("--retry-policy は --execute と一緒に使用してください。")
        return 2
    if args.retry_large_change_holds and (not args.retry_policy or not args.allow_large_change):
        print("--retry-large-change-holds は --retry-policy と --allow-large-change を一緒に指定してください。")
        return 2

    if args.retry_policy or args.pending_queue:
        retry_conn = connect_db()
        try:
            if args.retry_policy:
                ensure_retry_state_table(retry_conn)
            if args.pending_queue:
                ensure_pending_state_table(retry_conn)
                refresh_pending_price_queue(retry_conn, store_code)
        finally:
            retry_conn.close()

    if csv_path:
        if not csv_path.is_absolute():
            csv_path = BASE_DIR / csv_path
        csv_targets = read_csv_targets(csv_path)
        print(f"CSV targets: {len(csv_targets)} file={csv_path}")
        rows = fetch_price_targets_from_csv(
            store_code=store_code,
            csv_targets=csv_targets,
            limit=args.limit,
        )
    else:
        rows = fetch_price_targets(
            store_code=store_code,
            limit=args.limit,
            manage_number=manage_number,
            sku_code=sku_code,
            blocked_only=args.blocked_only,
            skip_deferred_retries=args.retry_policy,
            retry_large_change_holds=args.retry_large_change_holds,
            pending_queue=args.pending_queue,
        )
    print_targets(rows)
    print(f"楽天価格更新対象件数: {len(rows)}")

    if not rows:
        print_summary(total_targets=0, success_count=0, failed_count=0, skipped_count=0)
        return 0

    try:
        all_payload = build_all_dry_run_payload(rows)
    except Exception as e:
        print(f"送信予定JSON作成エラー: {e}")
        return 1

    output_path = Path(args.output) if args.output else None

    if dry_run:
        if output_path is None:
            output_path = write_json_file("items_patch_price_dry_run", all_payload)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(all_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print("")
        print("dry-run のため楽天APIへは送信しません。")
        print(f"送信予定JSON保存: {output_path}")
        print_summary(total_targets=len(rows), success_count=0, failed_count=0, skipped_count=0)
        return 0

    print("")
    print("実更新モードです。楽天商品API items.patch へ送信します。")
    print("在庫は更新しません。SKUの standardPrice のみ更新します。")
    print(f"最大価格変更率チェック: {'無視' if args.allow_large_change else args.max_change_rate}")
    verify_enabled = bool(args.verify and not args.no_verify)
    print(f"PATCH後確認: {'items.getで確認する' if verify_enabled else 'しない'}")
    print("")

    result_summary = {
        "api_name": "items.patch",
        "executed_at": datetime.now().isoformat(timespec="seconds"),
        "total_targets": len(rows),
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "items": [],
    }

    conn = connect_db()
    try:
        auth_store_code = resolve_rakuten_store_code(store_code, rows)
        for index, row in enumerate(rows, start=1):
            manage = str(row.get("mall_item_code") or "").strip()
            sku = str(row.get("sku_code") or manage).strip()
            request_payload: dict[str, Any] | None = None

            print(f"===== {index}/{len(rows)} manageNumber={manage} sku={sku} =====")

            try:
                validate_price_change(
                    row=row,
                    max_change_rate=args.max_change_rate,
                    allow_large_change=args.allow_large_change,
                    allow_current_price_null=args.allow_current_price_null,
                )

                request_payload = build_price_patch_payload(row)
                patch_response = call_item_patch(
                    manage,
                    auth_store_code,
                    request_payload,
                    max_retries=args.retry_count,
                    retry_wait=args.retry_wait,
                )

                verified_price: int | None = None
                verify_response: dict[str, Any] | None = None

                if verify_enabled:
                    if args.verify_wait > 0:
                        print_wait_log("sleep_verify", "post_patch_verify", args.verify_wait)
                        print(f"  PATCH後確認前に {args.verify_wait:.1f} 秒待機します")
                        time.sleep(args.verify_wait)

                    verify_response = call_item_get(
                        manage,
                        auth_store_code,
                        max_retries=args.retry_count,
                        retry_wait=args.retry_wait,
                    )
                    verified_price = extract_standard_price(verify_response, sku)
                    target_price = to_int(row.get("target_price"))

                    if verified_price != target_price:
                        raise RuntimeError(
                            f"PATCH後確認で価格不一致: verified={verified_price}, target={target_price}"
                        )

                response_payload = {
                    "patch_response": patch_response,
                    "verified_price": verified_price,
                    "verify_response": verify_response,
                }

                mark_success(conn, row, verified_price, request_payload, response_payload, retry_policy=args.retry_policy)

                result_summary["success_count"] += 1
                result_summary["items"].append({
                    "index": index,
                    "status": "success",
                    "store_product_id": row.get("store_product_id"),
                    "manageNumber": manage,
                    "variantId": sku,
                    "current_price": row.get("current_price"),
                    "target_price": row.get("target_price"),
                    "verified_price": verified_price,
                    "request": request_payload,
                    "response": patch_response,
                })
                print(f"成功: price {row.get('current_price')} -> {row.get('target_price')}")

            except Exception as e:
                error_message = str(e)
                # Item PATCH/GET 404 by itself is not enough to decide that
                # the listing disappeared: RMS can leave inventory records
                # behind.  Confirm through items.search before disabling it.
                deleted_search_response: dict[str, Any] | None = None
                confirmed_rms_deleted = False
                if is_item_api_not_found(error_message):
                    try:
                        confirmed_rms_deleted, deleted_search_response = confirm_item_absent_in_search(
                            manage,
                            auth_store_code,
                            max_retries=args.retry_count,
                            retry_wait=args.retry_wait,
                        )
                    except Exception as search_error:
                        error_message = f"{error_message} / RMS削除確認に失敗: {search_error}"

                if confirmed_rms_deleted:
                    mark_rms_deleted(
                        conn,
                        row,
                        error_message,
                        request_payload,
                        deleted_search_response or {},
                        retry_policy=args.retry_policy,
                    )
                    result_summary["skipped_count"] += 1
                    result_summary["items"].append({
                        "index": index,
                        "status": "rms_deleted",
                        "store_product_id": row.get("store_product_id"),
                        "manageNumber": manage,
                        "variantId": sku,
                        "current_price": row.get("current_price"),
                        "target_price": row.get("target_price"),
                        "request": request_payload,
                        "error": error_message,
                        "items_search": deleted_search_response,
                    })
                    print("RMS削除済みを確認: DBを無効化しました")
                else:
                    # A failure to persist retry metadata must not terminate the
                    # whole batch.  The next SKU still needs its price check.
                    try:
                        retry_state = mark_failed(conn, row, error_message, request_payload, retry_policy=args.retry_policy)
                    except Exception as retry_error:
                        retry_state = None
                        error_message = f"{error_message} / 失敗状態の保存にも失敗: {retry_error}"

                    result_summary["failed_count"] += 1
                    result_summary["items"].append({
                        "index": index,
                        "status": "failed",
                        "store_product_id": row.get("store_product_id"),
                        "manageNumber": manage,
                        "variantId": sku,
                        "current_price": row.get("current_price"),
                        "target_price": row.get("target_price"),
                        "request": request_payload,
                        "error": error_message,
                        "retry_state": retry_state,
                    })
                    print(f"失敗: {error_message}")
                    if retry_state:
                        retry_at = "保留（手動対応）" if retry_state["retry_delay_seconds"] is None else f"{retry_state['retry_delay_seconds']}秒後"
                        print(
                            "  RETRY_STATE"
                            f" state={retry_state['state']} kind={retry_state['failure_kind']}"
                            f" attempt={retry_state['attempt_count']} next={retry_at}"
                        )

            print("")

            if args.api_interval > 0 and index < len(rows):
                print_wait_log("sleep_rate_limit", "api_interval", args.api_interval)
                print(f"API制限対策: 次の商品まで {args.api_interval:.1f} 秒待機します")
                time.sleep(args.api_interval)
                print("")

    finally:
        conn.close()

    if output_path is None:
        output_path = write_json_file("items_patch_price_execute_result", result_summary)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print("楽天価格更新API 実行完了")
    print_summary(
        total_targets=result_summary["total_targets"],
        success_count=result_summary["success_count"],
        failed_count=result_summary["failed_count"],
        skipped_count=result_summary["skipped_count"],
    )
    print(f"結果JSON保存: {output_path}")

    return 0 if result_summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
