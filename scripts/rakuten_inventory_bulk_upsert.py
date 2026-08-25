import argparse
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from db_config import connect_db
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from rakuten_auth import build_rakuten_auth_header, resolve_rakuten_store_code


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR.parent / ".env"
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_api"

RAKUTEN_INVENTORY_BULK_UPSERT_URL = (
    "https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-upsert"
)


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


# =========================
# DB取得
# =========================

def fetch_inventory_targets(store_code: str | None, limit: int) -> list[dict[str, Any]]:
    where = [
        "s.mall = 'rakuten'",
        "sp.enabled = TRUE",
        "sp.target_stock IS NOT NULL",
        "COALESCE(sp.current_stock, -999999) <> sp.target_stock",
        "sp.mall_item_code IS NOT NULL",
        "sp.mall_item_code <> ''",
    ]
    params: list[Any] = []

    if store_code:
        where.append("s.store_code = %s")
        params.append(store_code)

    sql = f"""
        SELECT
            s.id AS store_id,
            s.store_code,
            s.max_stock,
            sp.id AS store_product_id,
            sp.asin,
            sp.mall_item_code,
            COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) AS sku_code,
            sp.current_price,
            sp.target_price,
            sp.current_stock,
            sp.target_stock,
            sp.force_stop,
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
    """
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


def fetch_inventory_zero_target(store_code: str, asin: str) -> list[dict[str, Any]]:
    """Return one explicit manual zero-stock target without changing its price."""
    sql = """
        SELECT
            s.id AS store_id,
            s.store_code,
            s.max_stock,
            sp.id AS store_product_id,
            sp.asin,
            sp.mall_item_code,
            COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) AS sku_code,
            sp.current_price,
            sp.target_price,
            sp.current_stock,
            0 AS target_stock,
            sp.force_stop,
            ap.amazon_price,
            ap.amazon_point,
            ap.available_qty,
            ap.business_ng,
            ap.system_error,
            ap.ng_reason,
            ap.checked_at,
            TRUE AS force_zero
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        LEFT JOIN amazon_products ap ON ap.asin = sp.asin
        WHERE s.mall = 'rakuten'
          AND s.store_code = %s
          AND UPPER(sp.asin) = UPPER(%s)
          AND sp.enabled = TRUE
          AND COALESCE(sp.mall_item_code, '') <> ''
        ORDER BY sp.updated_at DESC NULLS LAST
        LIMIT 1
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (store_code, asin))
            rows = cur.fetchall()
            col_names = [desc.name for desc in cur.description]
            return [dict(zip(col_names, row)) for row in rows]
    finally:
        conn.close()


def validate_target_stock_for_store(row: dict[str, Any]) -> str | None:
    store_code = str(row.get("store_code") or "").strip()
    asin = str(row.get("asin") or "").strip()
    manage_number = str(row.get("mall_item_code") or "").strip()
    target_stock = to_int(row.get("target_stock"))
    max_stock = to_int(row.get("max_stock"))

    if max_stock is None:
        return (
            f"SKIP store_code={store_code} ASIN={asin} manageNumber={manage_number} "
            f"target_stock={target_stock} max_stock={max_stock} "
            f"skip_reason=max_stock_missing"
        )

    if max_stock < 0:
        return (
            f"SKIP store_code={store_code} ASIN={asin} manageNumber={manage_number} "
            f"target_stock={target_stock} max_stock={max_stock} "
            f"skip_reason=max_stock_invalid"
        )

    if target_stock is None:
        return (
            f"SKIP store_code={store_code} ASIN={asin} manageNumber={manage_number} "
            f"target_stock={target_stock} max_stock={max_stock} "
            f"skip_reason=target_stock_missing"
        )

    if target_stock > max_stock:
        return (
            f"SKIP store_code={store_code} ASIN={asin} manageNumber={manage_number} "
            f"target_stock={target_stock} max_stock={max_stock} "
            f"skip_reason=target_stock_exceeds_max_stock"
        )

    return None


def split_safe_and_skipped_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    safe_rows: list[dict[str, Any]] = []
    skipped_rows: list[tuple[dict[str, Any], str]] = []

    for row in rows:
        skip_reason = validate_target_stock_for_store(row)
        if skip_reason:
            skipped_rows.append((row, skip_reason))
        else:
            safe_rows.append(row)

    return safe_rows, skipped_rows


# =========================
# 楽天API payload
# =========================

def build_inventory_row(row: dict[str, Any]) -> dict[str, Any]:
    manage_number = str(row.get("mall_item_code") or "").strip()
    sku_code = str(row.get("sku_code") or manage_number).strip()
    target_stock = to_int(row.get("target_stock"), 0)

    if not manage_number:
        raise ValueError("mall_item_code が空です")

    if not sku_code:
        raise ValueError("sku_code が空です")

    if target_stock is None:
        raise ValueError("target_stock が空です")

    if target_stock < 0:
        raise ValueError(f"target_stock がマイナスです: {target_stock}")

    return {
        "manageNumber": manage_number,
        "variantId": sku_code,
        "mode": "ABSOLUTE",
        "quantity": target_stock,
    }


def build_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "inventories": [build_inventory_row(row) for row in rows]
    }


def split_chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[i:i + size] for i in range(0, len(rows), size)]


# =========================
# 楽天API実行
# =========================

def call_inventory_bulk_upsert(payload: dict[str, Any], store_code: str) -> dict[str, Any]:
    headers = build_rakuten_auth_header(store_code)

    print(f"POST {RAKUTEN_INVENTORY_BULK_UPSERT_URL}")
    print(f"inventories={len(payload.get('inventories') or [])}")

    res = requests.post(
        RAKUTEN_INVENTORY_BULK_UPSERT_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    print(f"status_code={res.status_code}")

    try:
        data = res.json() if res.text else {}
    except Exception:
        data = {"_raw_text": res.text}

    if not (200 <= res.status_code < 300):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        raise RuntimeError(f"楽天在庫更新APIエラー status={res.status_code}: {data}")

    return data


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


def update_success(cur, row: dict[str, Any]) -> None:
    if row.get("force_zero"):
        cur.execute(
            """
            UPDATE store_products
            SET
                current_stock = 0,
                target_stock = 0,
                current_status = 'synced',
                api_last_synced_at = CURRENT_TIMESTAMP,
                api_last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (row["store_product_id"],),
        )
        return
    cur.execute(
        """
        UPDATE store_products
        SET
            current_stock = target_stock,
            current_status = 'synced',
            api_last_synced_at = CURRENT_TIMESTAMP,
            api_last_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (row["store_product_id"],),
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
    ログ失敗で本体更新まで巻き戻さないよう、呼び出し側で savepoint 内から使う。
    """
    columns = get_table_columns(cur, "price_update_logs")
    if not columns:
        return

    candidates: dict[str, Any] = {
        "store_product_id": row.get("store_product_id"),
        "store_id": row.get("store_id"),
        "store_code": row.get("store_code"),
        "asin": row.get("asin"),
        "mall_item_code": row.get("mall_item_code"),
        "sku_code": row.get("sku_code"),
        "api_name": "inventories.bulk.upsert",
        "update_type": "stock",
        "update_kind": "stock",
        "kind": "stock",
        "type": "stock",
        "old_price": row.get("current_price"),
        "current_price": row.get("current_price"),
        "new_price": row.get("target_price"),
        "target_price": row.get("target_price"),
        "old_stock": row.get("current_stock"),
        "current_stock": row.get("current_stock"),
        "new_stock": row.get("target_stock"),
        "target_stock": row.get("target_stock"),
        "quantity": row.get("target_stock"),
        "status": status,
        "result": status,
        "message": message[:2000],
        "error_message": message[:2000] if status != "success" else None,
        "request_url": RAKUTEN_INVENTORY_BULK_UPSERT_URL,
        "url": RAKUTEN_INVENTORY_BULK_UPSERT_URL,
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
        # 既存トランザクション内なら savepoint になる。
        # ログだけ失敗しても、在庫反映を巻き込まない。
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


def mark_rows_success(conn, rows: list[dict[str, Any]], request_payload: dict[str, Any], response_payload: dict[str, Any]) -> None:
    for row in rows:
        with conn.transaction():
            with conn.cursor() as cur:
                update_success(cur, row)
            save_log_best_effort(
                conn,
                row=row,
                status="success",
                message="在庫更新成功",
                request_payload=request_payload,
                response_payload=response_payload,
            )


def mark_rows_failed(conn, rows: list[dict[str, Any]], error_message: str, request_payload: dict[str, Any]) -> None:
    for row in rows:
        with conn.transaction():
            with conn.cursor() as cur:
                update_failed(cur, row, error_message)
            save_log_best_effort(
                conn,
                row=row,
                status="failed",
                message=error_message,
                request_payload=request_payload,
                response_payload=None,
            )


# =========================
# 表示
# =========================

def print_targets(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("楽天在庫更新対象はありません。")
        return

    print("")
    print("===== 楽天在庫更新対象 =====")
    print("")

    for row in rows:
        print(
            f"[{row.get('store_code')}] "
            f"id={row.get('store_product_id')} "
            f"ASIN={row.get('asin') or ''} "
            f"manageNumber={row.get('mall_item_code') or ''} "
            f"variantId={row.get('sku_code') or ''}"
        )
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


def print_skipped_rows(skipped_rows: list[tuple[dict[str, Any], str]]) -> None:
    if not skipped_rows:
        return

    print("")
    print("===== skipped inventory targets =====")
    print("")

    for _, skip_reason in skipped_rows:
        print(skip_reason)

    print("")


# =========================
# main
# =========================

def main() -> int:
    parser = argparse.ArgumentParser(description="楽天在庫API bulk-upsert 用のdry-run/実更新を行います。")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code。空文字なら楽天全店舗")
    parser.add_argument("--limit", type=int, default=10, help="対象最大件数。0は全件")
    parser.add_argument("--batch-size", type=int, default=400, help="bulk-upsert 1回あたりの最大件数（楽天API上限: 400）")
    parser.add_argument("--output", default="", help="送信予定JSON/結果JSONの保存先。空なら自動")
    parser.add_argument("--asin", default="", help="指定ASINだけを対象にします（--force-zeroと組み合わせ）")
    parser.add_argument("--force-zero", action="store_true", help="指定ASINのRMS在庫とDB目標在庫を0にします")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="API送信せずJSONだけ出力する")
    mode.add_argument("--execute", action="store_true", help="楽天APIへ実更新する")

    args = parser.parse_args()

    if args.limit < 0:
        print("--limit は 0以上にしてください。0は全件です。")
        return 2

    if args.batch_size <= 0:
        print("--batch-size は 1以上にしてください。")
        return 2

    if args.force_zero and not args.asin.strip():
        print("--force-zero には --asin が必要です。")
        return 2
    if args.asin.strip() and not args.force_zero:
        print("--asin は --force-zero と組み合わせてください。")
        return 2

    store_code = args.store.strip() or None
    dry_run = not args.execute

    if args.force_zero:
        if not store_code:
            print("--force-zero には --store が必要です。")
            return 2
        rows = fetch_inventory_zero_target(store_code=store_code, asin=args.asin.strip().upper())
    else:
        rows = fetch_inventory_targets(store_code=store_code, limit=args.limit)
    safe_rows, skipped_rows = split_safe_and_skipped_rows(rows)

    print_targets(safe_rows)
    print_skipped_rows(skipped_rows)
    print(f"inventory_target_count: {len(safe_rows)}")
    if args.force_zero:
        print("manual_stock_zero: true")
    if skipped_rows:
        print(f"inventory_skipped_count: {len(skipped_rows)}")

    if not safe_rows:
        return 0

    # payload作成時点で target_stock マイナスなどを検出する。
    try:
        all_payload = build_payload(safe_rows)
    except Exception as e:
        print(f"送信予定JSON作成エラー: {e}")
        return 1

    output_path = Path(args.output) if args.output else None

    if dry_run:
        if output_path is None:
            output_path = write_json_file("inventories_bulk_upsert_dry_run", all_payload)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(all_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print("")
        print("dry-run のため楽天APIへは送信しません。")
        print(f"送信予定JSON保存: {output_path}")
        return 0

    print("")
    print("実更新モードです。楽天APIへ送信します。")
    print("価格は更新しません。在庫数のみ ABSOLUTE で更新します。")
    print("")

    result_summary = {
        "request_url": RAKUTEN_INVENTORY_BULK_UPSERT_URL,
        "executed_at": datetime.now().isoformat(timespec="seconds"),
        "total_targets": len(safe_rows),
        "skipped_count": len(skipped_rows),
        "batch_size": args.batch_size,
        "success_count": 0,
        "failed_count": 0,
        "batches": [],
    }

    conn = connect_db()
    try:
        auth_store_code = resolve_rakuten_store_code(store_code, safe_rows)
        chunks = split_chunks(safe_rows, args.batch_size)

        for index, chunk_rows in enumerate(chunks, start=1):
            print(f"===== batch {index}/{len(chunks)} 件数={len(chunk_rows)} =====")
            request_payload = build_payload(chunk_rows)

            try:
                response_payload = call_inventory_bulk_upsert(request_payload, auth_store_code)
                mark_rows_success(conn, chunk_rows, request_payload, response_payload)

                result_summary["success_count"] += len(chunk_rows)
                result_summary["batches"].append({
                    "batch": index,
                    "status": "success",
                    "count": len(chunk_rows),
                    "request": request_payload,
                    "response": response_payload,
                })
                print(f"batch {index}: 成功")

            except Exception as e:
                error_message = str(e)
                mark_rows_failed(conn, chunk_rows, error_message, request_payload)

                result_summary["failed_count"] += len(chunk_rows)
                result_summary["batches"].append({
                    "batch": index,
                    "status": "failed",
                    "count": len(chunk_rows),
                    "request": request_payload,
                    "error": error_message,
                })
                print(f"batch {index}: 失敗 {error_message}")

    finally:
        conn.close()

    if output_path is None:
        output_path = write_json_file("inventories_bulk_upsert_execute_result", result_summary)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print("楽天在庫更新API 実行完了")
    print(f"成功件数: {result_summary['success_count']}")
    print(f"失敗件数: {result_summary['failed_count']}")
    print(f"結果JSON保存: {output_path}")

    return 0 if result_summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
