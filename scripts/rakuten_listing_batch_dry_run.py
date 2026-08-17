"""Run the normal listing preparation pipeline for a bounded ASIN batch.

This command is dry-run only: it may read Amazon, Keepa, Rakuten Web Service,
and the local/DB masters, but never uploads images or creates a Rakuten item.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.prepare_service import (
    PrepareListingRequest,
    precheck_keepa_before_amazon,
    precheck_local_listing_exclusion,
    prepare_listing,
)
from scripts.listing.amazon_bridge import fetch_amazon_result
from scripts.price_check_one_asin_db import create_amazon_page


ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
MAX_ASINS = 10000
# Current Keepa plan refills 20 tokens/minute.  Metadata-only prechecks cost
# one product token, so this leaves a small safety margin while adding no wait
# during the much slower Amazon-page path.
KEEPA_PRECHECK_MIN_INTERVAL_SECONDS = 3.1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asin-file", type=Path, required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--master-dir", type=Path, default=Path("reference/legacy_listing"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--page-timeout", type=int, default=15000)
    parser.add_argument("--allow-missing-master", action="store_true")
    return parser.parse_args()


def load_asins(path: Path) -> list[str]:
    raw = [line.strip().upper() for line in path.read_text(encoding="utf-8-sig").splitlines()]
    asins = list(dict.fromkeys(item for item in raw if item))
    invalid = [item for item in asins if not ASIN_RE.fullmatch(item)]
    if invalid:
        raise ValueError(f"invalid ASINs: {', '.join(invalid[:10])}")
    if not asins:
        raise ValueError("ASIN input is empty")
    if len(asins) > MAX_ASINS:
        raise ValueError(f"ASIN input exceeds {MAX_ASINS}")
    return asins


async def run_batch(args: argparse.Namespace, asins: list[str]) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "results.jsonl"
    summary_path = args.output_dir / "summary.json"
    counts: dict[str, int] = {}

    # This batch owns one visible Chrome page and intentionally does not close
    # it between ASINs or when the batch completes.
    playwright, browser, context, page = await create_amazon_page()
    next_keepa_precheck_at = 0.0
    with results_path.open("w", encoding="utf-8") as handle:
        for index, asin in enumerate(asins, start=1):
            try:
                request = PrepareListingRequest(
                    asin=asin, store_code=args.store, master_dir=args.master_dir,
                    dry_run=True, allow_missing_master=args.allow_missing_master,
                    page_timeout_ms=args.page_timeout,
                )
                result = precheck_local_listing_exclusion(request)
                if result is None:
                    now = asyncio.get_running_loop().time()
                    if now < next_keepa_precheck_at:
                        await asyncio.sleep(next_keepa_precheck_at - now)
                    next_keepa_precheck_at = asyncio.get_running_loop().time() + KEEPA_PRECHECK_MIN_INTERVAL_SECONDS
                    keepa_block, keepa_result = await asyncio.to_thread(
                        precheck_keepa_before_amazon,
                        request,
                    )
                    if keepa_block is not None:
                        result = keepa_block
                    else:
                        amazon_result = await fetch_amazon_result(asin, page_timeout_ms=args.page_timeout, page=page)
                        result = prepare_listing(
                            request,
                            amazon_fetcher=lambda _asin, _timeout: amazon_result,
                            keepa_fetcher=lambda _asin: keepa_result,
                        )
                payload = to_jsonable(sanitize_for_output(result))
            except Exception as exc:  # Keep later ASINs running even if one fails.
                payload = {
                    "asin": asin,
                    "mode": "dry_run",
                    "listing_status": "system_error",
                    "listing_reason": str(exc),
                    "execution_allowed": False,
                }
            payload["batch_index"] = index
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            status = str(payload.get("listing_status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
            print(f"LISTING_BATCH_PROGRESS {index}/{len(asins)} asin={asin} status={status}", flush=True)

    summary = {
        "mode": "dry_run",
        "store": args.store,
        "input_count": len(asins),
        "status_counts": counts,
        "eligible_count": counts.get("eligible", 0),
        "results_jsonl": str(results_path),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("LISTING_BATCH_SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    args = parse_args()
    asins = load_asins(args.asin_file)
    return asyncio.run(run_batch(args, asins))


if __name__ == "__main__":
    raise SystemExit(main())
