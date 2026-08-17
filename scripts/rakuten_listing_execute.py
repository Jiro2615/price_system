from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import urlparse

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.image_downloader import DownloadedImageResult
from scripts.listing.image_validator import ValidatedImageResult
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.rakuten_image_client import RakutenImageClient, RakutenImageUploadResult
from scripts.listing.rakuten_inventory_client import RakutenInventoryClient, RakutenInventoryResult, build_inventory_request
from scripts.listing.rakuten_item_client import RakutenItemClient, RakutenItemResult, build_item_request


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "execute_result.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or mock-execute a Rakuten listing execute flow from dry-run JSON")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--asin", required=True)
    parser.add_argument("--management-number", default="")
    parser.add_argument("--store", default="")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--mock-execute", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_output_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _hash_payload(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    text = json.dumps(to_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()


def _path_only(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.path or None


def _extract_item_management_number(item_payload: dict[str, Any] | None) -> str:
    if not isinstance(item_payload, dict):
        return ""
    variants = item_payload.get("variants")
    if not isinstance(variants, dict) or not variants:
        return ""
    return str(next(iter(variants.keys())) or "").strip()


def _extract_inventory_management_number(inventory_payload: dict[str, Any] | None) -> str:
    if not isinstance(inventory_payload, dict):
        return ""
    variant_path = inventory_payload.get("variantPath") or {}
    if not isinstance(variant_path, dict):
        return ""
    return str(variant_path.get("managementNumber") or "").strip()


def _extract_inventory_variant_key(inventory_payload: dict[str, Any] | None) -> str:
    if not isinstance(inventory_payload, dict):
        return ""
    variant_path = inventory_payload.get("variantPath") or {}
    if not isinstance(variant_path, dict):
        return ""
    return str(variant_path.get("variantKey") or "").strip()


def _contains_representative_color(item_payload: dict[str, Any] | None) -> bool:
    if not isinstance(item_payload, dict):
        return False
    variants = item_payload.get("variants") or {}
    if not isinstance(variants, dict):
        return False
    for variant in variants.values():
        if not isinstance(variant, dict):
            continue
        for attribute in variant.get("attributes") or []:
            if isinstance(attribute, dict) and str(attribute.get("name") or "") == "代表カラー":
                return True
    return False


def _representative_color_value(item_payload: dict[str, Any] | None) -> str:
    if not isinstance(item_payload, dict):
        return ""
    variants = item_payload.get("variants") or {}
    if not isinstance(variants, dict):
        return ""
    for variant in variants.values():
        if not isinstance(variant, dict):
            continue
        for attribute in variant.get("attributes") or []:
            if not isinstance(attribute, dict) or str(attribute.get("name") or "") != "代表カラー":
                continue
            values = attribute.get("values")
            if isinstance(values, list):
                return next((str(value).strip() for value in values if str(value).strip()), "")
            return str(attribute.get("value") or "").strip()
    return ""


def _build_unresolved_specifications(dry_run_result: dict[str, Any]) -> list[dict[str, Any]]:
    item_payload = dry_run_result.get("item_payload")
    if not isinstance(item_payload, dict):
        return []
    try:
        genre_id = int(item_payload.get("genreId"))
    except (TypeError, ValueError):
        genre_id = None
    if (
        genre_id == 213661
        and _contains_representative_color(item_payload)
        and _representative_color_value(item_payload) != "-"
    ):
        return [
            {
                "field": "代表カラー",
                "human_confirmation_required": True,
                "reason": "代表カラーの楽天API登録仕様が未確認です",
                "details": {
                    "genreId": genre_id,
                    "attributeId_confirmed": False,
                    "choiceId_confirmed": False,
                    "value_text_send_confirmed": False,
                },
            }
        ]
    return []


def _build_image_execution_plan(dry_run_result: dict[str, Any]) -> list[dict[str, Any]]:
    plan = dry_run_result.get("image_download_plan") or {}
    items = list(plan.get("items") or []) if isinstance(plan, dict) else []
    mapped: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        order = int(item.get("order") or 0)
        mapped.append(
            {
                "source_url": item.get("source_url"),
                "role": role,
                "order": order,
                "planned_filename": item.get("planned_filename"),
                "planned_relative_path": item.get("planned_relative_path"),
                "validation_required": True,
                "upload_required": True,
                "upload_destination": None,
                "item_payload_mapping": "images[0]" if role == "main" else f"images[{order - 1}]",
            }
        )
    return mapped


def _build_image_request_summary(dry_run_result: dict[str, Any]) -> dict[str, Any]:
    image_plan = _build_image_execution_plan(dry_run_result)
    return {
        "method": "POST",
        "endpoint_path": None,
        "image_count": len(image_plan),
        "filenames": [item["planned_filename"] for item in image_plan],
        "auth_configured": False,
    }


def _build_item_request_summary(dry_run_result: dict[str, Any], management_number: str) -> dict[str, Any]:
    item_payload = dry_run_result.get("item_payload")
    if not isinstance(item_payload, dict) or not management_number:
        return {}
    request = build_item_request(management_number, item_payload, {})
    return {
        "method": "PUT",
        "endpoint_path": _path_only(request.url),
        "management_number": management_number,
        "payload_hash": _hash_payload(request.payload),
        "payload_keys": sorted(request.payload.keys()),
        "payload": request.payload,
        "auth_configured": False,
    }


def _build_inventory_request_summary(dry_run_result: dict[str, Any], management_number: str) -> dict[str, Any]:
    inventory_payload = dry_run_result.get("inventory_payload")
    if not isinstance(inventory_payload, dict) or not management_number:
        return {}
    request = build_inventory_request(management_number, inventory_payload, {})
    return {
        "method": "PUT",
        "endpoint_path": _path_only(request.url),
        "management_number": request.management_number,
        "variant_key": request.variant_id,
        "quantity": request.payload.get("quantity"),
        "payload_hash": _hash_payload(request.payload),
        "payload": request.payload,
        "auth_configured": False,
    }


def _build_preflight_checks(
    dry_run_result: dict[str, Any],
    *,
    input_json_path: Path,
    asin_arg: str,
    management_number_arg: str,
    store_arg: str,
    mode: str,
    unresolved_specifications: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    asin = str(dry_run_result.get("asin") or "").strip()
    store_code = str(dry_run_result.get("store_code") or "").strip()
    management_number = str(dry_run_result.get("management_number") or "").strip()
    item_payload = dry_run_result.get("item_payload")
    inventory_payload = dry_run_result.get("inventory_payload")
    image_urls = list(dry_run_result.get("image_urls") or [])
    legacy_spacing_reviews = list(dry_run_result.get("legacy_spacing_reviews") or [])
    matched_forbidden_words = list(dry_run_result.get("matched_forbidden_words") or [])
    blocking_reasons = list(dry_run_result.get("blocking_reasons") or [])
    image_download_plan = dry_run_result.get("image_download_plan") or {}
    item_management_number = _extract_item_management_number(item_payload if isinstance(item_payload, dict) else None)
    inventory_management_number = _extract_inventory_management_number(inventory_payload if isinstance(inventory_payload, dict) else None)
    inventory_variant_key = _extract_inventory_variant_key(inventory_payload if isinstance(inventory_payload, dict) else None)
    standard_price = None
    attribute_count = 0
    payload_title = ""
    if isinstance(item_payload, dict):
        payload_title = str(item_payload.get("title") or "").strip()
        variants = item_payload.get("variants") or {}
        if isinstance(variants, dict) and variants:
            first_variant = next(iter(variants.values()))
            if isinstance(first_variant, dict):
                standard_price = first_variant.get("standardPrice")
                attribute_count = len(first_variant.get("attributes") or [])
    checks: list[dict[str, Any]] = []

    def add(key: str, value: Any, ok: bool, note: str = "", *, warning: bool = False) -> None:
        status = "ok" if ok else "warning" if warning else "blocked"
        checks.append({"key": key, "status": status, "value": value, "note": note})

    add("input_json_exists", str(input_json_path), input_json_path.exists())
    add("input_json_parsed", True, True)
    add("asin_match", {"input": asin, "argument": asin_arg}, asin == asin_arg)
    add("store_code_match", {"input": store_code, "argument": store_arg or store_code}, not store_arg or store_code == store_arg)
    add("listing_status_eligible", dry_run_result.get("listing_status"), dry_run_result.get("listing_status") == "eligible")
    add("execution_allowed", dry_run_result.get("execution_allowed"), bool(dry_run_result.get("execution_allowed")))
    add("blocking_reasons_empty", blocking_reasons, not blocking_reasons)
    add("management_number_present", management_number, bool(management_number))
    add("item_payload_present", isinstance(item_payload, dict), isinstance(item_payload, dict))
    add("inventory_payload_present", isinstance(inventory_payload, dict), isinstance(inventory_payload, dict))
    add("image_download_plan_present", bool(image_download_plan), bool(image_download_plan))
    add("image_urls_present", len(image_urls), len(image_urls) > 0)
    add("legacy_spacing_reviews_empty", legacy_spacing_reviews, not legacy_spacing_reviews)
    add("matched_forbidden_words_empty", matched_forbidden_words, not matched_forbidden_words)
    add("item_management_number_match", {"dry_run": management_number, "item": item_management_number}, management_number == item_management_number)
    add(
        "inventory_management_number_match",
        {"dry_run": management_number, "inventory": inventory_management_number},
        management_number == inventory_management_number,
    )
    add(
        "argument_management_number_match",
        {"input": management_number, "argument": management_number_arg or management_number},
        (not management_number_arg) or management_number == management_number_arg,
    )
    add(
        "inventory_variant_key_match",
        {"dry_run": management_number, "variant_key": inventory_variant_key},
        management_number == inventory_variant_key,
    )
    add("payload_title_present", payload_title, bool(payload_title))
    add("standard_price_numeric", standard_price, isinstance(standard_price, (int, float)))
    quantity = inventory_payload.get("quantity") if isinstance(inventory_payload, dict) else None
    add("inventory_quantity_present", quantity, isinstance(quantity, int) and quantity >= 0)
    ean = None
    keepa_result = dry_run_result.get("keepa_result")
    if isinstance(keepa_result, dict):
        ean = keepa_result.get("ean")
    else:
        ean = getattr(keepa_result, "ean", None)
    add("jan_ean_present", ean, bool(str(ean or "").strip()))
    add("attributes_present", attribute_count, attribute_count > 0)
    add("master_files_missing", list(dry_run_result.get("missing_master_files") or []), not list(dry_run_result.get("missing_master_files") or []), warning=True)
    add("allowed_phrase_matches_present", len(dry_run_result.get("allowed_phrase_matches") or []), True)
    add("required_separate_checks", list(dry_run_result.get("required_separate_checks") or []), True, warning=True)
    if unresolved_specifications:
        add(
            "unresolved_specifications",
            unresolved_specifications,
            mode != "execute",
            "plan-only/mock-execute では warning、execute では blocked",
            warning=(mode != "execute"),
        )
    return checks


def _derive_preflight_status(checks: list[dict[str, Any]]) -> str:
    statuses = [str(item.get("status") or "") for item in checks]
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _mock_download_result(plan: dict[str, Any] | None, *, output_root: Path, http_get: Callable[[str, float, bool], Any] | None = None) -> dict[str, Any]:
    items = []
    for item in list((plan or {}).get("items") or []):
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("planned_relative_path") or "")
        local_path = output_root / Path(*Path(relative_path).parts)
        items.append(
            DownloadedImageResult(
                role=str(item.get("role") or ""),
                order=int(item.get("order") or 0),
                source_url=str(item.get("source_url") or ""),
                planned_filename=str(item.get("planned_filename") or ""),
                relative_path=relative_path,
                local_path=str(local_path),
                local_exists=True,
                download_status="downloaded",
                http_status=200,
                content_type="image/jpeg",
                file_size=16,
                validation_errors=[],
            )
        )
    return {
        "execution_allowed": True,
        "blocked_reason": None,
        "output_root": str(output_root),
        "items": items,
        "downloaded_count": len(items),
        "failed_count": 0,
    }


def _mock_validation_result(items: list[Any]) -> dict[str, Any]:
    validated = []
    for item in items:
        validated.append(
            ValidatedImageResult(
                role=getattr(item, "role", ""),
                order=getattr(item, "order", 0),
                source_url=getattr(item, "source_url", ""),
                planned_filename=getattr(item, "planned_filename", ""),
                relative_path=getattr(item, "relative_path", ""),
                local_path=getattr(item, "local_path", ""),
                local_exists=True,
                download_status=getattr(item, "download_status", "downloaded"),
                http_status=getattr(item, "http_status", 200),
                content_type=getattr(item, "content_type", "image/jpeg"),
                file_size=getattr(item, "file_size", 16),
                width=1000,
                height=1000,
                sha256=sha256(str(getattr(item, "local_path", "")).encode("utf-8")).hexdigest(),
                validation_status="valid",
                validation_errors=[],
                upload_status="not_uploaded",
                rakuten_image_url=None,
                error_type=None,
                error_message=None,
            )
        )
    return {"items": validated, "valid_count": len(validated), "invalid_count": 0, "failed_count": 0}


def _run_mock_execute(dry_run_result: dict[str, Any], asin: str, management_number: str) -> dict[str, Any]:
    with TemporaryDirectory(dir=str(BASE_DIR)) as temp_dir:
        image_client = RakutenImageClient(
            uploader=lambda request: RakutenImageUploadResult(
                upload_status="uploaded",
                rakuten_image_url=f"https://image.mock.rakuten/{request.filename}",
                request_summary={"filename": request.filename},
                response_status=201,
            )
        )
        item_client = RakutenItemClient(
            sender=lambda request: RakutenItemResult(
                success=True,
                management_number=request.management_number,
                http_status=200,
                response_body_summary={"result": "ok"},
                retryable=False,
                request_summary={"url": request.url},
            )
        )
        inventory_client = RakutenInventoryClient(
            sender=lambda request: RakutenInventoryResult(
                success=True,
                management_number=request.management_number,
                http_status=200,
                response_body_summary={"result": "ok"},
                retryable=False,
                request_summary={"url": request.url},
            )
        )
        return execute_listing(
            ExecuteListingRequest(
                dry_run_result=dry_run_result,
                execute=True,
                approved=True,
                asin=asin,
                management_number=management_number,
                output_root=Path(temp_dir),
            ),
            image_downloader=_mock_download_result,
            image_validator=_mock_validation_result,
            image_client=image_client,
            item_client=item_client,
            inventory_client=inventory_client,
        )


def build_execute_cli_result(
    dry_run_result: dict[str, Any],
    *,
    input_json_path: Path,
    asin: str,
    management_number: str,
    store: str,
    mode: str,
    approved: bool,
) -> dict[str, Any]:
    dry_run_result = dict(dry_run_result)
    unresolved_specifications = _build_unresolved_specifications(dry_run_result)
    preflight_checks = _build_preflight_checks(
        dry_run_result,
        input_json_path=input_json_path,
        asin_arg=asin,
        management_number_arg=management_number,
        store_arg=store,
        mode=mode,
        unresolved_specifications=unresolved_specifications,
    )
    preflight_status = _derive_preflight_status(preflight_checks)
    input_management_number = str(dry_run_result.get("management_number") or "").strip()
    item_management_number = _extract_item_management_number(dry_run_result.get("item_payload"))
    inventory_management_number = _extract_inventory_management_number(dry_run_result.get("inventory_payload"))
    inventory_variant_key = _extract_inventory_variant_key(dry_run_result.get("inventory_payload"))
    all_management_numbers_match = bool(
        input_management_number
        and input_management_number == item_management_number == inventory_management_number == inventory_variant_key
        and ((not management_number) or input_management_number == management_number)
    )
    warnings = list(dry_run_result.get("warnings") or [])
    if unresolved_specifications and mode != "execute":
        warnings.append("unresolved specifications require human confirmation before real execute")
    blocking_reasons = list(dry_run_result.get("blocking_reasons") or [])
    if unresolved_specifications and mode == "execute":
        blocking_reasons.append("unresolved specifications block real execute")

    ready_for_mock_execute = preflight_status != "blocked"
    ready_for_real_execute = preflight_status != "blocked" and not unresolved_specifications and approved
    result = {
        "mode": mode,
        "asin": dry_run_result.get("asin"),
        "store_code": dry_run_result.get("store_code"),
        "management_number": dry_run_result.get("management_number"),
        "input_management_number": input_management_number,
        "argument_management_number": management_number,
        "item_management_number": item_management_number,
        "inventory_management_number": inventory_management_number,
        "inventory_variant_key": inventory_variant_key,
        "all_management_numbers_match": all_management_numbers_match,
        "preflight_status": preflight_status,
        "preflight_checks": preflight_checks,
        "warnings": warnings,
        "blocking_reasons": blocking_reasons,
        "unresolved_specifications": unresolved_specifications,
        "human_confirmation_required": bool(unresolved_specifications),
        "allowed_phrase_matches": dry_run_result.get("allowed_phrase_matches") or [],
        "matched_forbidden_words": dry_run_result.get("matched_forbidden_words") or [],
        "legacy_spacing_reviews": dry_run_result.get("legacy_spacing_reviews") or [],
        "image_execution_plan": _build_image_execution_plan(dry_run_result),
        "image_request_summary": _build_image_request_summary(dry_run_result),
        "item_request_summary": _build_item_request_summary(dry_run_result, input_management_number),
        "inventory_request_summary": _build_inventory_request_summary(dry_run_result, input_management_number),
        "execution_sequence": ["image download", "validation", "image upload", "item PUT", "item success confirmation", "inventory PUT"],
        "external_actions_performed": False,
        "secrets_exposed": False,
        "ready_for_mock_execute": ready_for_mock_execute,
        "ready_for_real_execute": ready_for_real_execute,
        "approved": approved,
        "listing_status": dry_run_result.get("listing_status"),
        "listing_reason": dry_run_result.get("listing_reason"),
        "execution_summary": dry_run_result.get("execution_summary"),
    }

    if mode == "mock_execute" and ready_for_mock_execute:
        result["mock_execute_result"] = sanitize_for_output(
            to_jsonable(_run_mock_execute(dry_run_result, str(dry_run_result.get("asin") or ""), input_management_number))
        )
    elif mode == "execute":
        result["execute_status"] = "blocked"
        if unresolved_specifications:
            result["execute_reason"] = "real execute is blocked by unresolved specifications"
        else:
            result["execute_reason"] = "real execute transport is not enabled in this phase"

    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_json_path = Path(args.input_json)
    if not input_json_path.exists():
        print(f"input JSON not found: {input_json_path}", file=sys.stderr)
        return 2

    try:
        dry_run_result = _load_json(input_json_path)
        mode = "plan_only" if args.plan_only else "mock_execute" if args.mock_execute else "execute"
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_json_path,
            asin=args.asin,
            management_number=args.management_number,
            store=args.store,
            mode=mode,
            approved=args.approved,
        )
    except Exception as exc:
        print(f"initialization error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(to_jsonable(result), ensure_ascii=False, indent=2)
    print(text)
    output_path = Path(args.output_json)
    _ensure_output_parent(output_path)
    output_path.write_text(text + "\r\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
