from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.master_loader import MissingMasterFileError
from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_DIR = BASE_DIR / "reference" / "legacy_listing"
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "result.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 dry-run for Rakuten listing payload preparation")
    parser.add_argument("--asin", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Allow DB SELECT, Amazon, and Keepa reads only.")
    parser.add_argument("--offline", action="store_true", help="Use local JSON fixtures only. No DB, Amazon, or Keepa access.")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--skip-amazon", action="store_true")
    parser.add_argument("--skip-keepa", action="store_true")
    parser.add_argument("--management-number", default="")
    parser.add_argument("--master-dir", default=str(DEFAULT_MASTER_DIR))
    parser.add_argument("--allow-missing-master", action="store_true")
    parser.add_argument("--page-timeout", type=int, default=15000)
    parser.add_argument("--store-settings-json", default="")
    parser.add_argument("--amazon-result-json", default="")
    parser.add_argument("--keepa-result-json", default="")
    return parser.parse_args()


def ensure_output_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()

    try:
        result = prepare_listing(
            PrepareListingRequest(
                asin=args.asin,
                store_code=args.store,
                master_dir=Path(args.master_dir),
                dry_run=args.dry_run,
                offline=args.offline,
                skip_amazon=args.skip_amazon,
                skip_keepa=args.skip_keepa,
                management_number=args.management_number,
                allow_missing_master=args.allow_missing_master,
                page_timeout_ms=args.page_timeout,
                store_settings_json=Path(args.store_settings_json) if args.store_settings_json else None,
                amazon_result_json=Path(args.amazon_result_json) if args.amazon_result_json else None,
                keepa_result_json=Path(args.keepa_result_json) if args.keepa_result_json else None,
            )
        )
    except MissingMasterFileError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"initialization error: {exc}", file=sys.stderr)
        return 2

    public_result = sanitize_for_output(result)
    jsonable = to_jsonable(public_result)
    text = json.dumps(jsonable, ensure_ascii=False, indent=2)
    print(text)

    output_path = Path(args.output_json)
    ensure_output_parent(output_path)
    output_path.write_text(text + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
