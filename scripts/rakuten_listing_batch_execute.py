"""Prepare listings concurrently, then execute the approved results serially."""
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
    parser.add_argument(
        "--prepare-workers",
        type=int,
        default=2,
        help="Amazon/Keepa を使う出品判定の並列数 (1-4)。RMS 実出品は常に 1 件ずつです。",
    )
    parser.add_argument("--allow-missing-master", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--confirm-real-api", action="store_true")
    parser.add_argument("--allow-live-transport", action="store_true")
    parser.add_argument("--update-existing", action="store_true", help="既出品のタイトル・説明・画像だけを最新化する")
    return parser.parse_args()


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(to_jsonable(sanitize_for_output(payload)), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run_batch(args: argparse.Namespace, asins: list[str]) -> int:
    if not (args.execute and args.approved and args.confirm_real_api and args.allow_live_transport):
        raise ValueError("--execute --approved --confirm-real-api --allow-live-transport are required")
    if len(asins) > min(MAX_ASINS, args.max_execute):
        raise ValueError(f"execution batch exceeds max-execute={args.max_execute}")
    if not 1 <= args.prepare_workers <= 4:
        raise ValueError("prepare-workers must be between 1 and 4")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "results.jsonl"
    playwright, browser, context, page = await create_amazon_page()
    completed = 0
    cabinet_folder_resolver = CachedCabinetUploadFolderResolver()
    prepare_pages = [page]
    for _ in range(1, args.prepare_workers):
        prepare_pages.append(await context.new_page())

    # 最速の経路は、ローカル判定・Keepa・Amazon・RMSを独立させること。
    # Keepa は契約トークンを守るため1本・一定間隔、Amazonはページごとに
    # 並列、RMS/Cabinetへの更新だけを必ず直列にする。
    local_precheck_workers = min(4, max(2, args.prepare_workers * 2))
    pipeline_buffer_size = max(50, args.prepare_workers * 10)
    prepared_queue: asyncio.Queue[tuple[int, str, dict[str, object]] | None] = asyncio.Queue(
        maxsize=pipeline_buffer_size
    )
    local_input_queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue(maxsize=pipeline_buffer_size)
    keepa_candidate_queue: asyncio.Queue[tuple[int, str, PrepareListingRequest] | None] = asyncio.Queue(
        maxsize=pipeline_buffer_size
    )
    amazon_candidate_queue: asyncio.Queue[tuple[int, str, PrepareListingRequest, object] | None] = asyncio.Queue(
        maxsize=pipeline_buffer_size
    )

    async def prepare_amazon_candidate(
        index: int,
        asin: str,
        request: PrepareListingRequest,
        keepa_result: object,
        amazon_page,
        tab_number: int,
    ) -> dict[str, object]:
        """Use one visible tab for a Keepa-approved candidate."""
        try:
            print(
                f"LISTING_PREPARE_TAB_START tab={tab_number}/{args.prepare_workers} "
                f"index={index} asin={asin}",
                flush=True,
            )
            amazon_result = await fetch_amazon_result(
                asin,
                page_timeout_ms=args.page_timeout,
                page=amazon_page,
            )
            dry = await asyncio.to_thread(
                prepare_listing,
                request,
                amazon_fetcher=lambda _asin, _timeout: amazon_result,
                keepa_fetcher=lambda _asin: keepa_result,
            )
            print(
                f"LISTING_PREPARE_TAB_DONE tab={tab_number}/{args.prepare_workers} "
                f"index={index} asin={asin}",
                flush=True,
            )
            return dry
        except Exception as exc:
            return {"asin": asin, "final_status": "system_error", "error": str(exc)}

    async def feed_local_prechecks() -> None:
        for index, asin in enumerate(asins, start=1):
            await local_input_queue.put((index, asin))
        for _ in range(local_precheck_workers):
            await local_input_queue.put(None)

    async def run_local_precheck_worker(worker_number: int) -> None:
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
                update_existing=args.update_existing,
            )
            try:
                dry = await asyncio.to_thread(precheck_local_listing_exclusion, request)
                if dry is not None:
                    await prepared_queue.put((index, asin, dry))
                    continue
                await keepa_candidate_queue.put((index, asin, request))
            except Exception as exc:
                await prepared_queue.put((index, asin, {"asin": asin, "final_status": "system_error", "error": str(exc)}))

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
                await prepared_queue.put((index, asin, {"asin": asin, "final_status": "system_error", "error": str(exc)}))
        for _ in range(args.prepare_workers):
            await amazon_candidate_queue.put(None)

    async def run_amazon_precheck_worker(tab_number: int) -> None:
        amazon_page = prepare_pages[tab_number - 1]
        while True:
            candidate = await amazon_candidate_queue.get()
            if candidate is None:
                return
            index, asin, request, keepa_result = candidate
            dry = await prepare_amazon_candidate(
                index,
                asin,
                request,
                keepa_result,
                amazon_page,
                tab_number,
            )
            await prepared_queue.put((index, asin, dry))

    async def close_local_stage() -> None:
        workers = [
            asyncio.create_task(run_local_precheck_worker(worker_number + 1))
            for worker_number in range(local_precheck_workers)
        ]
        await feed_local_prechecks()
        await asyncio.gather(*workers)
        await keepa_candidate_queue.put(None)

    async def close_amazon_stage() -> None:
        await asyncio.gather(
            *(run_amazon_precheck_worker(tab_number + 1) for tab_number in range(args.prepare_workers))
        )
        await prepared_queue.put(None)

    async def execute_one(index: int, asin: str, dry: dict[str, object]) -> dict[str, object]:
        nonlocal completed
        if dry.get("final_status") == "system_error" and not dry.get("management_number"):
            return dry
        item_dir = args.output_dir / asin
        item_dir.mkdir(exist_ok=True)
        try:
            management = str(dry.get("management_number") or "")
            dry_path = item_dir / "dry_run.json"; save_json(dry_path, dry)
            preflight = await asyncio.to_thread(
                build_preflight_result,
                dry,
                input_json_path=dry_path,
                asin=asin,
                store=args.store,
                management_number=management,
            )
            preflight_path = item_dir / "preflight.json"; save_json(preflight_path, preflight)
            mock = await asyncio.to_thread(build_mock_execute_result, dry, preflight, asin=asin, management_number=management, approved=True)
            mock_path = item_dir / "mock.json"; save_json(mock_path, mock)
            readiness = await asyncio.to_thread(
                build_real_readiness_result,
                dry_run_json=dry_path,
                preflight_json=preflight_path,
                mock_result_json=mock_path,
                api_spec_json=API_SPEC,
                asin=asin,
                management_number=management,
                store=args.store,
                allow_existing_update=args.update_existing,
            )
            readiness_path = item_dir / "readiness.json"; save_json(readiness_path, readiness)
            result = await asyncio.to_thread(
                build_real_execute_result,
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
                    content_refresh=args.update_existing,
                ),
                cabinet_folder_resolver=cabinet_folder_resolver,
            )
            save_json(item_dir / "execute.json", result)
            if result.get("final_status") == "completed" and not args.update_existing:
                db_sync = await asyncio.to_thread(
                    sync_listing_result_to_db,
                    ListingDbSyncRequest(result_json=item_dir / "execute.json", dry_run_json=dry_path, store=args.store, execute=True),
                )
                result["db_sync"] = db_sync
                if not db_sync.get("external_db_writes_performed"):
                    result["final_status"] = "db_sync_failed"
                save_json(item_dir / "execute.json", result)
            if result.get("final_status") == "completed":
                completed += 1
            return result
        except Exception as exc:
            return {"asin": asin, "final_status": "system_error", "error": str(exc)}

    print(
        "LISTING_BATCH_EXECUTE_PIPELINE "
        f"local_precheck_workers={local_precheck_workers} "
        "keepa_precheck_workers=1 "
        f"amazon_prepare_workers={args.prepare_workers} "
        "rms_execute_workers=1 "
        f"buffer={pipeline_buffer_size}",
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
            index, asin, dry = prepared_item
            result = await execute_one(index, asin, dry)
            result["batch_index"] = index
            handle.write(json.dumps(to_jsonable(sanitize_for_output(result)), ensure_ascii=False) + "\n"); handle.flush()
            print(f"LISTING_BATCH_EXECUTE_PROGRESS {index}/{len(asins)} asin={asin} status={result.get('final_status')}", flush=True)
    await asyncio.gather(local_stage, keepa_stage, amazon_stage)
    summary = {"mode": "real_execute", "store": args.store, "input_count": len(asins), "completed_count": completed, "results_jsonl": str(results_path), "completed_at": datetime.now(timezone.utc).isoformat()}
    save_json(args.output_dir / "summary.json", summary)
    print("LISTING_BATCH_EXECUTE_SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run_batch(args, load_asins(args.asin_file)))


if __name__ == "__main__":
    raise SystemExit(main())
