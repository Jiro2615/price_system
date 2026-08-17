from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.preflight_service import ensure_output_parent
from scripts.listing.real_execute_service import RealExecuteRequest, build_real_execute_result
from scripts.listing.real_execute_plan_service import build_real_execute_plan_result
from scripts.listing.listing_db_sync import ListingDbSyncRequest, sync_listing_result_to_db


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "real_execute_plan.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a real execute plan or guarded execute result from saved readiness/dry-run/mock results")
    parser.add_argument("--plan-only", action="store_true", help="build plan JSON only")
    parser.add_argument("--execute", action="store_true", help="required for any external processing")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--confirm-real-api", action="store_true")
    parser.add_argument("--allow-live-transport", action="store_true")
    parser.add_argument("--manual-image-cleanup-completed", action="store_true")
    parser.add_argument("--resume-after-image-upload", action="store_true")
    parser.add_argument("--resume-after-item-upsert", action="store_true")
    parser.add_argument("--confirm-asin", default="")
    parser.add_argument("--confirm-management-number", default="")
    parser.add_argument("--confirm-store", default="")
    parser.add_argument("--readiness-json", required=True)
    parser.add_argument("--dry-run-json", required=True)
    parser.add_argument("--preflight-json", required=True)
    parser.add_argument("--mock-result-json", required=True)
    parser.add_argument("--asin", required=True)
    parser.add_argument("--management-number", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.plan_only:
            result = build_real_execute_plan_result(
                readiness_json=Path(args.readiness_json),
                dry_run_json=Path(args.dry_run_json),
                preflight_json=Path(args.preflight_json),
                mock_result_json=Path(args.mock_result_json),
                asin=args.asin,
                management_number=args.management_number,
                store=args.store,
            )
        else:
            result = build_real_execute_result(
                RealExecuteRequest(
                    readiness_json=Path(args.readiness_json),
                    dry_run_json=Path(args.dry_run_json),
                    preflight_json=Path(args.preflight_json),
                    mock_result_json=Path(args.mock_result_json),
                    asin=args.asin,
                    management_number=args.management_number,
                    store=args.store,
                    execute=args.execute,
                    approved=args.approved,
                    confirm_real_api=args.confirm_real_api,
                    allow_live_transport=args.allow_live_transport,
                    manual_image_cleanup_completed=args.manual_image_cleanup_completed,
                    resume_after_image_upload=args.resume_after_image_upload,
                    resume_after_item_upsert=args.resume_after_item_upsert,
                    confirm_asin=args.confirm_asin,
                    confirm_management_number=args.confirm_management_number,
                    confirm_store=args.confirm_store,
                )
            )
    except Exception as exc:
        print(f"initialization error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    output_path = Path(args.output_json)
    try:
        ensure_output_parent(output_path)
        output_path.write_text(text + "\r\n", encoding="utf-8")
    except PermissionError as exc:
        print(f"output write error: {exc}", file=sys.stderr)
        return 1
    if args.execute and result.get("final_status") == "completed":
        try:
            db_sync = sync_listing_result_to_db(ListingDbSyncRequest(result_json=output_path, dry_run_json=Path(args.dry_run_json), store=args.store, execute=True))
            result["db_sync"] = db_sync
            if not db_sync.get("external_db_writes_performed"):
                result["final_status"] = "db_sync_failed"
        except Exception as exc:
            result["db_sync"] = {"external_db_writes_performed": False, "error": str(exc)}
            result["final_status"] = "db_sync_failed"
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
