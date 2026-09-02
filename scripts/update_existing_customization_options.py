#!/usr/bin/env python3
"""Replace existing Rakuten product options with the current canonical set.

The operation is deliberately resumable.  Each successful RMS PATCH is
appended to a JSONL checkpoint immediately, so rerunning the same command
skips completed management numbers and continues with the next one.

Only ``customizationOptions`` is PATCHed.  Prices, stock, descriptions,
images, attributes, and SKUs are never included in the request.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
PRICE_SYSTEM_ROOT = ROOT.parent / "price_system"
OUTPUT_DIR = ROOT / "output" / "customization_options_updates"
ITEM_API_BASE = "https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers"
DEFAULT_STORES = ("rakuten_1", "rakuten_2")

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PRICE_SYSTEM_ROOT / "scripts"))

from scripts.db_config import connect_db
from scripts.listing.rakuten_payload_builder import build_customization_options
from scripts.listing.text_sanitizer import sanitize_payload_text_for_rakuten_api
from rakuten_auth import build_rakuten_auth_header


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="既存楽天商品の商品オプションを現行の3項目へ統一する（既定はdry-run）"
    )
    parser.add_argument(
        "--store",
        action="append",
        choices=DEFAULT_STORES,
        help="対象店舗。複数指定可。未指定は rakuten_1 と rakuten_2 の両方。",
    )
    parser.add_argument("--limit", type=int, default=0, help="店舗ごとの最大件数。0は全件。")
    parser.add_argument("--execute", action="store_true", help="RMS Item APIへ実際にPATCHする。")
    parser.add_argument("--api-interval", type=float, default=1.1, help="同一店舗へのPATCH間隔（秒）。")
    parser.add_argument("--retry-count", type=int, default=3, help="一時的な通信・429/5xxの再試行回数。")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="再開用JSONL。未指定時は実行ごとに output 配下へ作成する。",
    )
    return parser.parse_args()


def item_url(manage_number: str) -> str:
    return f"{ITEM_API_BASE}/{quote(manage_number, safe='')}"


def target_management_numbers(store_code: str, limit: int) -> list[str]:
    conn = connect_db(options="-c default_transaction_read_only=on")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT sp.mall_item_code
                FROM store_products sp
                JOIN stores s ON s.id = sp.store_id
                WHERE s.store_code = %s
                  AND s.mall = 'rakuten'
                  AND sp.enabled = TRUE
                  AND COALESCE(sp.current_status, '') NOT IN ('deleted', 'delete_pending', 'rms_deleted')
                  AND COALESCE(sp.mall_item_code, '') <> ''
                ORDER BY sp.mall_item_code
                """,
                (store_code,),
            )
            values = [str(row[0]).strip() for row in cur.fetchall() if str(row[0] or "").strip()]
    finally:
        conn.close()
    return values[:limit] if limit else values


def read_completed(checkpoint: Path) -> set[tuple[str, str]]:
    if not checkpoint.exists():
        return set()
    completed: set[tuple[str, str]] = set()
    for line in checkpoint.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("status") == "updated":
            store = str(entry.get("store") or "").strip()
            management = str(entry.get("management_number") or "").strip()
            if store and management:
                completed.add((store, management))
    return completed


def append_checkpoint(checkpoint: Path, entry: dict[str, Any]) -> None:
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def patch_options(
    *,
    store_code: str,
    manage_number: str,
    options: list[dict[str, object]],
    retry_count: int,
) -> tuple[int, str]:
    headers = build_rakuten_auth_header(store_code)
    for attempt in range(1, max(1, retry_count) + 1):
        try:
            response = requests.patch(
                item_url(manage_number),
                headers=headers,
                json={"customizationOptions": options},
                timeout=60,
            )
        except requests.RequestException as exc:
            if attempt >= max(1, retry_count):
                return 0, f"request error: {exc}"
            time.sleep(min(30.0, 2.0 * attempt))
            continue
        if response.ok:
            return response.status_code, ""
        if response.status_code == 404:
            return response.status_code, response.text[:2000]
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < max(1, retry_count):
                time.sleep(min(60.0, 3.0 * attempt))
                continue
        return response.status_code, response.text[:2000]
    return 0, "retry loop ended unexpectedly"


def main() -> int:
    args = parse_args()
    if args.limit < 0:
        raise SystemExit("--limit は0以上にしてください")
    if args.api_interval < 1.0:
        raise SystemExit("--api-interval はRMS API保護のため1.0秒以上にしてください")
    stores = tuple(args.store or DEFAULT_STORES)
    checkpoint = args.checkpoint or (
        OUTPUT_DIR / f"customization_options_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    )
    options = sanitize_payload_text_for_rakuten_api(build_customization_options())
    completed = read_completed(checkpoint)
    total = 0
    updated = 0
    failed = 0
    skipped = 0

    for store_code in stores:
        management_numbers = target_management_numbers(store_code, args.limit)
        print(
            json.dumps(
                {"event": "store_start", "store": store_code, "targets": len(management_numbers), "checkpoint": str(checkpoint)},
                ensure_ascii=False,
            ),
            flush=True,
        )
        for index, manage_number in enumerate(management_numbers, start=1):
            total += 1
            base = {"at": datetime.now().isoformat(timespec="seconds"), "store": store_code, "management_number": manage_number}
            if (store_code, manage_number) in completed:
                skipped += 1
                continue
            if not args.execute:
                append_checkpoint(checkpoint, {**base, "status": "planned"})
                continue
            status, error = patch_options(
                store_code=store_code,
                manage_number=manage_number,
                options=options,
                retry_count=args.retry_count,
            )
            if 200 <= status < 300:
                updated += 1
                result = {**base, "status": "updated", "http_status": status}
            else:
                failed += 1
                result = {**base, "status": "failed", "http_status": status, "error": error}
            append_checkpoint(checkpoint, result)
            if index % 25 == 0 or index == len(management_numbers) or failed:
                print(
                    json.dumps(
                        {
                            "event": "progress",
                            "store": store_code,
                            "current": index,
                            "store_total": len(management_numbers),
                            "updated": updated,
                            "failed": failed,
                            "skipped": skipped,
                            "checkpoint": str(checkpoint),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            time.sleep(args.api_interval)

    print(
        json.dumps(
            {
                "event": "complete",
                "execute": args.execute,
                "stores": stores,
                "targets": total,
                "updated": updated,
                "failed": failed,
                "skipped": skipped,
                "checkpoint": str(checkpoint),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
