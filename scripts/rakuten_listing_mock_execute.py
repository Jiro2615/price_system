from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.mock_execute_service import build_mock_execute_result
from scripts.listing.models import to_jsonable
from scripts.listing.preflight_service import ensure_output_parent, load_json


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "mock_execute_result.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a fully mocked Rakuten listing execute flow from dry-run and preflight JSON")
    parser.add_argument("--dry-run-json", required=True)
    parser.add_argument("--preflight-json", required=True)
    parser.add_argument("--asin", required=True)
    parser.add_argument("--management-number", required=True)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument(
        "--fail-step",
        choices=["", "image-download", "image-validation", "image-upload", "item", "inventory"],
        default="",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dry_run_path = Path(args.dry_run_json)
    preflight_path = Path(args.preflight_json)
    if not dry_run_path.exists():
        print(f"dry-run JSON not found: {dry_run_path}", file=sys.stderr)
        return 2
    if not preflight_path.exists():
        print(f"preflight JSON not found: {preflight_path}", file=sys.stderr)
        return 2

    try:
        dry_run_result = load_json(dry_run_path)
        preflight_result = load_json(preflight_path)
        result = build_mock_execute_result(
            dry_run_result,
            preflight_result,
            asin=args.asin,
            management_number=args.management_number,
            approved=args.approved,
            fail_step=args.fail_step,
        )
    except Exception as exc:
        print(f"mock execute error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(to_jsonable(result), ensure_ascii=False, indent=2)
    print(text)

    output_path = Path(args.output_json)
    ensure_output_parent(output_path)
    output_path.write_text(text + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
