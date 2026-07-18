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

from scripts.listing.master_loader import MissingMasterFileError
from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_DIR = BASE_DIR / "reference" / "legacy_listing"
DEFAULT_STORE_SETTINGS_JSON = BASE_DIR / "tests" / "fixtures" / "offline_store_settings.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate_input_asin(asin: str, amazon_json: Path, keepa_json: Path) -> None:
    expected = asin.upper()
    amazon_payload = _load_json(amazon_json)
    keepa_payload = _load_json(keepa_json)
    requested = str(amazon_payload.get("requested_asin") or "").upper()
    page_asin = str(amazon_payload.get("page_asin") or "").upper()
    keepa_asin = str(keepa_payload.get("asin") or "").upper()
    if requested != expected:
        raise RuntimeError(f"Amazon requested_asin mismatch: {requested} != {expected}")
    if page_asin and page_asin != expected:
        raise RuntimeError(f"Amazon page_asin mismatch: {page_asin} != {expected}")
    if keepa_asin != expected:
        raise RuntimeError(f"Keepa asin mismatch: {keepa_asin} != {expected}")


def build_offline_listing_dry_run(
    *,
    asin: str,
    amazon_json: Path,
    keepa_json: Path,
    store: str,
    output_json: Path | None = None,
    overwrite: bool = False,
    store_settings_json: Path = DEFAULT_STORE_SETTINGS_JSON,
    master_dir: Path = DEFAULT_MASTER_DIR,
    allow_missing_master: bool = True,
) -> dict[str, Any]:
    normalized_asin = asin.strip().upper()
    _validate_input_asin(normalized_asin, amazon_json, keepa_json)
    result = prepare_listing(
        PrepareListingRequest(
            asin=normalized_asin,
            store_code=store,
            master_dir=master_dir,
            offline=True,
            allow_missing_master=allow_missing_master,
            store_settings_json=store_settings_json,
            amazon_result_json=amazon_json,
            keepa_result_json=keepa_json,
        )
    )
    public_result = sanitize_for_output(result)
    if output_json is not None:
        output_path = Path(output_json)
        if output_path.exists() and not overwrite:
            raise RuntimeError(f"output already exists; use --overwrite: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(to_jsonable(public_result), ensure_ascii=False, indent=2) + "\r\n", encoding="utf-8")
    return public_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a dry-run JSON from offline Amazon/Keepa input files only")
    parser.add_argument("--asin", required=True)
    parser.add_argument("--amazon-json", required=True)
    parser.add_argument("--keepa-json", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--store-settings-json", default=str(DEFAULT_STORE_SETTINGS_JSON))
    parser.add_argument("--master-dir", default=str(DEFAULT_MASTER_DIR))
    parser.add_argument("--strict-master", action="store_true", help="Fail when optional master files are missing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build_offline_listing_dry_run(
            asin=args.asin,
            amazon_json=Path(args.amazon_json),
            keepa_json=Path(args.keepa_json),
            store=args.store,
            output_json=Path(args.output_json),
            overwrite=args.overwrite,
            store_settings_json=Path(args.store_settings_json),
            master_dir=Path(args.master_dir),
            allow_missing_master=not args.strict_master,
        )
    except MissingMasterFileError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"offline build error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(to_jsonable(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
