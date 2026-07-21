import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from db_config import connect_db
from scripts.listing.rakuten_transport import build_rakuten_auth_headers
from psycopg.types.json import Jsonb


BASE_DIR = Path(__file__).resolve().parents[1]
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


def load_auth_header(store_code: str) -> dict[str, str]:
    return build_rakuten_auth_headers(store_code=store_code)


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
        LIMIT %s;
    """
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


def resolve_chunk_store_code(chunk_rows: list[dict[str, Any]], explicit_store_code: str | None) -> str:
    explicit = str(explicit_store_code or "").strip()
    if explicit:
        return explicit
    row_store_codes = {
        str(row.get("store_code") or "").strip()
        for row in chunk_rows
        if str(row.get("store_code") or "").strip()
    }
    if len(row_store_codes) == 1:
        return next(iter(row_store_codes))
    if len(row_store_codes) > 1:
        raise RuntimeError("multiple Rakuten stores found in one inventory batch. Specify --store explicitly")
    raise RuntimeError("store_code is empty")


# =========================
# 楽天API実行
# =========================

def call_inventory_bulk_upsert(payload: dict[str, Any], store_code: str) -> dict[str, Any]:
    headers = load_auth_header(store_code)

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


# =========================
# main
# =========================

def main() -> int:
    parser = argparse.ArgumentParser(description="楽天在庫API bulk-upsert 用のdry-run/実更新を行います。")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code。空文字なら楽天全店舗")
    parser.add_argument("--limit", type=int, default=10, help="対象最大件数")
    parser.add_argument("--batch-size", type=int, default=100, help="bulk-upsert 1回あたりの最大件数")
    parser.add_argument("--output", default="", help="送信予定JSON/結果JSONの保存先。空なら自動")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="API送信せずJSONだけ出力する")
    mode.add_argument("--execute", action="store_true", help="楽天APIへ実更新する")

    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit は 1以上にしてください。")
        return 2

    if args.batch_size <= 0:
        print("--batch-size は 1以上にしてください。")
        return 2

    store_code = args.store.strip() or None
    dry_run = not args.execute

    rows = fetch_inventory_targets(store_code=store_code, limit=args.limit)
    print_targets(rows)
    print(f"楽天在庫更新対象件数: {len(rows)}")

    if not rows:
        return 0

    # payload作成時点で target_stock マイナスなどを検出する。
    try:
        all_payload = build_payload(rows)
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
        "total_targets": len(rows),
        "batch_size": args.batch_size,
        "success_count": 0,
        "failed_count": 0,
        "batches": [],
    }

    conn = connect_db()
    try:
        chunks = split_chunks(rows, args.batch_size)

        for index, chunk_rows in enumerate(chunks, start=1):
            print(f"===== batch {index}/{len(chunks)} 件数={len(chunk_rows)} =====")
            request_payload = build_payload(chunk_rows)

            try:
                response_payload = call_inventory_bulk_upsert(request_payload, resolve_chunk_store_code(chunk_rows, store_code))
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
