from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.build_offline_listing_dry_run import build_offline_listing_dry_run
from scripts.listing.legacy_offline_input_scanner import scan_offline_input


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE_PATH = BASE_DIR / "tests" / "fixtures" / "legacy_comparison_sample_asins.json"
DEFAULT_INPUT_ROOT = BASE_DIR / "input" / "legacy_comparison"
DEFAULT_OUTPUT_ROOT = BASE_DIR / "output" / "listing"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dry-run JSON files for ready legacy comparison samples")
    parser.add_argument("--sample-json", default=str(DEFAULT_SAMPLE_PATH))
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--store", default="rakuten_1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    samples = json.loads(Path(args.sample_json).read_text(encoding="utf-8"))["samples"]
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)

    generated_paths: list[str] = []
    missing_asins: list[str] = []
    invalid_asins: list[str] = []
    failures: list[dict[str, str]] = []

    for sample in samples:
        asin = str(sample["asin"])
        scan = scan_offline_input(asin, search_roots=[input_root])
        if scan["validation_errors"]:
            invalid_asins.append(asin)
            continue
        if not scan["reusable_for_offline_evaluation"]:
            missing_asins.append(asin)
            continue
        try:
            output_path = output_root / f"{asin}_dry_run.json"
            build_offline_listing_dry_run(
                asin=asin,
                amazon_json=Path(scan["amazon_json_path"]),
                keepa_json=Path(scan["keepa_json_path"]),
                store=args.store,
                output_json=output_path,
            )
            generated_paths.append(str(output_path))
        except Exception as exc:
            failures.append({"asin": asin, "error": str(exc)})

    report = {
        "selected_count": len(samples),
        "ready_count": len(generated_paths) + len(failures),
        "generated_count": len(generated_paths),
        "missing_input_count": len(missing_asins),
        "invalid_input_count": len(invalid_asins),
        "failed_count": len(failures),
        "generated_paths": generated_paths,
        "missing_asins": missing_asins,
        "invalid_asins": invalid_asins,
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
