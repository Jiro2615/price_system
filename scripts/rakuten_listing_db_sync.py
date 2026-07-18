from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.preflight_service import ensure_output_parent
from scripts.listing.listing_db_sync import ListingDbSyncRequest, dump_result, sync_listing_result_to_db


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "listing_db_sync_preview.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync a successful Rakuten listing execute result into local DB")
    parser.add_argument("--result-json", required=True, help="real execute result JSON")
    parser.add_argument("--dry-run-json", default="", help="optional dry-run JSON override")
    parser.add_argument("--store", default="", help="optional store_code override")
    parser.add_argument("--execute", action="store_true", help="perform DB writes; omitted means preview only")
    parser.add_argument("--no-snapshot", action="store_true", help="do not insert rakuten_api_snapshots row")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = sync_listing_result_to_db(
            ListingDbSyncRequest(
                result_json=Path(args.result_json),
                dry_run_json=Path(args.dry_run_json) if args.dry_run_json else None,
                store=args.store,
                execute=bool(args.execute),
                save_snapshot=not bool(args.no_snapshot),
            )
        )
    except Exception as exc:
        print(f"initialization error: {exc}", file=sys.stderr)
        return 2

    text = dump_result(result)
    print(text)
    output_path = Path(args.output_json)
    try:
        ensure_output_parent(output_path)
        output_path.write_text(text + "\r\n", encoding="utf-8")
    except PermissionError as exc:
        print(f"output write error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
