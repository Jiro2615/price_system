from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.listing.image_downloader import DownloadedImageResult
from scripts.listing.image_validator import ValidatedImageResult
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.rakuten_image_client import RakutenImageClient, RakutenImageUploadResult
from scripts.listing.rakuten_inventory_client import RakutenInventoryClient, RakutenInventoryResult, build_inventory_request
from scripts.listing.rakuten_item_client import RakutenItemClient, RakutenItemResult


IMAGE_DOWNLOAD_FAILED = "image_download_failed"
IMAGE_VALIDATION_FAILED = "image_validation_failed"
IMAGE_UPLOAD_FAILED = "image_upload_failed"
ITEM_FAILED = "item_failed"
INVENTORY_FAILED = "inventory_failed"
VALIDATION_FAILED = "validation_failed"
COMPLETED = "completed"
MOCK_TEMP_ROOT = Path(__file__).resolve().parents[2] / "output" / "listing" / "mock_tmp"


def _planned_upload_url(asin: str, role: str, order: int) -> str:
    if role == "main":
        filename = "main.jpg"
    else:
        filename = f"sub_{order:02d}.jpg"
    return f"https://mock.invalid/rakuten/{asin}/{filename}"


def _mock_download_result_factory(fail_step: str):
    def _mock_download_result(plan: dict[str, Any] | None, *, output_root: Path, http_get=None) -> dict[str, Any]:
        items = []
        for raw in list((plan or {}).get("items") or []):
            if not isinstance(raw, dict):
                continue
            local_path = output_root / Path(str(raw.get("planned_relative_path") or "").replace("/", "\\"))
            status = "downloaded"
            local_exists = True
            error_type = None
            error_message = None
            if fail_step == "image-download" and int(raw.get("order") or 0) == 1:
                status = "failed"
                local_exists = False
                error_type = "mock_download_failure"
                error_message = "forced mock image download failure"
            items.append(
                DownloadedImageResult(
                    role=str(raw.get("role") or ""),
                    order=int(raw.get("order") or 0),
                    source_url=str(raw.get("source_url") or ""),
                    planned_filename=str(raw.get("planned_filename") or ""),
                    relative_path=str(raw.get("planned_relative_path") or ""),
                    local_path=str(local_path),
                    local_exists=local_exists,
                    download_status=status,
                    http_status=200 if status == "downloaded" else None,
                    content_type="image/jpeg" if status == "downloaded" else None,
                    file_size=16 if status == "downloaded" else None,
                    validation_errors=[],
                    upload_status="not_uploaded",
                    rakuten_image_url=None,
                    error_type=error_type,
                    error_message=error_message,
                )
            )
        return {
            "execution_allowed": True,
            "blocked_reason": None,
            "output_root": str(output_root),
            "items": items,
            "downloaded_count": sum(1 for item in items if item.download_status in {"downloaded", "reused"}),
            "failed_count": sum(1 for item in items if item.download_status == "failed"),
        }

    return _mock_download_result


def _mock_validation_result_factory(fail_step: str):
    def _mock_validation_result(items: list[Any]) -> dict[str, Any]:
        validated = []
        for source in items:
            order = int(getattr(source, "order", 0) or 0)
            status = "valid"
            errors: list[str] = []
            error_type = None
            error_message = None
            if fail_step == "image-validation" and order == 1:
                status = "invalid"
                errors = ["forced_mock_validation_failure"]
                error_type = "mock_validation_failure"
                error_message = "forced mock image validation failure"
            validated.append(
                ValidatedImageResult(
                    role=getattr(source, "role", ""),
                    order=order,
                    source_url=getattr(source, "source_url", ""),
                    planned_filename=getattr(source, "planned_filename", ""),
                    relative_path=getattr(source, "relative_path", ""),
                    local_path=getattr(source, "local_path", ""),
                    local_exists=bool(getattr(source, "local_exists", False)),
                    download_status=getattr(source, "download_status", "downloaded"),
                    http_status=getattr(source, "http_status", 200),
                    content_type=getattr(source, "content_type", "image/jpeg"),
                    file_size=getattr(source, "file_size", 16),
                    width=1000,
                    height=1000,
                    sha256=f"mock-sha256-{order:02d}",
                    validation_status=status,
                    validation_errors=errors,
                    upload_status="not_uploaded",
                    rakuten_image_url=None,
                    error_type=error_type,
                    error_message=error_message,
                )
            )
        return {
            "items": validated,
            "valid_count": sum(1 for item in validated if item.validation_status == "valid"),
            "invalid_count": sum(1 for item in validated if item.validation_status == "invalid"),
            "failed_count": sum(1 for item in validated if item.validation_status == "failed"),
        }

    return _mock_validation_result


def _mock_image_client(asin: str, fail_step: str) -> RakutenImageClient:
    def _uploader(request):
        order = int((request.metadata or {}).get("order") or 0)
        role = str((request.metadata or {}).get("role") or "")
        if fail_step == "image-upload" and order == 1:
            return RakutenImageUploadResult(
                upload_status="failed",
                rakuten_image_url=None,
                request_summary={"filename": request.filename, "local_path": request.local_path},
                response_status=500,
                error_type="mock_upload_failure",
                error_message="forced mock image upload failure",
            )
        return RakutenImageUploadResult(
            upload_status="uploaded",
            rakuten_image_url=_planned_upload_url(asin, role, order),
            request_summary={"filename": request.filename, "local_path": request.local_path},
            response_status=201,
        )

    return RakutenImageClient(uploader=_uploader)


def _mock_item_client(fail_step: str) -> RakutenItemClient:
    def _sender(request):
        if fail_step == "item":
            return RakutenItemResult(
                success=False,
                management_number=request.management_number,
                http_status=500,
                response_body_summary={"mock": True, "request_id": f"mock-item-{request.management_number}", "result": "error"},
                retryable=False,
                request_summary={"url": request.url, "management_number": request.management_number},
                error_type="mock_item_failure",
                error_message="forced mock item failure",
            )
        return RakutenItemResult(
            success=True,
            management_number=request.management_number,
            http_status=200,
            response_body_summary={"mock": True, "request_id": f"mock-item-{request.management_number}", "result": "ok"},
            retryable=False,
            request_summary={"url": request.url, "management_number": request.management_number},
        )

    return RakutenItemClient(sender=_sender)


def _mock_inventory_client(fail_step: str) -> RakutenInventoryClient:
    def _sender(request):
        if fail_step == "inventory":
            return RakutenInventoryResult(
                success=False,
                management_number=request.management_number,
                http_status=500,
                response_body_summary={"mock": True, "request_id": f"mock-inventory-{request.management_number}", "result": "error"},
                retryable=False,
                request_summary={"url": request.url, "management_number": request.management_number},
                error_type="mock_inventory_failure",
                error_message="forced mock inventory failure",
            )
        return RakutenInventoryResult(
            success=True,
            management_number=request.management_number,
            http_status=200,
            response_body_summary={"mock": True, "request_id": f"mock-inventory-{request.management_number}", "result": "ok"},
            retryable=False,
            request_summary={"url": request.url, "management_number": request.management_number},
        )

    return RakutenInventoryClient(sender=_sender)


def _determine_validation_errors(preflight_result: dict[str, Any], dry_run_result: dict[str, Any], asin: str, management_number: str, approved: bool) -> list[str]:
    errors: list[str] = []
    if str(preflight_result.get("asin") or "") != asin:
        errors.append("preflight asin does not match argument")
    if str(dry_run_result.get("asin") or "") != asin:
        errors.append("dry-run asin does not match argument")
    if str(preflight_result.get("management_number") or "") != management_number:
        errors.append("preflight management_number does not match argument")
    if str(dry_run_result.get("management_number") or "") != management_number:
        errors.append("dry-run management_number does not match argument")
    if not approved:
        errors.append("--approved is required for mock execute")
    if str(preflight_result.get("preflight_status") or "") not in {"passed", "warning"}:
        errors.append("preflight_status must be passed or warning")
    if not bool(preflight_result.get("ready_for_mock_execute")):
        errors.append("ready_for_mock_execute must be true")
    if dry_run_result.get("listing_status") != "eligible":
        errors.append("listing_status must be eligible")
    if not dry_run_result.get("execution_allowed", False):
        errors.append("execution_allowed must be true")
    if list(dry_run_result.get("blocking_reasons") or []):
        errors.append("blocking_reasons must be empty")
    if list(dry_run_result.get("matched_forbidden_words") or []):
        errors.append("matched_forbidden_words must be empty")
    if list(dry_run_result.get("legacy_spacing_reviews") or []):
        errors.append("legacy_spacing_reviews must be empty")
    if list(preflight_result.get("text_validation_issues") or []):
        errors.append("text_validation_issues must be empty")
    if not isinstance(dry_run_result.get("item_payload"), dict):
        errors.append("item_payload is required")
    if not isinstance(dry_run_result.get("inventory_payload"), dict):
        errors.append("inventory_payload is required")
    if not isinstance(dry_run_result.get("image_download_plan"), dict):
        errors.append("image_download_plan is required")
    return errors


def _build_image_results(execute_result: dict[str, Any]) -> list[dict[str, Any]]:
    download_items = {
        int(item.get("order") or 0): item
        for item in list((execute_result.get("download_result") or {}).get("items") or [])
        if isinstance(item, dict)
    }
    validation_items = {
        int(item.get("order") or 0): item
        for item in list((execute_result.get("validation_result") or {}).get("items") or [])
        if isinstance(item, dict)
    }
    upload_items = list(execute_result.get("image_upload_results") or [])
    upload_by_order: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(upload_items, start=1):
        if isinstance(item, dict):
            upload_by_order[index] = item

    orders = sorted(set(download_items) | set(validation_items) | set(upload_by_order))
    results: list[dict[str, Any]] = []
    for order in orders:
        download = download_items.get(order, {})
        validation = validation_items.get(order, {})
        upload = upload_by_order.get(order, {})
        results.append(
            {
                "source_url": download.get("source_url") or validation.get("source_url"),
                "role": download.get("role") or validation.get("role"),
                "order": order,
                "planned_filename": download.get("planned_filename") or validation.get("planned_filename"),
                "planned_path": download.get("relative_path") or validation.get("relative_path"),
                "download_status": download.get("download_status"),
                "validation_status": validation.get("validation_status"),
                "upload_status": upload.get("upload_status"),
                "mocked_uploaded_url": upload.get("rakuten_image_url"),
                "local_exists": download.get("local_exists"),
                "validation_errors": validation.get("validation_errors") or [],
                "error_type": validation.get("error_type") or download.get("error_type") or upload.get("error_type"),
                "error_message": validation.get("error_message") or download.get("error_message") or upload.get("error_message"),
            }
        )
    return results


def _extract_request_summary(result: dict[str, Any], key: str) -> dict[str, Any]:
    payload = result.get(key)
    if not isinstance(payload, dict):
        return {}
    return sanitize_for_output(payload.get("request_summary") or {})


def _extract_response_summary(result: dict[str, Any], key: str) -> dict[str, Any]:
    payload = result.get(key)
    if not isinstance(payload, dict):
        return {}
    return {
        "status_code": payload.get("http_status"),
        "success": bool(payload.get("success")),
        "mock": bool((payload.get("response_body_summary") or {}).get("mock")),
        "request_id": (payload.get("response_body_summary") or {}).get("request_id"),
        "error_type": payload.get("error_type"),
        "error_message": payload.get("error_message"),
    }


def _build_item_request_summary(dry_run_result: dict[str, Any], execute_result: dict[str, Any]) -> dict[str, Any]:
    executed_item_payload = execute_result.get("executed_item_payload") or dry_run_result.get("item_payload") or {}
    if not isinstance(executed_item_payload, dict):
        return {}
    variants = executed_item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return {}
    variant_key = str(next(iter(variants.keys())) or "").strip()
    variant = next(iter(variants.values()))
    if not isinstance(variant, dict):
        variant = {}
    attributes = list(variant.get("attributes") or [])
    representative_color = ""
    for attribute in attributes:
        if isinstance(attribute, dict) and str(attribute.get("name") or "") == "代表カラー":
            representative_color = str(attribute.get("value") or "")
            break
    return {
        "method": "PUT",
        "itemNumber": executed_item_payload.get("itemNumber"),
        "management_number": dry_run_result.get("management_number"),
        "title": executed_item_payload.get("title"),
        "genreId": executed_item_payload.get("genreId"),
        "standardPrice": variant.get("standardPrice"),
        "attributes": attributes,
        "representative_color": representative_color,
        "image_urls": [item.get("location") for item in list(executed_item_payload.get("images") or []) if isinstance(item, dict)],
        "variant_key": variant_key,
        "url": (_extract_request_summary(execute_result, "item_result") or {}).get("url"),
    }


def _build_item_request_summary(dry_run_result: dict[str, Any], execute_result: dict[str, Any]) -> dict[str, Any]:
    executed_item_payload = execute_result.get("executed_item_payload") or dry_run_result.get("item_payload") or {}
    if not isinstance(executed_item_payload, dict):
        return {}
    variants = executed_item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return {}
    variant_key = str(next(iter(variants.keys())) or "").strip()
    variant = next(iter(variants.values()))
    if not isinstance(variant, dict):
        variant = {}
    attributes = list(variant.get("attributes") or [])

    def first_value(attribute: dict[str, Any]) -> str:
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            return next((str(item or "") for item in raw_values if str(item or "").strip()), "")
        return str(attribute.get("value") or "")

    representative_color = ""
    fallback_value = ""
    for attribute in attributes:
        if not isinstance(attribute, dict):
            continue
        value = first_value(attribute)
        if value and not fallback_value:
            fallback_value = value
        if "カラー" in str(attribute.get("name") or ""):
            representative_color = value
            break
    if not representative_color and attributes:
        last_attribute = attributes[-1]
        if isinstance(last_attribute, dict):
            representative_color = first_value(last_attribute) or fallback_value

    return {
        "method": "PUT",
        "itemNumber": executed_item_payload.get("itemNumber"),
        "management_number": dry_run_result.get("management_number"),
        "title": executed_item_payload.get("title"),
        "genreId": executed_item_payload.get("genreId"),
        "standardPrice": variant.get("standardPrice"),
        "attributes": attributes,
        "representative_color": representative_color,
        "image_urls": [item.get("location") for item in list(executed_item_payload.get("images") or []) if isinstance(item, dict)],
        "variant_key": variant_key,
        "url": (_extract_request_summary(execute_result, "item_result") or {}).get("url"),
    }


def _build_item_request_summary(dry_run_result: dict[str, Any], execute_result: dict[str, Any]) -> dict[str, Any]:
    executed_item_payload = execute_result.get("executed_item_payload") or dry_run_result.get("item_payload") or {}
    if not isinstance(executed_item_payload, dict):
        return {}
    variants = executed_item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return {}
    variant_key = str(next(iter(variants.keys())) or "").strip()
    variant = next(iter(variants.values()))
    if not isinstance(variant, dict):
        variant = {}
    attributes = list(variant.get("attributes") or [])
    representative_color = ""
    for attribute in attributes:
        if not isinstance(attribute, dict):
            continue
        attribute_name = str(attribute.get("name") or "")
        if "カラー" not in attribute_name:
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            representative_color = next((str(item or "") for item in raw_values if str(item or "").strip()), "")
        else:
            representative_color = str(attribute.get("value") or "")
        break
    return {
        "method": "PUT",
        "itemNumber": executed_item_payload.get("itemNumber"),
        "management_number": dry_run_result.get("management_number"),
        "title": executed_item_payload.get("title"),
        "genreId": executed_item_payload.get("genreId"),
        "standardPrice": variant.get("standardPrice"),
        "attributes": attributes,
        "representative_color": representative_color,
        "image_urls": [item.get("location") for item in list(executed_item_payload.get("images") or []) if isinstance(item, dict)],
        "variant_key": variant_key,
        "url": (_extract_request_summary(execute_result, "item_result") or {}).get("url"),
    }


def _build_inventory_request_summary(dry_run_result: dict[str, Any], execute_result: dict[str, Any]) -> dict[str, Any]:
    inventory_payload = dry_run_result.get("inventory_payload") or {}
    if not isinstance(inventory_payload, dict):
        return {}
    request = build_inventory_request(str(dry_run_result.get("management_number") or ""), inventory_payload, {})
    return {
        "method": "PUT",
        "management_number": request.management_number,
        "variant_id": request.variant_id,
        "variantPath": inventory_payload.get("variantPath") or {},
        "quantity": request.payload.get("quantity"),
        "operationLeadTime": request.payload.get("operationLeadTime"),
        "shipFromIds": request.payload.get("shipFromIds"),
        "url": (_extract_request_summary(execute_result, "inventory_result") or {}).get("url") or request.url,
    }


def _map_final_status(validation_errors: list[str], execute_result: dict[str, Any], fail_step: str) -> str:
    if validation_errors:
        return VALIDATION_FAILED
    if fail_step == "image-download":
        return IMAGE_DOWNLOAD_FAILED if execute_result.get("execute_status") == "image_failed" else execute_result.get("execute_status") or VALIDATION_FAILED
    if fail_step == "image-validation":
        return IMAGE_VALIDATION_FAILED if execute_result.get("execute_status") == "image_failed" else execute_result.get("execute_status") or VALIDATION_FAILED
    if fail_step == "image-upload":
        return IMAGE_UPLOAD_FAILED if execute_result.get("execute_status") == "image_failed" else execute_result.get("execute_status") or VALIDATION_FAILED
    if execute_result.get("execute_status") == "item_failed":
        return ITEM_FAILED
    if execute_result.get("execute_status") == "inventory_failed":
        return INVENTORY_FAILED
    if execute_result.get("execute_status") == "completed":
        return COMPLETED
    return str(execute_result.get("execute_status") or VALIDATION_FAILED)


def build_mock_execute_result(
    dry_run_result: dict[str, Any],
    preflight_result: dict[str, Any],
    *,
    asin: str,
    management_number: str,
    approved: bool,
    fail_step: str = "",
) -> dict[str, Any]:
    validation_errors = _determine_validation_errors(preflight_result, dry_run_result, asin, management_number, approved)
    execution_sequence = [
        "preflight validation",
        "image download mock",
        "image validation mock",
        "image upload mock",
        "item API mock",
        "inventory API mock",
        "final result",
    ]
    base = {
        "mode": "mock_execute",
        "asin": asin,
        "store_code": dry_run_result.get("store_code"),
        "management_number": management_number,
        "approved": approved,
        "preflight_status": preflight_result.get("preflight_status"),
        "execution_sequence": execution_sequence,
        "image_results": [],
        "item_request_summary": {},
        "item_response": {},
        "inventory_request_summary": {},
        "inventory_response": {},
        "final_status": VALIDATION_FAILED if validation_errors else "",
        "item_success": False,
        "inventory_success": False,
        "warnings": list(preflight_result.get("warnings") or []),
        "errors": list(validation_errors),
        "external_actions_performed": False,
        "mock_only": True,
        "secrets_exposed": False,
    }
    if validation_errors:
        return base

    MOCK_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    execute_result = execute_listing(
        ExecuteListingRequest(
            dry_run_result=dry_run_result,
            execute=True,
            approved=True,
            asin=asin,
            management_number=management_number,
            # Mock downloaders return metadata only, so a stable workspace path
            # is sufficient and avoids creating temporary directories on Windows.
            output_root=MOCK_TEMP_ROOT,
        ),
        image_downloader=_mock_download_result_factory(fail_step),
        image_validator=_mock_validation_result_factory(fail_step),
        image_client=_mock_image_client(asin, fail_step),
        item_client=_mock_item_client(fail_step),
        inventory_client=_mock_inventory_client(fail_step),
    )

    jsonable = sanitize_for_output(to_jsonable(execute_result))
    base["image_results"] = _build_image_results(jsonable)
    base["item_request_summary"] = _build_item_request_summary(dry_run_result, jsonable)
    base["item_response"] = _extract_response_summary(jsonable, "item_result")
    base["inventory_request_summary"] = _build_inventory_request_summary(dry_run_result, jsonable)
    base["inventory_response"] = _extract_response_summary(jsonable, "inventory_result")
    base["errors"] = list(jsonable.get("errors") or [])
    base["final_status"] = _map_final_status(validation_errors, jsonable, fail_step)
    base["item_success"] = bool((jsonable.get("item_result") or {}).get("success"))
    base["inventory_success"] = bool((jsonable.get("inventory_result") or {}).get("success"))
    base["raw_execute_result"] = jsonable
    return base


def _build_item_request_summary(dry_run_result: dict[str, Any], execute_result: dict[str, Any]) -> dict[str, Any]:
    executed_item_payload = execute_result.get("executed_item_payload") or dry_run_result.get("item_payload") or {}
    if not isinstance(executed_item_payload, dict):
        return {}
    variants = executed_item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return {}
    variant_key = str(next(iter(variants.keys())) or "").strip()
    variant = next(iter(variants.values()))
    if not isinstance(variant, dict):
        variant = {}
    attributes = list(variant.get("attributes") or [])
    representative_color = ""
    for attribute in attributes:
        if not isinstance(attribute, dict):
            continue
        if str(attribute.get("name") or "") != "莉｣陦ｨ繧ｫ繝ｩ繝ｼ":
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            representative_color = next((str(item or "") for item in raw_values if str(item or "").strip()), "")
        else:
            representative_color = str(attribute.get("value") or "")
        break
    return {
        "method": "PUT",
        "itemNumber": executed_item_payload.get("itemNumber"),
        "management_number": dry_run_result.get("management_number"),
        "title": executed_item_payload.get("title"),
        "genreId": executed_item_payload.get("genreId"),
        "standardPrice": variant.get("standardPrice"),
        "attributes": attributes,
        "representative_color": representative_color,
        "image_urls": [item.get("location") for item in list(executed_item_payload.get("images") or []) if isinstance(item, dict)],
        "variant_key": variant_key,
        "url": (_extract_request_summary(execute_result, "item_result") or {}).get("url"),
    }
