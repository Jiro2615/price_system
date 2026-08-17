from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.collect_store2_prohibited_phrase_candidates import (
    read_completed_asins,
    read_latest_records,
    read_unique_asins,
    sanitize_error_message,
    write_summary,
)
from scripts.listing.master_loader import apply_store_allowed_phrase_overrides, load_master_data
from scripts.listing.prohibited_word_masking import analyze_prohibited_word_issues
from scripts.price_check_one_asin_db import (
    check_amazon_one,
    close_amazon_page,
    create_amazon_page,
)


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_DIR = BASE_DIR / "reference" / "legacy_listing"
DEFAULT_OUTPUT_JSONL = BASE_DIR / "output" / "diagnostics" / "store2_amazon_chrome_phrase_probe.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect store 2 prohibited-word contexts with one minimized Chrome session. No listing or DB writes."
    )
    parser.add_argument("--asin-file", required=True)
    parser.add_argument("--max-items", type=int, default=25)
    parser.add_argument("--max-consecutive-errors", type=int, default=3)
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_JSONL))
    parser.add_argument("--summary-json", default="")
    parser.add_argument("--master-dir", default=str(DEFAULT_MASTER_DIR))
    parser.add_argument("--page-timeout", type=int, default=30000)
    parser.add_argument("--retry-errors", action="store_true")
    return parser.parse_args()


async def page_text(page: Any, selector: str) -> str:
    try:
        locator = page.locator(selector)
        if await locator.count() == 0:
            return ""
        return "\n".join(text.strip() for text in await locator.all_inner_texts() if text.strip())
    except Exception:
        return ""


async def collect_one(page: Any, asin: str, master_data: Any, page_timeout_ms: int) -> dict[str, object]:
    amazon = await check_amazon_one(asin, page=page, page_timeout_ms=page_timeout_ms)
    title = str(amazon.get("title") or "")
    features = await page_text(page, "#feature-bullets")
    description = "\n".join(
        filter(
            None,
            [
                await page_text(page, "#productDescription"),
                await page_text(page, "#productDetails"),
            ],
        )
    )
    analysis = analyze_prohibited_word_issues(
        {"title": title, "amazon_features": features, "amazon_description": description},
        list(master_data.prohibited_words_rakuten) + list(master_data.prohibited_words_other),
        master_data.allowed_phrase_rules,
        separate_check_rules=master_data.allowed_phrase_separate_checks,
    )
    return {
        "asin": asin,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "result_kind": "result",
        "scan_mode": "amazon_chrome",
        "listing_status": "content_scanned",
        "listing_reason": str(amazon.get("ng_reason") or ""),
        "title": title,
        "amazon_check": {
            "amazon_price": amazon.get("amazon_price"),
            "available_qty": amazon.get("available_qty"),
            "gift_available": amazon.get("gift_available"),
            "shipping_status": amazon.get("shipping_status"),
            "business_ng": bool(amazon.get("business_ng")),
            "system_error": bool(amazon.get("system_error")),
        },
        "matched_forbidden_words": list(analysis["matched_forbidden_words"]),
        "allowed_phrase_matches": list(analysis["allowed_phrase_matches"]),
        "page_needs_reset": bool(amazon.get("page_needs_reset")),
    }


async def run(args: argparse.Namespace) -> int:
    if args.max_items <= 0 or args.max_consecutive_errors <= 0:
        print("--max-items and --max-consecutive-errors must be greater than 0", file=sys.stderr)
        return 2

    asin_file = Path(args.asin_file)
    output_path = Path(args.output_jsonl)
    summary_path = Path(args.summary_json) if args.summary_json else output_path.with_name(output_path.stem + "_summary.json")
    asins = read_unique_asins(asin_file)
    completed = read_completed_asins(output_path, retry_errors=args.retry_errors)
    selected = [asin for asin in asins if asin not in completed][: args.max_items]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    master_data = load_master_data(Path(args.master_dir), allow_missing=True)
    master_data = apply_store_allowed_phrase_overrides(master_data, Path(args.master_dir), "rakuten_2")
    print(f"ASINs: total={len(asins)} completed={len(completed)} selected={len(selected)} mode=amazon_chrome")

    playwright = browser = context = page = None
    consecutive_errors = 0
    try:
        playwright, browser, context, page = await create_amazon_page(start_minimized=True)
        with output_path.open("a", encoding="utf-8", newline="\n") as handle:
            for position, asin in enumerate(selected, start=1):
                try:
                    record = await collect_one(page, asin, master_data, args.page_timeout)
                    if record.get("page_needs_reset"):
                        await close_amazon_page(playwright, browser, context, page)
                        playwright, browser, context, page = await create_amazon_page(start_minimized=True)
                except Exception as exc:
                    record = {
                        "asin": asin,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "result_kind": "error",
                        "scan_mode": "amazon_chrome",
                        "error": sanitize_error_message(f"{type(exc).__name__}: {exc}"),
                        "matched_forbidden_words": [],
                        "allowed_phrase_matches": [],
                    }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                print(f"[{position}/{len(selected)}] {asin}: {record.get('listing_status') or record.get('result_kind')}")
                if record.get("result_kind") == "error":
                    consecutive_errors += 1
                    if consecutive_errors >= args.max_consecutive_errors:
                        print(f"Stopping after {consecutive_errors} consecutive errors.")
                        break
                else:
                    consecutive_errors = 0
    finally:
        await close_amazon_page(playwright, browser, context, page)

    write_summary(summary_path, read_latest_records(output_path), len(asins))
    print(f"Saved probe results: {output_path}")
    print(f"Saved review summary: {summary_path}")
    return 0


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
