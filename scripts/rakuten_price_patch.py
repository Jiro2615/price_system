import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from db_config import connect_db
from scripts.listing.rakuten_transport import build_rakuten_auth_headers
from psycopg.types.json import Jsonb


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_api"

RAKUTEN_ITEM_BASE_URL = "https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers"


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


def item_url(manage_number: str) -> str:
    encoded = quote(str(manage_number), safe="")
    return f"{RAKUTEN_ITEM_BASE_URL}/{encoded}"


# =========================
# DB取得
# =========================

def fetch_price_targets(
    store_code: str | None,
    limit: int,
    manage_number: str | None = None,
    sku_code: str | None = None,
    blocked_only: bool = False,
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
    headers = load_auth_header(store_code)
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
            print(f"  {api_label}: status={res.status_code} のため {wait_sec:.1f} 秒待って再試行します ({attempt}/{max_retries})")
            time.sleep(wait_sec)
            continue

        print(json.dumps(data, ensure_ascii=False, indent=2))
        raise RuntimeError(f"{api_label}エラー status={res.status_code}: {data}")

    raise RuntimeError(f"{api_label}エラー: retry exhausted")


def call_item_patch(
    manage_number: str,
    payload: dict[str, Any],
    store_code: str,
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


def mark_success(conn, row: dict[str, Any], verified_price: int | None, request_payload: dict[str, Any], response_payload: dict[str, Any]) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            update_success(cur, row, verified_price)
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


def mark_failed(conn, row: dict[str, Any], error_message: str, request_payload: dict[str, Any] | None) -> None:
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
    parser.add_argument("--limit", type=int, default=10, help="対象最大件数")
    parser.add_argument("--manage-number", default="", help="特定の商品管理番号だけに絞る")
    parser.add_argument("--sku", default="", help="特定のSKUだけに絞る")
    parser.add_argument("--blocked-only", action="store_true", help="rakuten_csv_update_blocked = TRUE の商品のみ対象にする")
    parser.add_argument("--output", default="", help="送信予定JSON/結果JSONの保存先。空なら自動")
    parser.add_argument("--max-change-rate", type=float, default=0.50, help="実更新時に許可する最大価格変更率。0.50=50%%。0なら無制限")
    parser.add_argument("--allow-large-change", action="store_true", help="価格変更率チェックを無視して実更新する")
    parser.add_argument("--allow-current-price-null", action="store_true", help="current_price がNULLでも実更新する")
    parser.add_argument("--no-verify", action="store_true", help="PATCH後のitems.get確認を省略する")
    parser.add_argument("--api-interval", type=float, default=1.5, help="1商品処理ごとに待つ秒数。楽天APIのQPS制限対策")
    parser.add_argument("--verify-wait", type=float, default=1.5, help="PATCH成功後、items.get確認前に待つ秒数")
    parser.add_argument("--retry-count", type=int, default=5, help="429/一時エラー時の再試行回数")
    parser.add_argument("--retry-wait", type=float, default=5.0, help="429/一時エラー時の基本待機秒数。再試行ごとに少し伸ばす")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="API送信せずJSONだけ出力する")
    mode.add_argument("--execute", action="store_true", help="楽天APIへ実更新する")

    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit は 1以上にしてください。")
        return 2

    store_code = args.store.strip() or None
    manage_number = args.manage_number.strip() or None
    sku_code = args.sku.strip() or None
    dry_run = not args.execute

    rows = fetch_price_targets(
        store_code=store_code,
        limit=args.limit,
        manage_number=manage_number,
        sku_code=sku_code,
        blocked_only=args.blocked_only,
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
    print(f"PATCH後確認: {'しない' if args.no_verify else 'items.getで確認する'}")
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
                    request_payload,
                    store_code=str(row.get("store_code") or store_code or ""),
                    max_retries=args.retry_count,
                    retry_wait=args.retry_wait,
                )

                verified_price: int | None = None
                verify_response: dict[str, Any] | None = None

                if not args.no_verify:
                    if args.verify_wait > 0:
                        print(f"  PATCH後確認前に {args.verify_wait:.1f} 秒待機します")
                        time.sleep(args.verify_wait)

                    verify_response = call_item_get(
                        manage,
                        store_code=str(row.get("store_code") or store_code or ""),
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

                mark_success(conn, row, verified_price, request_payload, response_payload)

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
                mark_failed(conn, row, error_message, request_payload)

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
                })
                print(f"失敗: {error_message}")

            print("")

            if args.api_interval > 0 and index < len(rows):
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
