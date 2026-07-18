from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.legacy_offline_input_scanner import DEFAULT_SEARCH_ROOTS, scan_selected_inputs
from scripts.listing.models import sanitize_for_output, to_jsonable


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE_PATH = BASE_DIR / "tests" / "fixtures" / "legacy_comparison_sample_asins.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan offline Amazon/Keepa inputs for selected legacy comparison ASINs")
    parser.add_argument("--sample-json", default=str(DEFAULT_SAMPLE_PATH))
    parser.add_argument("--search-root", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample_payload = json.loads(Path(args.sample_json).read_text(encoding="utf-8"))
    roots = [Path(item) for item in args.search_root] if args.search_root else DEFAULT_SEARCH_ROOTS
    report = scan_selected_inputs(sample_payload["samples"], search_roots=roots)
    print(json.dumps(to_jsonable(sanitize_for_output(report)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
