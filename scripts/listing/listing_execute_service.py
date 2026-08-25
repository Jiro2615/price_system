from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.listing.image_downloader import download_image_plan
from scripts.listing.image_validator import validate_downloaded_images
from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.rakuten_image_client import RakutenImageClient, build_upload_request_from_validation
from scripts.listing.rakuten_inventory_client import RakutenInventoryClient, build_inventory_request
from scripts.listing.rakuten_item_client import RakutenItemClient, build_item_request
from scripts.listing.rakuten_marketplace_policy import is_cosmetics_category
from scripts.listing.rakuten_shop_category_client import (
    DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
    RakutenShopCategoryClient,
    build_mapping_payload,
    response_json,
)


IMAGE_UPLOAD_WAIT_SECONDS = 1.5


@dataclass
class ExecuteListingRequest:
    dry_run_result: dict[str, Any]
    execute: bool = False
    approved: bool = False
    asin: str = ""
    management_number: str = ""
    output_root: Path = Path("output/listing_images")
    image_headers: dict[str, str] | None = None
    item_headers: dict[str, str] | None = None
    inventory_headers: dict[str, str] | None = None
    resume_after_image_upload: bool = False
    resume_after_item_upsert: bool = False
    content_refresh: bool = False


def _payload_hash(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    normalized = json.dumps(to_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _copy_item_payload_with_image_urls(item_payload: dict[str, Any], rakuten_image_urls: list[str]) -> dict[str, Any]:
    patched = copy.deepcopy(item_payload)
    patched["images"] = [{"type": "CABINET", "location": url} for url in rakuten_image_urls]
    return patched


def _build_existing_rakuten_image_locations(dry_run_result: dict[str, Any]) -> list[str]:
    plan = dict(dry_run_result.get("image_download_plan") or {})
    plan_items = list(plan.get("items") or [])
    locations = [
        str(item.get("item_location") or "").strip()
        for item in plan_items
        if isinstance(item, dict) and str(item.get("item_location") or "").strip()
    ]
    if locations:
        return locations

    store_settings = dict(dry_run_result.get("store_settings") or {})
    cabinet = dict(store_settings.get("cabinet") or {})
    folder_path = str(cabinet.get("folder_path") or "").replace("\\", "/").strip().strip("/")
    management_candidates = dict(to_jsonable(dry_run_result.get("management_number_candidates")) or {})
    image_base_name = str(
        management_candidates.get("legacy_candidate")
        or dry_run_result.get("management_number")
        or dry_run_result.get("asin")
        or ""
    ).strip()
    image_urls = list(dry_run_result.get("image_urls") or [])
    if not folder_path or not image_base_name or not image_urls:
        return []
    return [f"/{folder_path}/{image_base_name}_{index}.jpg" for index in range(1, len(image_urls) + 1)]


def _expected_image_count(dry_run_result: dict[str, Any]) -> int:
    plan = dict(dry_run_result.get("image_download_plan") or {})
    plan_items = [item for item in list(plan.get("items") or []) if isinstance(item, dict)]
    if plan_items:
        return len(plan_items)
    return len(list(dry_run_result.get("image_urls") or []))


def _build_upload_metadata(dry_run_result: dict[str, Any], item: Any) -> dict[str, Any]:
    store_settings = dict(dry_run_result.get("store_settings") or {})
    cabinet = dict(store_settings.get("cabinet") or {})
    image_plan = dict(dry_run_result.get("image_download_plan") or {})
    plan_items = list(image_plan.get("items") or [])
    match = None
    order = getattr(item, "order", None)
    source_url = str(getattr(item, "source_url", "") or "")
    for candidate in plan_items:
        if not isinstance(candidate, dict):
            continue
        if order is not None and int(candidate.get("order") or 0) == int(order):
            match = candidate
            break
        if source_url and str(candidate.get("source_url") or "") == source_url:
            match = candidate
            break
    management_candidates = dict(to_jsonable(dry_run_result.get("management_number_candidates")) or {})
    image_base_name = str(
        management_candidates.get("legacy_candidate")
        or dry_run_result.get("management_number")
        or dry_run_result.get("asin")
        or ""
    ).strip()
    safe_file_name = f"{image_base_name}_{int(order)}.jpg" if image_base_name and order is not None else ""
    file_name = str(safe_file_name or (match or {}).get("planned_filename") or getattr(item, "planned_filename", None) or "").strip()
    cabinet_folder_path = str(cabinet.get("folder_path") or "").replace("\\", "/").strip().strip("/")
    item_location = (match or {}).get("item_location")
    if not item_location and cabinet_folder_path and file_name:
        item_location = f"/{cabinet_folder_path}/{file_name}"
    elif item_location and file_name and cabinet_folder_path:
        item_location = f"/{cabinet_folder_path}/{file_name}"
    return {
        "upload_endpoint": "https://api.rms.rakuten.co.jp/es/1.0/cabinet/file/insert",
        "shop_url": cabinet.get("shop_url"),
        "cabinet_folder_id": cabinet.get("folder_id"),
        "cabinet_folder_path": cabinet_folder_path or cabinet.get("folder_path"),
        "item_location": item_location,
        "file_name": file_name or getattr(item, "planned_filename", None),
        "file_path": file_name or getattr(item, "planned_filename", None),
        "order": order,
        "role": getattr(item, "role", None),
        "sha256": getattr(item, "sha256", None),
    }


def _base_result(request: ExecuteListingRequest, dry_run_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "asin": dry_run_result.get("asin"),
        "store_code": dry_run_result.get("store_code"),
        "listing_status": dry_run_result.get("listing_status"),
        "management_number": dry_run_result.get("management_number"),
        "execute_requested": request.execute,
        "approved": request.approved,
        "execute_status": "not_started",
        "final_state": "not_started",
        "errors": [],
        "warnings": [],
        "download_result": None,
        "validation_result": None,
        "image_upload_results": [],
        "item_result": None,
        "shop_category_result": None,
        "inventory_result": None,
        "image_urls_before": list(dry_run_result.get("image_urls") or []),
        "rakuten_image_urls_after": [],
        "original_item_payload_hash": _payload_hash(dry_run_result.get("item_payload")),
        "executed_item_payload_hash": None,
        "executed_item_payload": None,
    }


def _fail(result: dict[str, Any], *, status: str, message: str, final_state: str = "blocked") -> dict[str, Any]:
    result["execute_status"] = status
    result["final_state"] = final_state
    result["errors"].append(message)
    return result


def _is_download_success(item: Any) -> bool:
    return (
        getattr(item, "download_status", None) in {"downloaded", "reused"}
        and bool(getattr(item, "local_exists", False))
        and bool(str(getattr(item, "local_path", "") or "").strip())
    )


def _is_validation_success(item: Any) -> bool:
    return (
        getattr(item, "validation_status", None) == "valid"
        and not list(getattr(item, "validation_errors", []) or [])
        and getattr(item, "error_type", None) in (None, "")
    )


def _summarize_image_items(items: list[Any], *, stage: str) -> str:
    parts: list[str] = []
    for item in items:
        parts.append(
            (
                f"order={getattr(item, 'order', None)}"
                f", status={getattr(item, stage, None)}"
                f", local_exists={getattr(item, 'local_exists', None)}"
                f", local_path={getattr(item, 'local_path', None)}"
                f", errors={list(getattr(item, 'validation_errors', []) or [])}"
                f", error_type={getattr(item, 'error_type', None)}"
                f", error_message={getattr(item, 'error_message', None)}"
            )
        )
    return "; ".join(parts)


def _classify_upload_failure(upload: Any) -> str:
    status_code = getattr(upload, "response_status", None)
    error_message = str(getattr(upload, "error_message", None) or "")
    lowered = error_message.lower()
    if status_code == 400 and "request data is wrong format" in lowered:
        return "image upload failed: request data is wrong format"
    if status_code == 403 and "qpslimit" in lowered:
        return "image upload failed: QPSLimit"
    return f"image upload failed: status={status_code}, error={error_message or getattr(upload, 'error_type', None)}"


def _requires_cosmetics_shop_category(dry_run_result: dict[str, Any], store_code: str) -> bool:
    """Return whether this listing uses LifeForest's cosmetics display category.

    The established compliance classifier covers Amazon's Beauty hierarchy,
    while an explicit ``医薬部外品`` marker covers products that are not
    consistently placed below that hierarchy in Keepa.
    """
    if str(store_code or "").strip().lower() != "rakuten_2":
        return False
    keepa = dry_run_result.get("keepa_result") or {}
    category_tree = keepa.get("category_tree") if isinstance(keepa, dict) else getattr(keepa, "category_tree", None)
    if is_cosmetics_category(category_tree):
        return True
    item_payload = dry_run_result.get("item_payload") or {}
    title = str(item_payload.get("title") or "") if isinstance(item_payload, dict) else ""
    description = str(item_payload.get("descriptionForPC") or "") if isinstance(item_payload, dict) else ""
    return "医薬部外品" in f"{title}\n{description}"


def _assign_cosmetics_shop_category(
    *,
    client: RakutenShopCategoryClient,
    management_number: str,
    store_code: str,
) -> dict[str, Any]:
    """Add the cosmetics shop category without replacing existing mappings."""
    current_result = client.get_item_mapping(management_number, store_code=store_code)
    current = response_json(current_result)
    if not current_result.success:
        return {
            "success": False,
            "stage": "get_current_mapping",
            "target_category_id": DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
            "error": current_result.error_message or "Category API mapping read failed",
            "request_summary": current_result.request_summary,
        }

    current_ids = [str(value) for value in list(current.get("categoryIds") or [])]
    if DEFAULT_COSMETICS_SHOP_CATEGORY_ID in current_ids:
        return {
            "success": True,
            "skipped": True,
            "reason": "already_assigned",
            "target_category_id": DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
            "category_ids": current_ids,
        }

    target_result = client.get_category(DEFAULT_COSMETICS_SHOP_CATEGORY_ID, store_code=store_code)
    target = response_json(target_result)
    if not target_result.success:
        return {
            "success": False,
            "stage": "get_target_category",
            "target_category_id": DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
            "error": target_result.error_message or "Category API category read failed",
            "request_summary": target_result.request_summary,
        }
    try:
        payload = build_mapping_payload(
            current,
            target_category_id=DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
            target_is_plural=str(((target.get("categoryFeatures") or {}).get("categoryPageViewMode") or "")).upper() == "PLURAL",
        )
    except ValueError as exc:
        return {
            "success": False,
            "stage": "build_mapping",
            "target_category_id": DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
            "error": str(exc),
            "category_ids": current_ids,
        }

    put_result = client.put_item_mapping(management_number, payload, store_code=store_code)
    return {
        "success": put_result.success,
        "stage": "put_mapping",
        "target_category_id": DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
        "category_ids": payload.get("categoryIds") or [],
        "main_plural_category_id": payload.get("mainPluralCategoryId"),
        "http_status": put_result.http_status,
        "error": put_result.error_message,
        "request_summary": put_result.request_summary,
    }


def execute_listing(
    request: ExecuteListingRequest,
    *,
    http_get: Callable[[str, float, bool], Any] | None = None,
    image_downloader: Callable[..., dict[str, Any]] = download_image_plan,
    image_validator: Callable[..., dict[str, Any]] = validate_downloaded_images,
    image_client: RakutenImageClient | None = None,
    item_client: RakutenItemClient | None = None,
    inventory_client: RakutenInventoryClient | None = None,
    shop_category_client: RakutenShopCategoryClient | None = None,
) -> dict[str, Any]:
    dry_run_result = dict(request.dry_run_result)
    result = _base_result(request, dry_run_result)

    asin = str(dry_run_result.get("asin") or "").strip().upper()
    store_code = str(dry_run_result.get("store_code") or "").strip()
    management_number = str(dry_run_result.get("management_number") or "").strip()
    item_payload = dry_run_result.get("item_payload")
    inventory_payload = dry_run_result.get("inventory_payload")
    blocking_reasons = list(dry_run_result.get("blocking_reasons") or [])
    legacy_spacing_reviews = list(dry_run_result.get("legacy_spacing_reviews") or [])

    if not request.execute:
        return _fail(result, status="not_requested", message="--execute is required")
    if not request.approved:
        return _fail(result, status="approval_required", message="human approval is required")
    if str(request.asin or asin).strip().upper() != asin:
        return _fail(result, status="validation_failed", message="ASIN does not match dry-run result")
    if request.management_number and str(request.management_number).strip() != management_number:
        return _fail(result, status="validation_failed", message="management_number does not match dry-run result")
    if dry_run_result.get("listing_status") != "eligible":
        return _fail(result, status="validation_failed", message="listing_status must be eligible")
    if not dry_run_result.get("execution_allowed", False):
        return _fail(result, status="validation_failed", message="dry-run result is not execution_allowed")
    if blocking_reasons:
        return _fail(result, status="validation_failed", message=f"blocking_reasons must be empty: {blocking_reasons}")
    if legacy_spacing_reviews:
        return _fail(
            result,
            status="validation_failed",
            message="legacy spacing replacements require migration review before execute",
        )
    if not management_number:
        return _fail(result, status="validation_failed", message="management_number is required")
    if not isinstance(item_payload, dict) or not isinstance(inventory_payload, dict):
        return _fail(result, status="validation_failed", message="item_payload and inventory_payload are required")

    if request.resume_after_image_upload or request.resume_after_item_upsert:
        rakuten_image_urls = _build_existing_rakuten_image_locations(dry_run_result)
        expected_image_count = _expected_image_count(dry_run_result)
        resume_reason = "resume_after_item_upsert" if request.resume_after_item_upsert else "resume_after_image_upload"
        result["download_result"] = {"skipped": True, "reason": resume_reason}
        result["validation_result"] = {"skipped": True, "reason": resume_reason}
        result["image_upload_results"] = [
            {
                "upload_status": "reused",
                "rakuten_image_url": location,
                "order": index,
            }
            for index, location in enumerate(rakuten_image_urls, start=1)
        ]
        if len(rakuten_image_urls) != expected_image_count:
            return _fail(
                result,
                status="image_failed",
                message=f"{resume_reason} requires {expected_image_count} existing image locations, got {len(rakuten_image_urls)}",
                final_state="partial_failure",
            )
    else:
        download_result = image_downloader(
            dry_run_result.get("image_download_plan"),
            output_root=Path(request.output_root),
            http_get=http_get,
        )
        result["download_result"] = sanitize_for_output(to_jsonable(download_result))
        downloaded_items = list(download_result.get("items") or [])
        if not downloaded_items or any(not _is_download_success(item) for item in downloaded_items):
            return _fail(
                result,
                status="image_failed",
                message=f"image download failed: {_summarize_image_items(downloaded_items, stage='download_status')}",
                final_state="partial_failure",
            )

        validation_result = image_validator(downloaded_items)
        result["validation_result"] = sanitize_for_output(to_jsonable(validation_result))
        validated_items = list(validation_result.get("items") or [])
        if not validated_items or any(not _is_validation_success(item) for item in validated_items):
            return _fail(
                result,
                status="image_failed",
                message=f"image validation failed: {_summarize_image_items(validated_items, stage='validation_status')}",
                final_state="partial_failure",
            )

        image_client = image_client or RakutenImageClient()
        upload_results = []
        for index, item in enumerate(validated_items):
            upload_request = build_upload_request_from_validation(item, store_code=store_code, headers=request.image_headers)
            metadata = dict(upload_request.metadata or {})
            metadata.update(_build_upload_metadata(dry_run_result, item))
            upload_request.metadata = metadata
            destination_file_name = str(metadata.get("file_name") or "").strip()
            if destination_file_name:
                upload_request.filename = destination_file_name
            upload_result = image_client.upload_image(upload_request)
            upload_results.append(upload_result)
            if upload_result.upload_status != "uploaded":
                result["image_upload_results"] = sanitize_for_output(to_jsonable(upload_results))
                result["execute_status"] = "image_uploaded"
                return _fail(result, status="image_failed", message=_classify_upload_failure(upload_result), final_state="partial_failure")
            if index < len(validated_items) - 1:
                time.sleep(IMAGE_UPLOAD_WAIT_SECONDS)
        result["image_upload_results"] = sanitize_for_output(to_jsonable(upload_results))

        rakuten_image_urls = [str(upload.rakuten_image_url) for upload in upload_results if upload.rakuten_image_url]
        if not rakuten_image_urls:
            return _fail(result, status="image_failed", message="rakuten image URLs were not returned", final_state="partial_failure")

    executed_item_payload = _copy_item_payload_with_image_urls(item_payload, rakuten_image_urls)
    item_request = build_item_request(management_number, executed_item_payload, request.item_headers or {}, store_code=store_code)
    executed_item_payload = item_request.payload
    result["rakuten_image_urls_after"] = rakuten_image_urls
    result["executed_item_payload"] = sanitize_for_output(to_jsonable(executed_item_payload))
    result["executed_item_payload_hash"] = _payload_hash(executed_item_payload)
    result["execute_status"] = "image_uploaded"

    if request.resume_after_item_upsert:
        result["item_result"] = {
            "success": True,
            "management_number": management_number,
            "http_status": None,
            "skipped": True,
            "reason": "resume_after_item_upsert",
            "request_summary": {
                "management_number": management_number,
                "payload": sanitize_for_output(to_jsonable(executed_item_payload)),
            },
        }
    else:
        item_client = item_client or RakutenItemClient()
        item_result = item_client.put_item(item_request)
        result["item_result"] = sanitize_for_output(to_jsonable(item_result))
        if not item_result.success:
            return _fail(result, status="item_failed", message=item_result.error_message or "item API failed", final_state="partial_failure")

    result["execute_status"] = "item_succeeded"

    if request.content_refresh:
        result["inventory_result"] = {
            "success": True,
            "skipped": True,
            "reason": "content_refresh does not change inventory",
        }
        result["execute_status"] = "completed"
        result["final_state"] = "completed"
        return result

    # Shop display categories are managed by Category API, not Item API
    # ``genreId``.  A category failure must not cause a second Item API write:
    # the item has already been registered, so retain a visible warning and
    # continue the inventory registration.
    if _requires_cosmetics_shop_category(dry_run_result, store_code):
        try:
            shop_category_client = shop_category_client or RakutenShopCategoryClient()
            category_result = _assign_cosmetics_shop_category(
                client=shop_category_client,
                management_number=management_number,
                store_code=store_code,
            )
            result["shop_category_result"] = sanitize_for_output(to_jsonable(category_result))
            if not category_result.get("success"):
                result["warnings"].append(
                    "化粧品ショップカテゴリの設定に失敗しました: "
                    + str(category_result.get("error") or "Category API error")
                )
        except Exception as exc:
            result["shop_category_result"] = {
                "success": False,
                "target_category_id": DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
                "error": str(exc),
            }
            result["warnings"].append(f"化粧品ショップカテゴリの設定に失敗しました: {exc}")

    inventory_client = inventory_client or RakutenInventoryClient()
    inventory_request = build_inventory_request(management_number, inventory_payload, request.inventory_headers or {}, store_code=store_code)
    inventory_result = inventory_client.put_inventory(inventory_request)
    result["inventory_result"] = sanitize_for_output(to_jsonable(inventory_result))
    if not inventory_result.success:
        result["execute_status"] = "inventory_failed"
        result["final_state"] = "partial_failure"
        result["errors"].append(inventory_result.error_message or "inventory API failed")
        return result

    result["execute_status"] = "completed"
    result["final_state"] = "completed"
    return result
