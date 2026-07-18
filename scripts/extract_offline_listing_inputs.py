from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.models import sanitize_for_output, to_jsonable


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_asin(asin: str, amazon_result: dict[str, Any], keepa_result: dict[str, Any]) -> None:
    expected = asin.upper()
    requested = str(amazon_result.get("requested_asin") or "").upper()
    page_asin = str(amazon_result.get("page_asin") or "").upper()
    keepa_asin = str(keepa_result.get("asin") or "").upper()
    if requested != expected:
        raise RuntimeError(f"Amazon requested_asin mismatch: {requested} != {expected}")
    if page_asin and page_asin != expected:
        raise RuntimeError(f"Amazon page_asin mismatch: {page_asin} != {expected}")
    if keepa_asin != expected:
        raise RuntimeError(f"Keepa asin mismatch: {keepa_asin} != {expected}")


def extract_offline_inputs(dry_run_json_path: Path, output_dir: Path, *, overwrite: bool = False) -> dict[str, Any]:
    dry_run = _load_json(Path(dry_run_json_path))
    asin = str(dry_run.get("asin") or "").strip().upper()
    if not asin:
        raise RuntimeError("dry-run JSON does not contain asin")
    amazon_result = sanitize_for_output(to_jsonable(dry_run.get("amazon_result") or {}))
    keepa_result = sanitize_for_output(to_jsonable(dry_run.get("keepa_result") or {}))
    if not amazon_result or not keepa_result:
        raise RuntimeError("dry-run JSON does not contain both amazon_result and keepa_result")
    _validate_asin(asin, amazon_result, keepa_result)

    out_dir = Path(output_dir)
    amazon_path = out_dir / "amazon_result.json"
    keepa_path = out_dir / "keepa_result.json"
    metadata_path = out_dir / "metadata.json"
    existing = [path for path in (amazon_path, keepa_path, metadata_path) if path.exists()]
    if existing and not overwrite:
        raise RuntimeError(f"output already exists; use --overwrite: {existing[0]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "asin": asin,
        "source": "legacy_system_saved_result",
        "captured_at": None,
        "notes": None,
        "source_dry_run_json": str(Path(dry_run_json_path)),
    }
    amazon_path.write_text(json.dumps(amazon_result, ensure_ascii=False, indent=2) + "\r\n", encoding="utf-8")
    keepa_path.write_text(json.dumps(keepa_result, ensure_ascii=False, indent=2) + "\r\n", encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\r\n", encoding="utf-8")
    return {
        "asin": asin,
        "output_dir": str(out_dir),
        "amazon_result_path": str(amazon_path),
        "keepa_result_path": str(keepa_path),
        "metadata_path": str(metadata_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract amazon_result / keepa_result from an existing listing dry-run JSON")
    parser.add_argument("--dry-run-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = extract_offline_inputs(Path(args.dry_run_json), Path(args.output_dir), overwrite=args.overwrite)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
