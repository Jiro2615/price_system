from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.listing.image_downloader import download_image_plan, requests_http_get
from scripts.listing.image_validator import validate_downloaded_images
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.preflight_service import load_json
from scripts.listing.rakuten_image_client import RakutenImageClient
from scripts.listing.rakuten_inventory_client import RakutenInventoryClient
from scripts.listing.rakuten_item_client import RakutenItemClient
from scripts.listing.real_readiness_service import save_execution_history_stub
from scripts.listing.rakuten_transport import build_rakuten_auth_headers


@dataclass
class RealExecuteRequest:
    readiness_json: Path
    dry_run_json: Path
    preflight_json: Path
    mock_result_json: Path
    asin: str
    management_number: str
    store: str
    execute: bool = False
    approved: bool = False
    confirm_real_api: bool = False
    confirm_asin: str = ""
    confirm_management_number: str = ""
    confirm_store: str = ""
    allow_live_transport: bool = False
    output_root: Path = Path("output/listing_images")
    image_headers: dict[str, str] | None = None
    item_headers: dict[str, str] | None = None
    inventory_headers: dict[str, str] | None = None
    manual_image_cleanup_completed: bool = False
    resume_after_image_upload: bool = False
    resume_after_item_upsert: bool = False


def _validate_readiness_inputs(
    request: RealExecuteRequest,
    readiness_result: dict[str, Any],
    dry_run_result: dict[str, Any],
    preflight_result: dict[str, Any],
    mock_result: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            reasons.append(reason)

    require(str(readiness_result.get("asin") or "") == request.asin, "readiness asin mismatch")
    require(str(readiness_result.get("store_code") or "") == request.store, "readiness store mismatch")
    require(str(readiness_result.get("management_number") or "") == request.management_number, "readiness management_number mismatch")
    require(str(dry_run_result.get("asin") or "") == request.asin, "dry-run asin mismatch")
    require(str(dry_run_result.get("store_code") or "") == request.store, "dry-run store mismatch")
    require(str(dry_run_result.get("management_number") or "") == request.management_number, "dry-run management_number mismatch")
    require(str(preflight_result.get("preflight_status") or "") in {"passed", "warning"}, "preflight_status must be passed or warning")
    require(str(mock_result.get("final_status") or "") == "completed", "mock_final_status must be completed")
    require(str(readiness_result.get("readiness_status") or "") in {"ready", "warning"}, "readiness_status must be ready or warning")
    require(bool(readiness_result.get("ready_for_real_execute")) is True, "ready_for_real_execute must be true")
    require(list(readiness_result.get("unresolved_specifications") or []) == [], "unresolved_specifications must be empty")
    require(bool(readiness_result.get("real_execute_spec_ready")) is True, "real_execute_spec_ready must be true")
    require(bool(readiness_result.get("human_confirmation_required")) is False, "human_confirmation_required must be false")
    require(bool((readiness_result.get("duplicate_execution_guard") or {}).get("duplicate_blocked")) is False, "duplicate execution guard must not be blocked")
    require(bool(readiness_result.get("secrets_exposed")) is False, "secrets_exposed must be false")
    require(bool(readiness_result.get("external_actions_performed")) is False, "external_actions_performed must be false")
    require(isinstance(dry_run_result.get("item_payload"), dict), "item_payload must be present")
    require(isinstance(dry_run_result.get("inventory_payload"), dict), "inventory_payload must be present")
    return reasons


def _validate_execute_guards(request: RealExecuteRequest) -> list[str]:
    reasons: list[str] = []

    if not request.execute:
        reasons.append("--execute is required for external processing")
        return reasons

    if not request.approved:
        reasons.append("--approved is required")
    if not request.confirm_real_api:
        reasons.append("--confirm-real-api is required")
    if str(request.confirm_asin or "").strip() != request.asin:
        reasons.append("--confirm-asin must match the target ASIN")
    if str(request.confirm_management_number or "").strip() != request.management_number:
        reasons.append("--confirm-management-number must match the target management number")
    if str(request.confirm_store or "").strip() != request.store:
        reasons.append("--confirm-store must match the target store")
    return reasons


def _build_base_result(request: RealExecuteRequest) -> dict[str, Any]:
    return {
        "mode": "real_execute",
        "asin": request.asin,
        "store_code": request.store,
        "management_number": request.management_number,
        "execute_requested": request.execute,
        "approved": request.approved,
        "confirm_real_api": request.confirm_real_api,
        "confirm_asin": request.confirm_asin,
        "confirm_management_number": request.confirm_management_number,
        "confirm_store": request.confirm_store,
        "allow_live_transport": request.allow_live_transport,
        "final_status": "blocked",
        "would_execute": False,
        "external_actions_performed": False,
        "secrets_exposed": False,
        "blocking_reasons": [],
        "warnings": [],
        "transport_dry_check": {
            "active": not request.allow_live_transport,
            "transport_ready": False,
            "reason": None,
        },
        "execution_sequence": [
            "execution_history start write",
            "image upload planned images",
            "items.upsert",
            "inventory upsert",
            "execution_history final write",
        ],
        "execution_history": {
            "written": False,
            "history_path": None,
        },
        "raw_execute_result": None,
    }


def _build_transport_ready_summary(store_code: str = "") -> dict[str, Any]:
    try:
        __import__("requests")
        requests_available = True
        requests_reason = None
    except Exception as exc:
        requests_available = False
        requests_reason = str(exc)

    try:
        build_rakuten_auth_headers(store_code=store_code)
        auth_configured = True
        auth_reason = None
    except Exception as exc:
        auth_configured = False
        auth_reason = str(exc)

    return {
        "requests_available": requests_available,
        "auth_configured": auth_configured,
        "ready": requests_available and auth_configured,
        "reason": auth_reason or requests_reason,
    }


def _expected_image_count(dry_run_result: dict[str, Any]) -> int:
    image_plan = dict(dry_run_result.get("image_download_plan") or {})
    plan_items = [item for item in list(image_plan.get("items") or []) if isinstance(item, dict)]
    if plan_items:
        return len(plan_items)
    return len(list(dry_run_result.get("image_urls") or []))


def _current_history_block_reason(
    history_path: Path | None,
    *,
    expected_image_count: int = 0,
    manual_image_cleanup_completed: bool = False,
    resume_after_image_upload: bool = False,
    resume_after_item_upsert: bool = False,
) -> str | None:
    if history_path is None or not history_path.exists():
        return None
    try:
        history = load_json(history_path)
    except Exception as exc:
        return f"execution_history could not be parsed: {exc}"

    final_status = str(history.get("final_status") or "").strip()
    item_registered = bool(history.get("item_registered"))
    inventory_registered = bool(history.get("inventory_registered"))
    cleanup_completed = bool(history.get("cleanup_completed"))
    images_uploaded = int(history.get("images_uploaded") or 0)
    cleanup_pending = bool(history.get("cleanup_pending"))
    manual_image_cleanup_completed = bool(history.get("manual_image_cleanup_completed")) or manual_image_cleanup_completed

    if (
        resume_after_item_upsert
        and final_status == "inventory_failed"
        and item_registered
        and not inventory_registered
        and not cleanup_pending
    ):
        return None

    if (
        final_status in {"image_failed", "item_failed"}
        and not item_registered
        and not inventory_registered
        and not cleanup_pending
        and (
            images_uploaded == 0
            or manual_image_cleanup_completed
            or (resume_after_image_upload and expected_image_count > 0 and images_uploaded == expected_image_count)
        )
    ):
        return None

    if final_status == "completed":
        return "execution_history already has completed status"
    if cleanup_pending:
        return "execution_history indicates cleanup is still incomplete"
    if final_status == "item_registered" or item_registered:
        return "execution_history indicates item registration already occurred"
    if final_status == "inventory_registered" or inventory_registered:
        return "execution_history indicates inventory registration already occurred"
    if images_uploaded > 0 and not manual_image_cleanup_completed and not resume_after_image_upload:
        return "execution_history indicates images were already uploaded"
    if (item_registered or inventory_registered) and not cleanup_completed:
        return "execution_history indicates cleanup is still incomplete"
    return None


def _write_history(
    *,
    asin: str,
    store_code: str,
    management_number: str,
    final_status: str,
    item_registered: bool,
    inventory_registered: bool,
    images_uploaded: int,
    cleanup_completed: bool,
    manual_image_cleanup_completed: bool,
    request_hashes: dict[str, Any],
    response_summaries: dict[str, Any],
) -> Path:
    return save_execution_history_stub(
        asin=asin,
        store_code=store_code,
        management_number=management_number,
        final_status=final_status,
        item_registered=item_registered,
        inventory_registered=inventory_registered,
        images_uploaded=images_uploaded,
        cleanup_completed=cleanup_completed,
        manual_image_cleanup_completed=manual_image_cleanup_completed,
        request_hashes=request_hashes,
        response_summaries=response_summaries,
    )


def build_real_execute_result(
    request: RealExecuteRequest,
    *,
    http_get: Callable[[str, float, bool], Any] | None = None,
    image_downloader: Callable[..., dict[str, Any]] | None = None,
    image_validator: Callable[..., dict[str, Any]] | None = None,
    image_client: RakutenImageClient | None = None,
    item_client: RakutenItemClient | None = None,
    inventory_client: RakutenInventoryClient | None = None,
) -> dict[str, Any]:
    readiness_result = load_json(request.readiness_json)
    dry_run_result = load_json(request.dry_run_json)
    preflight_result = load_json(request.preflight_json)
    mock_result = load_json(request.mock_result_json)
    cabinet_config = dict(readiness_result.get("cabinet_config") or {})
    store_settings = dict(dry_run_result.get("store_settings") or {})
    store_cabinet = dict(store_settings.get("cabinet") or {})
    merged_cabinet = {
        "shop_url": cabinet_config.get("shop_url") or store_cabinet.get("shop_url"),
        "folder_id": cabinet_config.get("folder_id") or store_cabinet.get("folder_id"),
        "folder_name": cabinet_config.get("folder_name") or store_cabinet.get("folder_name"),
        "folder_path": cabinet_config.get("folder_path") or store_cabinet.get("folder_path"),
        "folder_node": cabinet_config.get("folder_node") or store_cabinet.get("folder_node"),
    }
    store_settings["cabinet"] = merged_cabinet
    dry_run_result["store_settings"] = store_settings

    result = _build_base_result(request)
    result["readiness_json"] = str(request.readiness_json)
    result["dry_run_json"] = str(request.dry_run_json)
    result["preflight_json"] = str(request.preflight_json)
    result["mock_result_json"] = str(request.mock_result_json)
    # Preserve the original eligibility decision so a blocked batch row explains
    # the product-specific cause, rather than only its downstream gate failures.
    result["listing_status"] = str(dry_run_result.get("listing_status") or "")
    result["listing_reason"] = str(dry_run_result.get("listing_reason") or "")

    readiness_reasons = _validate_readiness_inputs(request, readiness_result, dry_run_result, preflight_result, mock_result)
    guard_reasons = _validate_execute_guards(request)
    blocking_reasons = readiness_reasons + guard_reasons
    result["blocking_reasons"] = blocking_reasons

    duplicate_guard = dict(readiness_result.get("duplicate_execution_guard") or {})
    result["execution_history"]["history_path"] = duplicate_guard.get("history_path")
    result["execution_history"]["manual_image_cleanup_completed"] = request.manual_image_cleanup_completed
    result["execution_history"]["resume_after_image_upload"] = request.resume_after_image_upload
    result["execution_history"]["resume_after_item_upsert"] = request.resume_after_item_upsert
    history_path = Path(str(duplicate_guard.get("history_path") or "")).resolve() if duplicate_guard.get("history_path") else None

    if blocking_reasons:
        result["final_status"] = "blocked"
        return result

    transport_ready = _build_transport_ready_summary(request.store)
    result["transport_dry_check"]["transport_ready"] = bool(transport_ready.get("ready"))
    result["transport_dry_check"]["reason"] = transport_ready.get("reason")
    if not transport_ready.get("ready"):
        result["blocking_reasons"] = [f"transport is not configured: {transport_ready.get('reason') or 'unknown reason'}"]
        result["final_status"] = "blocked"
        return result
    if not request.allow_live_transport:
        result["blocking_reasons"] = ["transport dry-check is active; live transport is not allowed in this phase"]
        result["final_status"] = "blocked"
        return result

    current_history_block = _current_history_block_reason(
        history_path,
        expected_image_count=_expected_image_count(dry_run_result),
        manual_image_cleanup_completed=request.manual_image_cleanup_completed,
        resume_after_image_upload=request.resume_after_image_upload,
        resume_after_item_upsert=request.resume_after_item_upsert,
    )
    if current_history_block:
        result["blocking_reasons"] = [current_history_block]
        result["final_status"] = "blocked"
        return result

    image_downloader = image_downloader or download_image_plan
    image_validator = image_validator or validate_downloaded_images
    image_client = image_client or RakutenImageClient()
    item_client = item_client or RakutenItemClient()
    inventory_client = inventory_client or RakutenInventoryClient()
    http_get = http_get or requests_http_get

    history_path = _write_history(
        asin=request.asin,
        store_code=request.store,
        management_number=request.management_number,
        final_status="started",
        item_registered=False,
        inventory_registered=False,
        images_uploaded=0,
        cleanup_completed=False,
        manual_image_cleanup_completed=request.manual_image_cleanup_completed,
        request_hashes={},
        response_summaries={},
    )
    result["execution_history"]["written"] = True
    result["execution_history"]["history_path"] = str(history_path)

    raw_execute_result = execute_listing(
        ExecuteListingRequest(
            dry_run_result=dry_run_result,
            execute=True,
            approved=True,
            asin=request.asin,
            management_number=request.management_number,
            output_root=request.output_root,
            image_headers=request.image_headers,
            item_headers=request.item_headers,
            inventory_headers=request.inventory_headers,
            resume_after_image_upload=request.resume_after_image_upload,
            resume_after_item_upsert=request.resume_after_item_upsert,
        ),
        http_get=http_get,
        image_downloader=image_downloader,
        image_validator=image_validator,
        image_client=image_client,
        item_client=item_client,
        inventory_client=inventory_client,
    )

    upload_results = list(raw_execute_result.get("image_upload_results") or [])
    item_result = raw_execute_result.get("item_result") or {}
    inventory_result = raw_execute_result.get("inventory_result") or {}
    item_registered = bool(item_result.get("success"))
    inventory_registered = bool(inventory_result.get("success"))
    final_status = str(raw_execute_result.get("execute_status") or "blocked")
    _write_history(
        asin=request.asin,
        store_code=request.store,
        management_number=request.management_number,
        final_status=final_status,
        item_registered=item_registered,
        inventory_registered=inventory_registered,
        images_uploaded=sum(1 for item in upload_results if str(item.get("upload_status") or "") == "uploaded"),
        cleanup_completed=False,
        manual_image_cleanup_completed=request.manual_image_cleanup_completed,
        request_hashes={
            "original_item_payload_hash": raw_execute_result.get("original_item_payload_hash"),
            "executed_item_payload_hash": raw_execute_result.get("executed_item_payload_hash"),
        },
        response_summaries={
            "item_result": item_result,
            "inventory_result": inventory_result,
        },
    )

    result["final_status"] = final_status
    result["would_execute"] = True
    result["external_actions_performed"] = True
    result["raw_execute_result"] = raw_execute_result
    return result
