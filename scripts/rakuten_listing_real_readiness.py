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
from scripts.listing.preflight_service import ensure_output_parent
from scripts.listing.real_readiness_service import build_real_readiness_result


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "real_readiness.json"
DEFAULT_API_SPEC_JSON = BASE_DIR / "reference" / "rakuten_api" / "rakuten_listing_api_spec.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local readiness report before any real Rakuten pilot execute")
    parser.add_argument("--dry-run-json", required=True)
    parser.add_argument("--preflight-json", required=True)
    parser.add_argument("--mock-result-json", required=True)
    parser.add_argument("--api-spec-json", default=str(DEFAULT_API_SPEC_JSON))
    parser.add_argument("--asin", required=True)
    parser.add_argument("--management-number", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_real_readiness_result(
            dry_run_json=Path(args.dry_run_json),
            preflight_json=Path(args.preflight_json),
            mock_result_json=Path(args.mock_result_json),
            api_spec_json=Path(args.api_spec_json),
            asin=args.asin,
            management_number=args.management_number,
            store=args.store,
        )
    except Exception as exc:
        print(f"real readiness error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(to_jsonable(result), ensure_ascii=False, indent=2)
    print(text)
    output_path = Path(args.output_json)
    ensure_output_parent(output_path)
    output_path.write_text(text + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
