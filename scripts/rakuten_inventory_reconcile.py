"""Read Rakuten RMS inventory and refresh DB current_stock in small batches.

This is deliberately separate from inventories.bulk.upsert: it is a read-side
reconciliation for sales, cancellations, or manual RMS edits. Once current_stock
is refreshed, the normal inventory updater decides whether target_stock should be
sent back to RMS.
"""

from __future__ import annotations

import argparse
from urllib.parse import quote

import requests

from db_config import connect_db
from rakuten_auth import build_rakuten_auth_header


def fetch_targets(cur, store_code: str, limit: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            sp.id,
            sp.mall_item_code,
            sp.sku_code,
            sp.current_stock,
            sp.target_stock
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        WHERE s.mall = 'rakuten'
          AND s.store_code = %s
          AND COALESCE(sp.mall_item_code, '') <> ''
          AND COALESCE(sp.sku_code, '') <> ''
        ORDER BY sp.rms_inventory_checked_at NULLS FIRST, sp.id
        LIMIT %s
        """,
        (store_code, limit),
    )
    columns = [description.name for description in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_rms_quantity(headers: dict[str, str], manage_number: str, sku_code: str) -> int:
    url = (
        "https://api.rms.rakuten.co.jp/es/2.1/"
        f"inventories/manage-numbers/{quote(manage_number, safe='')}/variants/{quote(sku_code, safe='')}"
    )
    response = requests.get(url, headers=headers, timeout=60)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:500]}
    response.raise_for_status()
    value = payload.get("quantity")
    if value is None or value == "":
        raise ValueError("RMS inventory response did not contain quantity")
    return int(float(str(value)))


def save_success(cur, product_id: int, quantity: int) -> None:
    cur.execute(
        """
        UPDATE store_products
        SET current_stock = %s,
            current_status = 'rms_reconciled',
            rms_inventory_checked_at = CURRENT_TIMESTAMP,
            rms_inventory_last_error = '',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (quantity, product_id),
    )


def save_error(cur, product_id: int, message: str) -> None:
    cur.execute(
        """
        UPDATE store_products
        SET rms_inventory_checked_at = CURRENT_TIMESTAMP,
            rms_inventory_last_error = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (message[:1000], product_id),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile Rakuten RMS inventory into DB current_stock")
    parser.add_argument("--store", default="rakuten_2")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--execute", action="store_true", help="persist the fetched RMS quantities to DB")
    args = parser.parse_args()

    store_code = args.store.strip().lower()
    if not store_code:
        raise SystemExit("store is required")
    if not 1 <= args.limit <= 400:
        raise SystemExit("limit must be between 1 and 400")

    conn = connect_db()
    checked = 0
    changed = 0
    failed = 0
    try:
        with conn.cursor() as cur:
            targets = fetch_targets(cur, store_code, args.limit)
        headers = build_rakuten_auth_header(store_code)
        for product in targets:
            checked += 1
            try:
                rms_quantity = fetch_rms_quantity(headers, product["mall_item_code"], product["sku_code"])
                is_changed = product["current_stock"] != rms_quantity
                changed += 1 if is_changed else 0
                print(
                    f"[inventory-reconcile] id={product['id']} "
                    f"stock={product['current_stock']}->{rms_quantity} changed={is_changed}",
                    flush=True,
                )
                if args.execute:
                    with conn.cursor() as cur:
                        save_success(cur, int(product["id"]), rms_quantity)
                    conn.commit()
            except Exception as exc:
                failed += 1
                print(f"[inventory-reconcile] id={product['id']} failed: {exc}", flush=True)
                if args.execute:
                    with conn.cursor() as cur:
                        save_error(cur, int(product["id"]), str(exc))
                    conn.commit()
    finally:
        conn.close()

    print(
        f"[inventory-reconcile] store={store_code} checked={checked} changed={changed} "
        f"failed={failed} execute={args.execute}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
