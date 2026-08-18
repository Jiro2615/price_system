"""Prepare and execute a bounded, sequential Rakuten listing batch."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.rakuten_listing_batch_dry_run import MAX_ASINS, load_asins
from scripts.listing.amazon_bridge import fetch_amazon_result
from scripts.listing.mock_execute_service import build_mock_execute_result
from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.preflight_service import build_preflight_result
from scripts.listing.prepare_service import (
    PrepareListingRequest,
    precheck_keepa_before_amazon,
    precheck_local_listing_exclusion,
    prepare_listing,
)
from scripts.listing.real_execute_service import RealExecuteRequest, build_real_execute_result
from scripts.listing.cabinet_rotation import CachedCabinetUploadFolderResolver
from scripts.listing.listing_db_sync import ListingDbSyncRequest, sync_listing_result_to_db
from scripts.listing.real_readiness_service import build_real_readiness_result
from scripts.price_check_one_asin_db import create_amazon_page


BASE_DIR = Path(__file__).resolve().parents[1]
API_SPEC = BASE_DIR / "reference" / "rakuten_api" / "rakuten_listing_api_spec.json"
KEEPA_PRECHECK_MIN_INTERVAL_SECONDS = 3.1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asin-file", type=Path, required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--master-dir", type=Path, default=Path("reference/legacy_listing"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--page-timeout", type=int, default=15000)
    parser.add_argument("--max-execute", type=int, default=MAX_ASINS)
    parser.add_argument("--allow-missing-master", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--confirm-real-api", action="store_true")
    parser.add_argument("--allow-live-transport", action="store_true")
    return parser.parse_args()


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(to_jsonable(sanitize_for_output(payload)), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run_batch(args: argparse.Namespace, asins: list[str]) -> int:
    if not (args.execute and args.approved and args.confirm_real_api and args.allow_live_transport):
        raise ValueError("--execute --approved --confirm-real-api --allow-live-transport are required")
    if len(asins) > min(MAX_ASINS, args.max_execute):
        raise ValueError(f"execution batch exceeds max-execute={args.max_execute}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "results.jsonl"
    playwright, browser, context, page = await create_amazon_page()
    completed = 0
    next_keepa_precheck_at = 0.0
    cabinet_folder_resolver = CachedCabinetUploadFolderResolver()
    with results_path.open("w", encoding="utf-8") as handle:
        for index, asin in enumerate(asins, start=1):
            item_dir = args.output_dir / asin
            item_dir.mkdir(exist_ok=True)
            try:
                request = PrepareListingRequest(asin=asin, store_code=args.store, master_dir=args.master_dir, dry_run=True, allow_missing_master=args.allow_missing_master, page_timeout_ms=args.page_timeout)
                dry = precheck_local_listing_exclusion(request)
                if dry is None:
                    now = asyncio.get_running_loop().time()
                    if now < next_keepa_precheck_at:
                        await asyncio.sleep(next_keepa_precheck_at - now)
                    next_keepa_precheck_at = asyncio.get_running_loop().time() + KEEPA_PRECHECK_MIN_INTERVAL_SECONDS
                    keepa_block, keepa_result = await asyncio.to_thread(
                        precheck_keepa_before_amazon,
                        request,
                    )
                    if keepa_block is not None:
                        dry = keepa_block
                    else:
                        amazon_result = await fetch_amazon_result(asin, page_timeout_ms=args.page_timeout, page=page)
                        dry = prepare_listing(
                            request,
                            amazon_fetcher=lambda _asin, _timeout: amazon_result,
                            keepa_fetcher=lambda _asin: keepa_result,
                        )
                management = str(dry.get("management_number") or "")
                dry_path = item_dir / "dry_run.json"; save_json(dry_path, dry)
                preflight = build_preflight_result(dry, input_json_path=dry_path, asin=asin, store=args.store, management_number=management)
                preflight_path = item_dir / "preflight.json"; save_json(preflight_path, preflight)
                mock = build_mock_execute_result(dry, preflight, asin=asin, management_number=management, approved=True)
                mock_path = item_dir / "mock.json"; save_json(mock_path, mock)
                readiness = build_real_readiness_result(dry_run_json=dry_path, preflight_json=preflight_path, mock_result_json=mock_path, api_spec_json=API_SPEC, asin=asin, management_number=management, store=args.store)
                readiness_path = item_dir / "readiness.json"; save_json(readiness_path, readiness)
                result = build_real_execute_result(
                    RealExecuteRequest(
                        readiness_json=readiness_path,
                        dry_run_json=dry_path,
                        preflight_json=preflight_path,
                        mock_result_json=mock_path,
                        asin=asin,
                        management_number=management,
                        store=args.store,
                        execute=True,
                        approved=True,
                        confirm_real_api=True,
                        confirm_asin=asin,
                        confirm_management_number=management,
                        confirm_store=args.store,
                        allow_live_transport=True,
                    ),
                    cabinet_folder_resolver=cabinet_folder_resolver,
                )
                save_json(item_dir / "execute.json", result)
                if result.get("final_status") == "completed":
                    db_sync = sync_listing_result_to_db(ListingDbSyncRequest(result_json=item_dir / "execute.json", dry_run_json=dry_path, store=args.store, execute=True))
                    result["db_sync"] = db_sync
                    if not db_sync.get("external_db_writes_performed"):
                        result["final_status"] = "db_sync_failed"
                    save_json(item_dir / "execute.json", result)
                if result.get("final_status") == "completed": completed += 1
            except Exception as exc:
                result = {"asin": asin, "final_status": "system_error", "error": str(exc)}
            result["batch_index"] = index
            handle.write(json.dumps(to_jsonable(sanitize_for_output(result)), ensure_ascii=False) + "\n"); handle.flush()
            print(f"LISTING_BATCH_EXECUTE_PROGRESS {index}/{len(asins)} asin={asin} status={result.get('final_status')}", flush=True)
    summary = {"mode": "real_execute", "store": args.store, "input_count": len(asins), "completed_count": completed, "results_jsonl": str(results_path), "completed_at": datetime.now(timezone.utc).isoformat()}
    save_json(args.output_dir / "summary.json", summary)
    print("LISTING_BATCH_EXECUTE_SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run_batch(args, load_asins(args.asin_file)))


if __name__ == "__main__":
    raise SystemExit(main())
