from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.offline_dry_run_comparator import compare_offline_dry_runs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare source dry-run and offline rebuilt dry-run")
    parser.add_argument("--source-dry-run", required=True)
    parser.add_argument("--offline-dry-run", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output_json)
    if output_path.exists() and not args.overwrite:
        print(f"comparison output already exists; use --overwrite: {output_path}", file=sys.stderr)
        return 2
    report = compare_offline_dry_runs(Path(args.source_dry_run), Path(args.offline_dry_run))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
