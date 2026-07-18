from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.listing.models import AmazonCheckResult, KeepaProductData


DEFAULT_SEARCH_ROOTS = [
    Path("input/legacy_comparison"),
    Path("output/listing"),
    Path("output/amazon"),
    Path("output/keepa"),
    Path("tests/fixtures"),
]


def _candidate_directories(asin: str, roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        candidate = root / asin
        if candidate.exists() and candidate.is_dir():
            candidates.append(candidate)
    return candidates


def _candidate_dry_runs(asin: str, roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    filename = f"{asin}_dry_run.json"
    for root in roots:
        direct = root / filename
        if direct.exists():
            candidates.append(direct)
            continue
        try:
            for nested in root.rglob(filename):
                candidates.append(nested)
        except OSError:
            continue
    return candidates


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _validate_amazon_payload(asin: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        parsed = AmazonCheckResult(**payload)
    except Exception as exc:
        return [f"amazon_result.json dataclass conversion failed: {exc}"]
    if str(parsed.requested_asin or "").upper() != asin:
        errors.append(f"Amazon requested_asin mismatch: {parsed.requested_asin}")
    if parsed.page_asin and str(parsed.page_asin).upper() != asin:
        errors.append(f"Amazon page_asin mismatch: {parsed.page_asin}")
    return errors


def _validate_keepa_payload(asin: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        parsed = KeepaProductData(**payload)
    except Exception as exc:
        return [f"keepa_result.json dataclass conversion failed: {exc}"]
    if str(parsed.asin or "").upper() != asin:
        errors.append(f"Keepa asin mismatch: {parsed.asin}")
    return errors


def scan_offline_input(asin: str, search_roots: list[Path] | None = None) -> dict[str, Any]:
    normalized_asin = asin.strip().upper()
    roots = [Path(root) for root in (search_roots or DEFAULT_SEARCH_ROOTS)]
    canonical_dir = roots[0] / normalized_asin
    candidate_dirs = _candidate_directories(normalized_asin, roots)
    selected_dir = candidate_dirs[0] if candidate_dirs else canonical_dir
    amazon_path = selected_dir / "amazon_result.json"
    keepa_path = selected_dir / "keepa_result.json"
    metadata_path = selected_dir / "metadata.json"

    validation_errors: list[str] = []
    missing_components: list[str] = []

    directory_exists = bool(candidate_dirs) or canonical_dir.exists()
    amazon_json_exists = amazon_path.exists()
    keepa_json_exists = keepa_path.exists()
    metadata_exists = metadata_path.exists()

    amazon_json_valid = False
    keepa_json_valid = False
    asin_matches = False
    amazon_payload: dict[str, Any] | None = None
    keepa_payload: dict[str, Any] | None = None

    if not directory_exists:
        missing_components.append("directory")
    if not amazon_json_exists:
        missing_components.append("amazon_result.json")
    if not keepa_json_exists:
        missing_components.append("keepa_result.json")

    if amazon_json_exists:
        amazon_payload, error = _load_json(amazon_path)
        if error:
            validation_errors.append(f"amazon_result.json invalid JSON: {error}")
        elif isinstance(amazon_payload, dict):
            amazon_errors = _validate_amazon_payload(normalized_asin, amazon_payload)
            if amazon_errors:
                validation_errors.extend(amazon_errors)
            else:
                amazon_json_valid = True

    if keepa_json_exists:
        keepa_payload, error = _load_json(keepa_path)
        if error:
            validation_errors.append(f"keepa_result.json invalid JSON: {error}")
        elif isinstance(keepa_payload, dict):
            keepa_errors = _validate_keepa_payload(normalized_asin, keepa_payload)
            if keepa_errors:
                validation_errors.extend(keepa_errors)
            else:
                keepa_json_valid = True

    asin_matches = amazon_json_valid and keepa_json_valid
    reusable = directory_exists and amazon_json_valid and keepa_json_valid and asin_matches

    dry_run_sources = [str(path) for path in _candidate_dry_runs(normalized_asin, roots)]

    return {
        "asin": normalized_asin,
        "search_roots": [str(root) for root in roots],
        "directory_exists": directory_exists,
        "candidate_directories": [str(path) for path in candidate_dirs],
        "amazon_json_exists": amazon_json_exists,
        "keepa_json_exists": keepa_json_exists,
        "metadata_exists": metadata_exists,
        "amazon_json_valid": amazon_json_valid,
        "keepa_json_valid": keepa_json_valid,
        "asin_matches": asin_matches,
        "reusable_for_offline_evaluation": reusable,
        "missing_components": missing_components,
        "validation_errors": validation_errors,
        "canonical_directory": str(canonical_dir),
        "selected_directory": str(selected_dir) if directory_exists else None,
        "amazon_json_path": str(amazon_path) if amazon_json_exists else None,
        "keepa_json_path": str(keepa_path) if keepa_json_exists else None,
        "metadata_path": str(metadata_path) if metadata_exists else None,
        "dry_run_json_sources": dry_run_sources,
    }


def scan_selected_inputs(samples: list[dict[str, Any]], search_roots: list[Path] | None = None) -> dict[str, Any]:
    results = [scan_offline_input(str(item["asin"]), search_roots=search_roots) for item in samples]
    return {
        "selected_count": len(samples),
        "ready_count": sum(1 for item in results if item["reusable_for_offline_evaluation"]),
        "missing_input_count": sum(1 for item in results if item["missing_components"]),
        "invalid_input_count": sum(1 for item in results if item["validation_errors"]),
        "results": results,
    }
