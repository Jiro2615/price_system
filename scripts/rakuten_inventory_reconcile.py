"""Read Rakuten RMS inventory and refresh DB current_stock in small batches.

This is deliberately separate from inventories.bulk.upsert: it is a read-side
reconciliation for sales, cancellations, or manual RMS edits. Once current_stock
is refreshed, the normal inventory updater decides whether target_stock should be
sent back to RMS.
"""

from __future__ import annotations

import argparse
import time
from urllib.parse import quote

import requests

from db_config import connect_db
from rakuten_auth import build_rakuten_auth_header


class RmsInventoryNotFoundError(RuntimeError):
    """Raised when the RMS inventory endpoint returns HTTP 404."""


RMS_INVENTORY_404_PENDING_PREFIX = "RMS inventory 404 pending confirmation:"


def fetch_targets(cur, store_code: str, limit: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            sp.id,
            sp.mall_item_code,
            sp.sku_code,
            sp.current_stock,
            sp.target_stock,
            sp.rms_inventory_last_error
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        WHERE s.mall = 'rakuten'
          AND s.store_code = %s
          AND sp.enabled = TRUE
          AND COALESCE(sp.force_stop, FALSE) = FALSE
          AND COALESCE(sp.mall_item_code, '') <> ''
          AND COALESCE(sp.sku_code, '') <> ''
        ORDER BY sp.rms_inventory_checked_at NULLS FIRST, sp.id
        LIMIT %s
        """,
        (store_code, limit),
    )
    columns = [description.name for description in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def retry_wait_seconds(response: requests.Response | None, fallback_seconds: float, attempt: int) -> float:
    """Prefer the server-provided rate-limit wait, then use capped backoff."""
    retry_after = ""
    if response is not None:
        retry_after = str(response.headers.get("Retry-After") or "").strip()
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(60.0, max(0.0, fallback_seconds) * (2 ** attempt))


def fetch_rms_quantity(
    headers: dict[str, str],
    manage_number: str,
    sku_code: str,
    *,
    retry_count: int,
    retry_wait: float,
    timeout: float,
) -> int:
    url = (
        "https://api.rms.rakuten.co.jp/es/2.1/"
        f"inventories/manage-numbers/{quote(manage_number, safe='')}/variants/{quote(sku_code, safe='')}"
    )
    for attempt in range(retry_count + 1):
        response: requests.Response | None = None
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            try:
                payload = response.json()
            except ValueError:
                payload = {"raw": response.text[:500]}

            retryable_status = response.status_code == 429 or 500 <= response.status_code < 600
            if retryable_status and attempt < retry_count:
                wait_seconds = retry_wait_seconds(response, retry_wait, attempt)
                print(
                    f"[inventory-reconcile] RMS status={response.status_code}; "
                    f"retry {attempt + 1}/{retry_count} after {wait_seconds:g}s",
                    flush=True,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code == 404:
                raise RmsInventoryNotFoundError(
                    f"RMS item not found (404): manageNumber={manage_number}, variantId={sku_code}"
                )

            response.raise_for_status()
            value = payload.get("quantity")
            if value is None or value == "":
                raise ValueError("RMS inventory response did not contain quantity")
            return int(float(str(value)))
        except requests.RequestException as exc:
            if attempt >= retry_count:
                raise
            wait_seconds = retry_wait_seconds(response, retry_wait, attempt)
            print(
                f"[inventory-reconcile] RMS request error={exc}; "
                f"retry {attempt + 1}/{retry_count} after {wait_seconds:g}s",
                flush=True,
            )
            time.sleep(wait_seconds)

    raise RuntimeError("RMS inventory retry loop ended unexpectedly")


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
        SET rms_inventory_last_error = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (message[:1000], product_id),
    )


def save_rms_deleted(cur, product_id: int, message: str) -> None:
    """Disable a DB row after two independent RMS inventory 404 responses."""
    cur.execute(
        """
        UPDATE store_products
        SET enabled = FALSE,
            force_stop = TRUE,
            current_status = 'rms_deleted',
            rms_inventory_checked_at = CURRENT_TIMESTAMP,
            rms_inventory_last_error = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (message[:1000], product_id),
    )


def save_rms_inventory_404_pending(cur, product_id: int, message: str) -> None:
    """Remember one 404 without disabling a potentially live RMS item.

    The first 404 is not retried in this run.  Because RMS may transiently
    return 404 while the item is still reachable later, the next full cycle
    must independently see the same response before ``save_rms_deleted`` is
    allowed to disable the record.
    """
    cur.execute(
        """
        UPDATE store_products
        SET rms_inventory_checked_at = CURRENT_TIMESTAMP,
            rms_inventory_last_error = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (f"{RMS_INVENTORY_404_PENDING_PREFIX} {message}"[:1000], product_id),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile Rakuten RMS inventory into DB current_stock")
    parser.add_argument("--store", default="rakuten_2")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--execute", action="store_true", help="persist the fetched RMS quantities to DB")
    parser.add_argument("--api-interval", type=float, default=0.5, help="RMS inventory GET間の待機秒数")
    parser.add_argument("--retry-count", type=int, default=5, help="429/一時エラー時の再試行回数")
    parser.add_argument("--retry-wait", type=float, default=5.0, help="429/一時エラー時の基本待機秒数")
    args = parser.parse_args()

    store_code = args.store.strip().lower()
    if not store_code:
        raise SystemExit("store is required")
    if not 1 <= args.limit <= 400:
        raise SystemExit("limit must be between 1 and 400")
    if args.api_interval < 0:
        raise SystemExit("api-interval must be >= 0")
    if args.retry_count < 0:
        raise SystemExit("retry-count must be >= 0")
    if args.retry_wait < 0:
        raise SystemExit("retry-wait must be >= 0")

    conn = connect_db()
    checked = 0
    changed = 0
    failed = 0
    rms_404_pending = 0
    rms_deleted = 0
    try:
        with conn.cursor() as cur:
            targets = fetch_targets(cur, store_code, args.limit)
        headers = build_rakuten_auth_header(store_code)
        for index, product in enumerate(targets, start=1):
            checked += 1
            try:
                rms_quantity = fetch_rms_quantity(
                    headers,
                    product["mall_item_code"],
                    product["sku_code"],
                    retry_count=args.retry_count,
                    retry_wait=args.retry_wait,
                    timeout=60,
                )
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
                if index < len(targets) and args.api_interval:
                    time.sleep(args.api_interval)
            except RmsInventoryNotFoundError as exc:
                was_pending = str(product.get("rms_inventory_last_error") or "").startswith(
                    RMS_INVENTORY_404_PENDING_PREFIX
                )
                if was_pending:
                    rms_deleted += 1
                    message = "rms_deleted"
                else:
                    rms_404_pending += 1
                    message = "rms_404_pending"
                print(f"[inventory-reconcile] id={product['id']} {message}: {exc}", flush=True)
                if args.execute:
                    with conn.cursor() as cur:
                        if was_pending:
                            save_rms_deleted(cur, int(product["id"]), str(exc))
                        else:
                            save_rms_inventory_404_pending(cur, int(product["id"]), str(exc))
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
        f"rms_404_pending={rms_404_pending} rms_deleted={rms_deleted} "
        f"failed={failed} execute={args.execute}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
