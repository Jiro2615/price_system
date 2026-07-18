from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.models import to_jsonable
from scripts.listing.preflight_service import build_preflight_result, ensure_output_parent, load_json


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "preflight_result.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local preflight report from a Rakuten listing dry-run JSON")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--asin", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--management-number", default="")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_json_path = Path(args.input_json)
    if not input_json_path.exists():
        print(f"input JSON not found: {input_json_path}", file=sys.stderr)
        return 2

    try:
        dry_run_result = load_json(input_json_path)
        result = build_preflight_result(
            dry_run_result,
            input_json_path=input_json_path,
            asin=args.asin,
            store=args.store,
            management_number=args.management_number,
        )
    except Exception as exc:
        print(f"preflight error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(to_jsonable(result), ensure_ascii=False, indent=2)
    print(text)

    output_path = Path(args.output_json)
    ensure_output_parent(output_path)
    output_path.write_text(text + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
