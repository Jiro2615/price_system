"""Plan or apply LifeForest's cosmetics shop-category assignment.

Only products that have a saved Rakuten listing result classified as Beauty or
医薬部外品 are eligible.  The plan reads Category API mappings first and keeps
any existing real categories; the API write is opt-in with ``--execute``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# This script is invoked directly by the execution agent.  Add the project
# root so its ``scripts.*`` package imports work in that invocation mode too.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.db_config import connect_db
from scripts.listing.rakuten_marketplace_policy import is_cosmetics_category
from scripts.listing.rakuten_shop_category_client import (
    DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
    RakutenShopCategoryClient,
    build_mapping_payload,
    response_json,
)


DEFAULT_OUTPUT_DIR = ROOT / "output" / "compliance_updates"


def is_cosmetics_source(dry_run: dict[str, Any]) -> bool:
    keepa = dry_run.get("keepa_result") or {}
    category_tree = keepa.get("category_tree") if isinstance(keepa, dict) else None
    if is_cosmetics_category(category_tree):
        return True
    item_payload = dry_run.get("item_payload") or {}
    if not isinstance(item_payload, dict):
        return False
    return "医薬部外品" in "\n".join(
        str(item_payload.get(key) or "") for key in ("title", "descriptionForPC", "descriptionForSP")
    )


def latest_saved_cosmetics_sources(allowed_asins: set[str]) -> dict[str, dict[str, str]]:
    """Return the newest saved cosmetics decision for currently listed ASINs.

    A listing batch can contain many historic attempts for the same ASIN.  The
    category operation only needs the newest one, so first select that path by
    filename/mtime and then parse just those JSON files.  This keeps a one-off
    existing-item update fast even after the batch archive grows large.
    """
    latest_paths: dict[str, tuple[float, Path]] = {}
    for path in (ROOT / "output" / "listing" / "batches").glob("*/*/dry_run.json"):
        asin = path.parent.name.strip().upper()
        if asin not in allowed_asins:
            continue
        try:
            modified_at = path.stat().st_mtime
        except OSError:
            continue
        if asin not in latest_paths or modified_at > latest_paths[asin][0]:
            latest_paths[asin] = (modified_at, path)

    sources: dict[str, dict[str, str]] = {}
    for asin, (_modified_at, path) in latest_paths.items():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(payload.get("store_code") or "").strip().lower() != "rakuten_2":
            continue
        if str(payload.get("asin") or "").strip().upper() != asin or not is_cosmetics_source(payload):
            continue
        sources[asin] = {"asin": asin, "source_path": str(path)}
    return sources


def listed_products() -> list[dict[str, str]]:
    conn = connect_db(options="-c default_transaction_read_only=on")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.asin, sp.mall_item_code
                FROM store_products sp
                JOIN stores s ON s.id = sp.store_id
                WHERE s.store_code = 'rakuten_2'
                  AND s.mall = 'rakuten'
                  AND sp.enabled = TRUE
                  AND COALESCE(sp.current_status, '') NOT IN ('deleted', 'delete_pending')
                  AND COALESCE(sp.mall_item_code, '') <> ''
                  AND COALESCE(sp.asin, '') <> ''
                ORDER BY sp.id
                """
            )
            return [
                {"asin": str(asin).strip().upper(), "management_number": str(manage_number).strip()}
                for asin, manage_number in cur.fetchall()
            ]
    finally:
        conn.close()


def build_plan(*, category_id: str, limit: int, request_interval: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    client = RakutenShopCategoryClient()
    target_result = client.get_category(category_id, store_code="rakuten_2")
    target = response_json(target_result)
    if not target_result.success or str(target.get("categoryId") or "") != category_id:
        raise RuntimeError(f"cosmetics shop category {category_id} could not be read: {target_result.error_message or target_result.http_status}")
    target_is_plural = str(((target.get("categoryFeatures") or {}).get("categoryPageViewMode") or "")).upper() == "PLURAL"

    products = listed_products()
    candidates = latest_saved_cosmetics_sources({product["asin"] for product in products})
    entries: list[dict[str, Any]] = []
    for product in products:
        if limit and len(entries) >= limit:
            break
        source = candidates.get(product["asin"])
        if not source:
            continue
        mapping_result = client.get_item_mapping(product["management_number"], store_code="rakuten_2")
        current = response_json(mapping_result)
        entry: dict[str, Any] = {
            **product,
            **source,
            "target_category_id": category_id,
            "current_category_ids": list(current.get("categoryIds") or []),
        }
        if not mapping_result.success:
            entry.update({"status": "read_error", "error": mapping_result.error_message or str(mapping_result.http_status)})
        elif category_id in entry["current_category_ids"]:
            entry.update({"status": "already_assigned", "next_category_ids": entry["current_category_ids"]})
        else:
            try:
                payload = build_mapping_payload(
                    current,
                    target_category_id=category_id,
                    target_is_plural=target_is_plural,
                )
                entry.update({"status": "ready", "next_category_ids": payload["categoryIds"], "payload": payload})
            except ValueError as exc:
                entry.update({"status": "blocked", "error": str(exc)})
        entries.append(entry)
        if request_interval > 0:
            time.sleep(request_interval)
    return entries, {
        "target_category": {
            "category_id": category_id,
            "title": str(target.get("title") or ""),
            "page_view_mode": str(((target.get("categoryFeatures") or {}).get("categoryPageViewMode") or "")),
        },
        "candidate_count": len(candidates),
    }


def execute_ready_entries(entries: list[dict[str, Any]], *, request_interval: float) -> None:
    client = RakutenShopCategoryClient()
    for entry in entries:
        if entry.get("status") != "ready":
            continue
        result = client.put_item_mapping(
            str(entry["management_number"]),
            dict(entry.get("payload") or {}),
            store_code="rakuten_2",
        )
        entry["api_status"] = result.http_status
        if result.success:
            entry["status"] = "updated"
        else:
            entry["status"] = "update_error"
            entry["error"] = result.error_message or str(result.http_status)
        print(
            "COSMETIC_CATEGORY_PROGRESS "
            + json.dumps({"asin": entry["asin"], "status": entry["status"]}, ensure_ascii=False),
            flush=True,
        )
        if request_interval > 0:
            time.sleep(request_interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default="rakuten_2")
    parser.add_argument("--category-id", default=DEFAULT_COSMETICS_SHOP_CATEGORY_ID)
    parser.add_argument("--limit", type=int, default=0, help="0 means all detected cosmetics listings")
    parser.add_argument("--request-interval", type=float, default=0.25)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--execute", action="store_true", help="Send Category API updates for ready rows")
    parser.add_argument("--confirm-store", default="", help="Must be rakuten_2 when --execute is used")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if str(args.store or "").strip().lower() != "rakuten_2":
        raise SystemExit("This cosmetics category assignment is restricted to store=rakuten_2")
    category_id = str(args.category_id or "").strip()
    if not category_id.isdecimal():
        raise SystemExit("--category-id must be numeric")
    if args.limit < 0:
        raise SystemExit("--limit must be 0 (all) or greater")
    if args.request_interval < 0:
        raise SystemExit("--request-interval must be 0 or greater")
    if args.execute and str(args.confirm_store or "").strip().lower() != "rakuten_2":
        raise SystemExit("--execute requires --confirm-store rakuten_2")

    entries, summary = build_plan(category_id=category_id, limit=args.limit, request_interval=args.request_interval)
    if args.execute:
        execute_ready_entries(entries, request_interval=args.request_interval)
    counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    payload = {
        "mode": "execute" if args.execute else "plan_only",
        "store_code": "rakuten_2",
        "executed": bool(args.execute),
        **summary,
        "counts": counts,
        "entries": entries,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    output_path = args.output_json or (DEFAULT_OUTPUT_DIR / f"cosmetics_shop_category_{datetime.now():%Y%m%d_%H%M%S}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("COSMETIC_CATEGORY_RESULT " + json.dumps({**payload, "entries": len(entries), "output_json": str(output_path)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
