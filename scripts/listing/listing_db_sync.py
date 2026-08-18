from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from scripts.db_config import connect_db
from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.preflight_service import load_json


@dataclass
class ListingDbSyncRequest:
    result_json: Path
    dry_run_json: Path | None = None
    store: str = ""
    execute: bool = False
    save_snapshot: bool = True


def _first_variant(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    variants = payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return "", {}
    key = str(next(iter(variants.keys())) or "").strip()
    value = next(iter(variants.values()))
    return key, value if isinstance(value, dict) else {}


def _to_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_jan_code(value: Any) -> str:
    """Return a usable JAN/EAN, or an empty string when the source is not exact.

    Listing preparation obtains this value from Keepa's ``eanList``.  It must
    never replace a previously stored code with a display label or malformed
    value when syncing a later execution result.
    """
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) not in {8, 12, 13, 14}:
        return ""
    check_total = sum(int(digit) * (3 if position % 2 else 1) for position, digit in enumerate(digits[-2::-1], start=1))
    return digits if (check_total + int(digits[-1])) % 10 == 0 else ""


def _load_related_json(result: dict[str, Any], explicit_path: Path | None, key: str) -> dict[str, Any]:
    if explicit_path is not None:
        return load_json(explicit_path)
    raw_path = str(result.get(key) or "").strip()
    if raw_path:
        return load_json(Path(raw_path))
    return {}


def _extract_sync_payload(request: ListingDbSyncRequest) -> dict[str, Any]:
    result = load_json(request.result_json)
    dry_run = _load_related_json(result, request.dry_run_json, "dry_run_json")
    raw = result.get("raw_execute_result") or {}
    executed_item_payload = raw.get("executed_item_payload") or dry_run.get("item_payload") or {}
    inventory_payload = dry_run.get("inventory_payload") or {}
    amazon_result = dry_run.get("amazon_result") or {}
    keepa_result = dry_run.get("keepa_result") or {}

    variant_id, variant_payload = _first_variant(executed_item_payload if isinstance(executed_item_payload, dict) else {})
    management_number = str(
        result.get("management_number")
        or raw.get("management_number")
        or dry_run.get("management_number")
        or executed_item_payload.get("itemNumber")
        or ""
    ).strip()
    store_code = str(request.store or result.get("store_code") or dry_run.get("store_code") or "").strip()
    asin = str(result.get("asin") or raw.get("asin") or dry_run.get("asin") or amazon_result.get("requested_asin") or "").strip().upper()
    standard_price = _to_int_or_none(variant_payload.get("standardPrice"))
    quantity = _to_int_or_none(inventory_payload.get("quantity"))

    return {
        "result": result,
        "dry_run": dry_run,
        "raw_execute_result": raw,
        "asin": asin,
        "store_code": store_code,
        "management_number": management_number,
        "variant_id": variant_id or management_number,
        "title": str(executed_item_payload.get("title") or amazon_result.get("title") or "").strip(),
        "standard_price": standard_price,
        "quantity": quantity,
        "amazon_result": amazon_result,
        "jan_code": _normalize_jan_code(
            keepa_result.get("ean") if isinstance(keepa_result, dict) else getattr(keepa_result, "ean", "")
        ),
        "executed_item_payload": executed_item_payload,
        "inventory_payload": inventory_payload,
        "final_status": str(result.get("final_status") or raw.get("execute_status") or "").strip(),
        "item_success": bool((raw.get("item_result") or {}).get("success")),
        "inventory_success": bool((raw.get("inventory_result") or {}).get("success")),
    }


def _build_preview(sync: dict[str, Any], *, execute: bool, save_snapshot: bool) -> dict[str, Any]:
    ready = (
        sync["final_status"] == "completed"
        and sync["item_success"]
        and sync["inventory_success"]
        and bool(sync["asin"])
        and bool(sync["store_code"])
        and bool(sync["management_number"])
    )
    operations = [
        {
            "table": "amazon_products",
            "mode": "upsert_by_asin",
            "key": {"asin": sync["asin"]},
            "values": {
                "title": sync["amazon_result"].get("title") or sync["title"],
                "amazon_price": sync["amazon_result"].get("amazon_price"),
                "available_qty": sync["amazon_result"].get("available_qty"),
                "gift_available": sync["amazon_result"].get("gift_available"),
                "shipping_status": sync["amazon_result"].get("shipping_status"),
                "business_ng": sync["amazon_result"].get("business_ng"),
                "system_error": sync["amazon_result"].get("system_error"),
                "ng_reason": sync["amazon_result"].get("ng_reason"),
                "jan_code": sync["jan_code"] or None,
            },
        },
        {
            "table": "store_products",
            "mode": "update_or_insert_by_store_id_and_mall_item_code",
            "key": {"store_code": sync["store_code"], "mall_item_code": sync["management_number"]},
            "values": {
                "asin": sync["asin"],
                "sku_code": sync["variant_id"],
                "current_price": sync["standard_price"],
                "current_stock": sync["quantity"],
                "current_status": "listed",
                "item_name": sync["title"],
            },
        },
    ]
    if save_snapshot:
        operations.append(
            {
                "table": "rakuten_api_snapshots",
                "mode": "insert",
                "key": {"store_code": sync["store_code"], "mall_item_code": sync["management_number"]},
                "values": {"api_name": "listing.real_execute"},
            }
        )
    return {
        "mode": "listing_db_sync",
        "execute_requested": execute,
        "ready_for_db_sync": ready,
        "blocking_reasons": [] if ready else _blocking_reasons(sync),
        "external_db_writes_performed": False,
        "asin": sync["asin"],
        "store_code": sync["store_code"],
        "management_number": sync["management_number"],
        "variant_id": sync["variant_id"],
        "title": sync["title"],
        "standard_price": sync["standard_price"],
        "quantity": sync["quantity"],
        "operations": operations,
    }


def _blocking_reasons(sync: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if sync["final_status"] != "completed":
        reasons.append("real execute final_status must be completed")
    if not sync["item_success"]:
        reasons.append("item_result.success must be true")
    if not sync["inventory_success"]:
        reasons.append("inventory_result.success must be true")
    for key in ("asin", "store_code", "management_number"):
        if not sync[key]:
            reasons.append(f"{key} is required")
    return reasons


def _upsert_amazon_product(cur: Any, sync: dict[str, Any]) -> None:
    amazon = sync["amazon_result"]
    cur.execute(
        """
        INSERT INTO amazon_products (
            asin, title, amazon_price, amazon_point, available_qty, gift_available,
            shipping_status, business_ng, system_error, ng_reason, jan_code, checked_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (asin) DO UPDATE SET
            title = EXCLUDED.title,
            amazon_price = EXCLUDED.amazon_price,
            amazon_point = EXCLUDED.amazon_point,
            available_qty = EXCLUDED.available_qty,
            gift_available = EXCLUDED.gift_available,
            shipping_status = EXCLUDED.shipping_status,
            business_ng = EXCLUDED.business_ng,
            system_error = EXCLUDED.system_error,
            ng_reason = EXCLUDED.ng_reason,
            jan_code = COALESCE(EXCLUDED.jan_code, amazon_products.jan_code),
            checked_at = EXCLUDED.checked_at,
            updated_at = EXCLUDED.updated_at
        """,
        (
            sync["asin"],
            amazon.get("title") or sync["title"],
            _to_int_or_none(amazon.get("amazon_price")),
            _to_int_or_none(amazon.get("amazon_point")) or 0,
            _to_int_or_none(amazon.get("available_qty")),
            amazon.get("gift_available"),
            amazon.get("shipping_status") or "",
            bool(amazon.get("business_ng")),
            bool(amazon.get("system_error")),
            amazon.get("ng_reason") or None,
            sync["jan_code"] or None,
        ),
    )


def _get_store_id(cur: Any, store_code: str) -> int:
    cur.execute("SELECT id FROM stores WHERE store_code = %s AND enabled = TRUE", (store_code,))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"store not found or disabled: {store_code}")
    return int(row[0])


def _update_or_insert_store_product(cur: Any, sync: dict[str, Any], store_id: int) -> None:
    cur.execute(
        """
        UPDATE store_products
        SET
            asin = %s,
            sku_code = %s,
            current_price = %s,
            current_stock = %s,
            current_status = %s,
            item_name = %s,
            enabled = TRUE,
            force_stop = FALSE,
            last_synced_at = CURRENT_TIMESTAMP,
            api_last_synced_at = CURRENT_TIMESTAMP,
            api_last_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE store_id = %s
          AND mall_item_code = %s
        """,
        (
            sync["asin"],
            sync["variant_id"],
            sync["standard_price"],
            sync["quantity"],
            "listed",
            sync["title"],
            store_id,
            sync["management_number"],
        ),
    )
    if cur.rowcount:
        return
    cur.execute(
        """
        INSERT INTO store_products (
            store_id, asin, mall_item_code, sku_code, current_price, current_stock,
            current_status, enabled, force_stop, item_name, last_synced_at,
            api_last_synced_at, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, FALSE, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            store_id,
            sync["asin"],
            sync["management_number"],
            sync["variant_id"],
            sync["standard_price"],
            sync["quantity"],
            "listed",
            sync["title"],
        ),
    )


def _insert_snapshot(cur: Any, sync: dict[str, Any], store_id: int) -> None:
    snapshot = sanitize_for_output(
        {
            "final_status": sync["final_status"],
            "item_success": sync["item_success"],
            "inventory_success": sync["inventory_success"],
            "executed_item_payload": sync["executed_item_payload"],
            "inventory_payload": sync["inventory_payload"],
            "raw_execute_result": sync["raw_execute_result"],
        }
    )
    cur.execute(
        """
        INSERT INTO rakuten_api_snapshots (
            store_id, mall_item_code, sku_code, api_name, request_url, response_json, fetched_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (
            store_id,
            sync["management_number"],
            sync["variant_id"],
            "listing.real_execute",
            None,
            Jsonb(to_jsonable(snapshot)),
        ),
    )


def sync_listing_result_to_db(request: ListingDbSyncRequest) -> dict[str, Any]:
    sync = _extract_sync_payload(request)
    result = _build_preview(sync, execute=request.execute, save_snapshot=request.save_snapshot)
    if result["blocking_reasons"] or not request.execute:
        return result

    with connect_db() as conn:
        with conn.cursor() as cur:
            store_id = _get_store_id(cur, sync["store_code"])
            _upsert_amazon_product(cur, sync)
            _update_or_insert_store_product(cur, sync, store_id)
            if request.save_snapshot:
                _insert_snapshot(cur, sync, store_id)
        conn.commit()

    result["external_db_writes_performed"] = True
    return result


def dump_result(result: dict[str, Any]) -> str:
    return json.dumps(to_jsonable(result), ensure_ascii=False, indent=2)
