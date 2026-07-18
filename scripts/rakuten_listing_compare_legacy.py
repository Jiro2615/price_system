from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.legacy_comparison import compare_with_saved_results, load_legacy_baseline, load_saved_dry_run_result
from scripts.listing.models import sanitize_for_output, to_jsonable


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_PATH = BASE_DIR / "tests" / "fixtures" / "legacy_listing_baseline.json"
DEFAULT_RESULTS_DIR = BASE_DIR / "output" / "listing"
DEFAULT_OUTPUT_PATH = BASE_DIR / "output" / "listing" / "legacy_comparison_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare saved new-system dry-run results against legacy listing baseline")
    parser.add_argument("--baseline-json", default=str(DEFAULT_BASELINE_PATH))
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = load_legacy_baseline(Path(args.baseline_json))
    report = compare_with_saved_results(
        baseline,
        result_loader=lambda asin: load_saved_dry_run_result(Path(args.results_dir), asin),
    )
    public_report = sanitize_for_output(report)
    text = json.dumps(to_jsonable(public_report), ensure_ascii=False, indent=2)
    print(text)
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
