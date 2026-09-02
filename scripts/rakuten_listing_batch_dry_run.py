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
FORCE_BYPASS_RULES = frozenset({"blacklist", "past_ng", "prohibited_words", "missing_attributes", "seller_count", "regulated_evidence"})
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
    parser.add_argument(
        "--prepare-workers",
        type=int,
        default=2,
        help="Amazon確認タブ数 (1-4)。Keepa確認はトークン保護のため直列です。",
    )
    parser.add_argument("--allow-missing-master", action="store_true")
    parser.add_argument("--ignore-rules", default="", help="条件無視ASIN出品で許可するルール（カンマ区切り）")
    parser.add_argument("--require-minimum-same-jan-listings", action="store_true")
    return parser.parse_args()


def parse_bypass_rules(value: str) -> tuple[str, ...]:
    rules = tuple(dict.fromkeys(part.strip() for part in str(value or "").split(",") if part.strip()))
    unknown = sorted(set(rules) - FORCE_BYPASS_RULES)
    if unknown:
        raise ValueError(f"unsupported ignore rules: {', '.join(unknown)}")
    return rules


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
    if not 1 <= args.prepare_workers <= 4:
        raise ValueError("prepare-workers must be between 1 and 4")
    args.bypass_rules = parse_bypass_rules(args.ignore_rules)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "results.jsonl"
    summary_path = args.output_dir / "summary.json"
    counts: dict[str, int] = {}

    # Keepa's token refill is shared, so Keepa stays serial. Amazon checks can
    # run in the requested number of visible tabs after a candidate passes it.
    playwright, browser, context, page = await create_amazon_page()
    prepare_pages = [page]
    for _ in range(1, args.prepare_workers):
        prepare_pages.append(await context.new_page())

    local_precheck_workers = min(4, max(2, args.prepare_workers * 2))
    pipeline_buffer_size = max(50, args.prepare_workers * 10)
    prepared_queue: asyncio.Queue[tuple[int, str, dict[str, object]] | None] = asyncio.Queue(maxsize=pipeline_buffer_size)
    local_input_queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue(maxsize=pipeline_buffer_size)
    keepa_candidate_queue: asyncio.Queue[tuple[int, str, PrepareListingRequest] | None] = asyncio.Queue(maxsize=pipeline_buffer_size)
    amazon_candidate_queue: asyncio.Queue[tuple[int, str, PrepareListingRequest, object] | None] = asyncio.Queue(maxsize=pipeline_buffer_size)

    def system_error(asin: str, exc: Exception) -> dict[str, object]:
        return {
            "asin": asin,
            "mode": "dry_run",
            "listing_status": "system_error",
            "listing_reason": str(exc),
            "execution_allowed": False,
        }

    async def prepare_amazon_candidate(index: int, asin: str, request: PrepareListingRequest, keepa_result: object, amazon_page, tab_number: int) -> dict[str, object]:
        try:
            print(f"LISTING_PREPARE_TAB_START tab={tab_number}/{args.prepare_workers} index={index} asin={asin}", flush=True)
            amazon_result = await fetch_amazon_result(asin, page_timeout_ms=args.page_timeout, page=amazon_page)
            result = await asyncio.to_thread(
                prepare_listing,
                request,
                amazon_fetcher=lambda _asin, _timeout: amazon_result,
                keepa_fetcher=lambda _asin: keepa_result,
            )
            print(f"LISTING_PREPARE_TAB_DONE tab={tab_number}/{args.prepare_workers} index={index} asin={asin}", flush=True)
            return result
        except Exception as exc:
            return system_error(asin, exc)

    async def feed_local_prechecks() -> None:
        for index, asin in enumerate(asins, start=1):
            await local_input_queue.put((index, asin))
        for _ in range(local_precheck_workers):
            await local_input_queue.put(None)

    async def run_local_precheck_worker() -> None:
        while True:
            item = await local_input_queue.get()
            if item is None:
                return
            index, asin = item
            request = PrepareListingRequest(
                asin=asin,
                store_code=args.store,
                master_dir=args.master_dir,
                dry_run=True,
                allow_missing_master=args.allow_missing_master,
                page_timeout_ms=args.page_timeout,
                bypass_rules=args.bypass_rules,
                require_minimum_same_jan_listings=args.require_minimum_same_jan_listings,
            )
            try:
                result = await asyncio.to_thread(precheck_local_listing_exclusion, request)
                if result is not None:
                    await prepared_queue.put((index, asin, result))
                else:
                    await keepa_candidate_queue.put((index, asin, request))
            except Exception as exc:
                await prepared_queue.put((index, asin, system_error(asin, exc)))

    async def run_keepa_prechecks() -> None:
        next_keepa_precheck_at = 0.0
        while True:
            candidate = await keepa_candidate_queue.get()
            if candidate is None:
                break
            index, asin, request = candidate
            try:
                now = asyncio.get_running_loop().time()
                if now < next_keepa_precheck_at:
                    await asyncio.sleep(next_keepa_precheck_at - now)
                next_keepa_precheck_at = asyncio.get_running_loop().time() + KEEPA_PRECHECK_MIN_INTERVAL_SECONDS
                keepa_block, keepa_result = await asyncio.to_thread(precheck_keepa_before_amazon, request)
                if keepa_block is not None:
                    await prepared_queue.put((index, asin, keepa_block))
                else:
                    await amazon_candidate_queue.put((index, asin, request, keepa_result))
            except Exception as exc:
                await prepared_queue.put((index, asin, system_error(asin, exc)))
        for _ in range(args.prepare_workers):
            await amazon_candidate_queue.put(None)

    async def run_amazon_precheck_worker(tab_number: int) -> None:
        amazon_page = prepare_pages[tab_number - 1]
        while True:
            candidate = await amazon_candidate_queue.get()
            if candidate is None:
                return
            index, asin, request, keepa_result = candidate
            result = await prepare_amazon_candidate(index, asin, request, keepa_result, amazon_page, tab_number)
            await prepared_queue.put((index, asin, result))

    async def close_local_stage() -> None:
        workers = [asyncio.create_task(run_local_precheck_worker()) for _ in range(local_precheck_workers)]
        await feed_local_prechecks()
        await asyncio.gather(*workers)
        await keepa_candidate_queue.put(None)

    async def close_amazon_stage() -> None:
        await asyncio.gather(*(run_amazon_precheck_worker(tab_number + 1) for tab_number in range(args.prepare_workers)))
        await prepared_queue.put(None)

    print(
        "LISTING_BATCH_DRY_RUN_PIPELINE "
        f"local_precheck_workers={local_precheck_workers} "
        "keepa_precheck_workers=1 "
        f"amazon_prepare_workers={args.prepare_workers} buffer={pipeline_buffer_size}",
        flush=True,
    )
    local_stage = asyncio.create_task(close_local_stage())
    keepa_stage = asyncio.create_task(run_keepa_prechecks())
    amazon_stage = asyncio.create_task(close_amazon_stage())

    with results_path.open("w", encoding="utf-8") as handle:
        while True:
            prepared_item = await prepared_queue.get()
            if prepared_item is None:
                break
            index, asin, result = prepared_item
            payload = to_jsonable(sanitize_for_output(result))
            payload["batch_index"] = index
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            status = str(payload.get("listing_status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
            print(f"LISTING_BATCH_PROGRESS {index}/{len(asins)} asin={asin} status={status}", flush=True)

    await asyncio.gather(local_stage, keepa_stage, amazon_stage)

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
