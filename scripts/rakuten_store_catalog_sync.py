import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from db_config import connect_db
from rakuten_auth import build_rakuten_auth_header


ITEM_SEARCH_URL = "https://api.rms.rakuten.co.jp/es/2.0/items/search"
INVENTORY_BULK_GET_URL = "https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-get"
ITEM_SEARCH_HITS = 100
INVENTORY_BATCH_SIZE = 1000
DEFAULT_API_INTERVAL_SECONDS = 1.1
# A catalog sync can run outside the Web Orchestrator process, where the
# per-store UI settings are not available.  Keep the known default here so a
# missing optional SHOP_URL env var does not discard Item API image paths.
DEFAULT_SHOP_SLUGS: dict[str, str] = {
    "rakuten_1": "ecprime500",
}


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"could not decode ASIN map file: {path}")


def load_asin_map(path_text: str) -> dict[str, str]:
    if not path_text.strip():
        return {}
    path = Path(path_text)
    if not path.is_file():
        raise RuntimeError(f"ASIN map file not found: {path}")
    text = read_text_with_fallback(path)
    sample = text[:4096]
    delimiter = "\t" if sample.count("\t") >= sample.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    if not reader.fieldnames:
        raise RuntimeError("ASIN map file has no header")
    normalized = {str(name or "").strip(): name for name in reader.fieldnames}
    manage_column = next((normalized[name] for name in ("楽天商品管理番号", "管理番号", "mall_item_code") if name in normalized), None)
    asin_column = next((normalized[name] for name in ("ASIN", "asin") if name in normalized), None)
    if not manage_column or not asin_column:
        raise RuntimeError("ASIN map file requires 楽天商品管理番号 (or 管理番号) and ASIN columns")
    result: dict[str, str] = {}
    for row in reader:
        manage_number = str(row.get(manage_column) or "").strip()
        asin = str(row.get(asin_column) or "").strip().upper()
        if not manage_number or not asin:
            continue
        previous = result.get(manage_number)
        if previous and previous != asin:
            raise RuntimeError(f"ASIN map has conflicting ASINs for management number: {manage_number}")
        result[manage_number] = asin
    if not result:
        raise RuntimeError("ASIN map file has no usable rows")
    return result


def chunks(values: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def wait_for_interval(last_request_at: float | None, interval_seconds: float) -> float:
    if last_request_at is not None:
        remaining = interval_seconds - (time.monotonic() - last_request_at)
        if remaining > 0:
            time.sleep(remaining)
    return time.monotonic()


def request_json(method: str, url: str, store_code: str, *, params: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.request(
        method,
        url,
        headers=build_rakuten_auth_header(store_code),
        params=params,
        json=payload,
        timeout=90,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:1000]}
    if not response.ok:
        raise RuntimeError(f"RMS API status={response.status_code}: {json.dumps(data, ensure_ascii=False)[:1000]}")
    if not isinstance(data, dict):
        raise RuntimeError("RMS API response is not an object")
    return data


def shop_slug_from_env(store_code: str) -> str:
    import os

    prefix = re.sub(r"[^A-Za-z0-9]+", "_", store_code).strip("_").upper()
    value = str(
        os.getenv(f"{prefix}_SHOP_URL")
        or os.getenv(f"{prefix}_CABINET_SHOP_URL")
        or DEFAULT_SHOP_SLUGS.get(str(store_code or "").strip().lower(), "")
    ).strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.path.strip("/").split("/")[0] if parsed.path.strip("/") else parsed.netloc.split(".")[0]


def image_url(shop_slug: str, image: object) -> tuple[str, str, str]:
    if not isinstance(image, dict):
        return "", "", ""
    location = str(image.get("location") or "").strip()
    image_type = str(image.get("type") or "").strip().upper()
    if not location:
        return "", "", image_type
    if location.startswith(("https://", "http://")):
        return location, location, image_type
    path = location.replace("\\", "/").lstrip("/")
    if not shop_slug:
        return "", path, image_type
    if image_type == "GOLD":
        return f"https://www.rakuten.ne.jp/gold/{shop_slug}/{path}", path, image_type
    return f"https://tshop.r10s.jp/{shop_slug}/cabinet/{path}", path, image_type


def fetch_items(
    store_code: str,
    interval_seconds: float,
    progress_callback: Any | None = None,
) -> tuple[list[dict[str, Any]], int]:
    items: list[dict[str, Any]] = []
    cursor_mark = "*"
    request_count = 0
    last_request_at: float | None = None
    while cursor_mark:
        last_request_at = wait_for_interval(last_request_at, interval_seconds)
        data = request_json(
            "GET",
            ITEM_SEARCH_URL,
            store_code,
            params={
                "cursorMark": cursor_mark,
                "hits": ITEM_SEARCH_HITS,
                "isInventoryIncluded": "true",
            },
        )
        request_count += 1
        results = data.get("results")
        if not isinstance(results, list):
            raise RuntimeError("items.search response does not contain results")
        for result in results:
            item = result.get("item") if isinstance(result, dict) else None
            if isinstance(item, dict):
                items.append(item)
        if progress_callback:
            progress_callback({"phase": "items.search", "request_count": request_count, "rms_item_count": len(items)})
        next_mark = str(data.get("nextCursorMark") or "").strip()
        if not next_mark or next_mark == cursor_mark:
            break
        cursor_mark = next_mark
    return items, request_count


def catalog_rows(items: list[dict[str, Any]], shop_slug: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    inventory_requests: list[dict[str, str]] = []
    for item in items:
        manage_number = str(item.get("manageNumber") or "").strip()
        variants = item.get("variants") if isinstance(item.get("variants"), dict) else {}
        if not manage_number or not variants:
            continue
        images = item.get("images") if isinstance(item.get("images"), list) else []
        main_image_url, main_image_path, main_image_type = image_url(shop_slug, images[0] if images else None)
        title = str(item.get("title") or "").strip()
        hidden = bool(item.get("hideItem"))
        unlimited = bool(item.get("unlimitedInventoryFlag"))
        for variant_id, variant in variants.items():
            sku_code = str(variant_id or "").strip()
            if not sku_code or not isinstance(variant, dict):
                continue
            rows.append(
                {
                    "manage_number": manage_number,
                    "sku_code": sku_code,
                    "item_name": title,
                    "current_price": to_int(variant.get("standardPrice")),
                    "current_stock": None,
                    "status": "warehouse" if hidden else "synced",
                    "enabled": not hidden,
                    "unlimited_inventory": unlimited,
                    "rakuten_image_url": main_image_url,
                    "rakuten_image_path": main_image_path,
                    "rakuten_image_type": main_image_type,
                }
            )
            if not unlimited:
                inventory_requests.append({"manageNumber": manage_number, "variantId": sku_code})
    return rows, inventory_requests


def fetch_inventory(
    store_code: str,
    requests_to_send: list[dict[str, str]],
    interval_seconds: float,
    progress_callback: Any | None = None,
) -> tuple[dict[tuple[str, str], int], int]:
    quantities: dict[tuple[str, str], int] = {}
    request_count = 0
    last_request_at: float | None = None
    for batch in chunks(requests_to_send, INVENTORY_BATCH_SIZE):
        last_request_at = wait_for_interval(last_request_at, interval_seconds)
        data = request_json("POST", INVENTORY_BULK_GET_URL, store_code, payload={"inventories": batch})
        request_count += 1
        inventories = data.get("inventories")
        if not isinstance(inventories, list):
            raise RuntimeError("inventories.bulk-get response does not contain inventories")
        for inventory in inventories:
            if not isinstance(inventory, dict):
                continue
            manage_number = str(inventory.get("manageNumber") or "").strip()
            sku_code = str(inventory.get("variantId") or "").strip()
            quantity = to_int(inventory.get("quantity"))
            if manage_number and sku_code and quantity is not None:
                quantities[(manage_number, sku_code)] = quantity
        if progress_callback:
            progress_callback(
                {
                    "phase": "inventories.bulk-get",
                    "request_count": request_count,
                    "inventory_value_count": len(quantities),
                    "inventory_request_count": len(requests_to_send),
                }
            )
    return quantities, request_count


def store_id_and_existing(conn, store_code: str) -> tuple[int, dict[tuple[str, str], dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE mall = 'rakuten' AND store_code = %s", (store_code,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"store not found: {store_code}")
        store_id = int(row[0])
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'store_products' AND column_name = 'stock_zero_since'
            """
        )
        stock_zero_since_expr = "stock_zero_since" if cur.fetchone() else "NULL::TIMESTAMPTZ"
        cur.execute(
            f"""
            SELECT id, mall_item_code, COALESCE(sku_code, ''), asin, {stock_zero_since_expr}
            FROM store_products
            WHERE store_id = %s
            """,
            (store_id,),
        )
        existing = {
            (str(manage or ""), str(sku or "")): {
                "id": int(product_id),
                "asin": str(asin or "").strip(),
                "stock_zero_since": stock_zero_since,
            }
            for product_id, manage, sku, asin, stock_zero_since in cur.fetchall()
        }
    return store_id, existing


def apply_rows(
    conn,
    store_code: str,
    rows: list[dict[str, Any]],
    *,
    replace_store_products: bool,
    asin_map: dict[str, str],
) -> dict[str, int]:
    store_id, existing = store_id_and_existing(conn, store_code)
    updated = 0
    inserted = 0
    deleted = 0
    restored_asin = 0
    with conn.cursor() as cur:
        # store_products.asin is a foreign key to amazon_products.  The RMS
        # export can contain ASINs which have not yet been checked by an
        # Amazon worker, so create a minimal parent record first.  Keep this
        # in the same transaction as the replacement: a later failure leaves
        # the current store catalog untouched.
        mapped_asins = sorted(
            {
                str(
                    asin_map.get(row["manage_number"], "")
                    or (existing.get((row["manage_number"], row["sku_code"])) or {}).get("asin")
                    or ""
                )
                .strip()
                .upper()
                for row in rows
            }
            - {""}
        )
        if mapped_asins:
            cur.executemany(
                """
                INSERT INTO amazon_products (asin, created_at, updated_at)
                VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (asin) DO NOTHING
                """,
                [(asin,) for asin in mapped_asins],
            )
        if replace_store_products:
            cur.execute("DELETE FROM store_products WHERE store_id = %s", (store_id,))
            deleted = int(cur.rowcount or 0)
        for row in rows:
            key = (row["manage_number"], row["sku_code"])
            stock = row["current_stock"]
            common = (
                row["item_name"],
                row["current_price"],
                stock,
                row["status"],
                row["enabled"],
                row["rakuten_image_url"],
                row["rakuten_image_path"],
                row["rakuten_image_type"],
            )
            previous = existing.get(key)
            product_id = previous.get("id") if previous else None
            if product_id is not None and not replace_store_products:
                cur.execute(
                    """
                    UPDATE store_products
                    SET item_name = %s,
                        current_price = COALESCE(%s, current_price),
                        current_stock = CASE WHEN %s IS NULL THEN current_stock ELSE %s END,
                        current_status = %s,
                        enabled = %s,
                        rakuten_image_url = COALESCE(NULLIF(%s, ''), rakuten_image_url),
                        rakuten_image_path = COALESCE(NULLIF(%s, ''), rakuten_image_path),
                        rakuten_image_type = COALESCE(NULLIF(%s, ''), rakuten_image_type),
                        api_last_synced_at = CURRENT_TIMESTAMP,
                        api_last_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (*common[:2], stock, stock, *common[3:], product_id),
                )
                updated += 1
                continue
            asin = asin_map.get(row["manage_number"], "") or (str(previous.get("asin") or "").strip() if previous else "")
            stock_zero_since = previous.get("stock_zero_since") if previous and stock == 0 else None
            if asin:
                restored_asin += 1
            cur.execute(
                """
                INSERT INTO store_products (
                    store_id, asin, mall_item_code, sku_code, current_price, current_stock,
                    current_status, enabled, force_stop, item_name, rakuten_image_url,
                    rakuten_image_path, rakuten_image_type, stock_zero_since, api_last_synced_at, created_at, updated_at
                )
                VALUES (%s, NULLIF(%s, ''), %s, %s, %s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    store_id,
                    asin,
                    row["manage_number"],
                    row["sku_code"],
                    row["current_price"],
                    stock,
                    row["status"],
                    row["enabled"],
                    row["item_name"],
                    row["rakuten_image_url"],
                    row["rakuten_image_path"],
                    row["rakuten_image_type"],
                    stock_zero_since,
                ),
            )
            inserted += 1
    conn.commit()
    return {
        "updated_count": updated,
        "inserted_count": inserted,
        "deleted_store_product_count": deleted,
        "restored_asin_mapping_count": restored_asin,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RMSの現在商品一覧を店舗単位でDBへ安全に同期します。")
    parser.add_argument("--store", required=True, help="stores.store_code")
    parser.add_argument("--asin-map-file", default="", help="楽天商品管理番号とASINのTSV/CSV。再構築時に最優先でASINを復元する")
    parser.add_argument("--execute", action="store_true", help="確認済みのRMS結果をDBへ反映する")
    parser.add_argument(
        "--replace-store-products",
        action="store_true",
        help="指定店舗のstore_productsを全消去してRMSの現行商品一覧から再作成する（--execute必須）",
    )
    parser.add_argument("--output", required=True, help="結果JSONの保存先")
    parser.add_argument("--api-interval", type=float, default=DEFAULT_API_INTERVAL_SECONDS)
    args = parser.parse_args()
    if args.api_interval < 1:
        raise RuntimeError("--api-interval must be at least 1 second")
    if args.replace_store_products and not args.execute:
        raise RuntimeError("--replace-store-products requires --execute")

    store_code = args.store.strip().lower()
    asin_map = load_asin_map(args.asin_map_file)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path = output_path.with_suffix(output_path.suffix + ".progress.json")
    started_at = datetime.now().isoformat(timespec="seconds")
    def record_progress(detail: dict[str, Any]) -> None:
        progress_path.write_text(
            json.dumps({"store": store_code, "started_at": started_at, "updated_at": datetime.now().isoformat(timespec="seconds"), **detail}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    record_progress({"phase": "started"})
    try:
        items, item_request_count = fetch_items(store_code, args.api_interval, record_progress)
        rows, inventory_requests = catalog_rows(items, shop_slug_from_env(store_code))
        record_progress({"phase": "catalog_normalized", "rms_item_count": len(items), "rms_sku_count": len(rows)})
        quantities, inventory_request_count = fetch_inventory(store_code, inventory_requests, args.api_interval, record_progress)
        for row in rows:
            row["current_stock"] = quantities.get((row["manage_number"], row["sku_code"]))

        with connect_db() as conn:
            store_id, existing = store_id_and_existing(conn, store_code)
            existing_keys = set(existing)
            live_keys = {(row["manage_number"], row["sku_code"]) for row in rows}
            result = {
                "store": store_code,
                "store_id": store_id,
                "started_at": started_at,
                "completed_at": datetime.now().isoformat(timespec="seconds"),
                "execute": bool(args.execute),
                "rms_item_count": len(items),
                "rms_sku_count": len(rows),
                "asin_map_manage_number_count": len(asin_map),
                "rms_manage_number_missing_from_asin_map_count": len({row["manage_number"] for row in rows} - set(asin_map)),
                "item_search_request_count": item_request_count,
                "inventory_bulk_request_count": inventory_request_count,
                "inventory_value_count": len(quantities),
                "existing_db_row_count": len(existing_keys),
                "matched_db_row_count": len(existing_keys & live_keys),
                "new_rms_row_count": len(live_keys - existing_keys),
                "db_only_row_count": len(existing_keys - live_keys),
                "replace_store_products": bool(args.replace_store_products),
                "note": (
                    "RMS検索の反映遅延による誤停止を避けるため、通常同期はDBのみの行を削除しません。"
                    if not args.replace_store_products
                    else "指定店舗のstore_productsを全消去し、RMS検索結果から再作成します。管理番号+SKUが一致するASINのみ復元します。"
                ),
            }
            if args.execute:
                record_progress({"phase": "replacing_store_products", "rms_sku_count": len(rows)})
                result.update(
                    apply_rows(
                        conn,
                        store_code,
                        rows,
                        replace_store_products=bool(args.replace_store_products),
                        asin_map=asin_map,
                    )
                )
    except Exception as exc:
        failure = {"store": store_code, "started_at": started_at, "failed_at": datetime.now().isoformat(timespec="seconds"), "error": str(exc)}
        output_path.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        record_progress({"phase": "failed", "error": str(exc)})
        raise
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    record_progress({"phase": "completed", **result})
    print(json.dumps(result, ensure_ascii=False))
    print(f"RAKUTEN_STORE_CATALOG_SYNC_RESULT={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
