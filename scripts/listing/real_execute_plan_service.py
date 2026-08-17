from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.listing.models import to_jsonable
from scripts.listing.rakuten_inventory_client import build_inventory_request
from scripts.listing.rakuten_item_client import build_item_request
from scripts.listing.preflight_service import load_json


ITEM_UPSERT_ENDPOINT = "https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/{manageNumber}"
INVENTORY_UPSERT_ENDPOINT = "https://api.rms.rakuten.co.jp/es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}"
IMAGE_UPLOAD_ENDPOINT = "https://api.rms.rakuten.co.jp/es/1.0/cabinet/file/insert"


def _get_check_value(readiness_result: dict[str, Any], key: str) -> Any:
    for check in list(readiness_result.get("checks") or []):
        if isinstance(check, dict) and str(check.get("key") or "") == key:
            return check.get("value")
    return None


def _normalize_folder_path(path: str | None) -> str:
    return str(path or "").replace("\\", "/").strip().strip("/")


def _normalize_shop_url(value: str | None) -> str:
    raw = str(value or "").strip().strip("/")
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return parsed.path.strip("/") if parsed.netloc else raw


def _build_safe_image_name(image_base_name: str, order: int) -> str:
    return f"{str(image_base_name or '').strip()}_{order}.jpg"


def _build_image_plan(dry_run_result: dict[str, Any], readiness_result: dict[str, Any], asin: str) -> dict[str, Any]:
    cabinet_config = dict(readiness_result.get("cabinet_config") or {})
    folder_id = cabinet_config.get("folder_id")
    folder_path = _normalize_folder_path(str(cabinet_config.get("folder_path") or ""))
    shop_url = _normalize_shop_url(str(cabinet_config.get("shop_url") or ""))
    dry_image_plan = dict(dry_run_result.get("image_download_plan") or {})
    planned_items = [item for item in list(dry_image_plan.get("items") or []) if isinstance(item, dict)]
    image_urls = [str(item.get("source_url") or "").strip() for item in planned_items if str(item.get("source_url") or "").strip()]
    if not image_urls:
        image_urls = list(dry_run_result.get("image_urls") or [])
    management_candidates = dict(to_jsonable(dry_run_result.get("management_number_candidates")) or {})
    image_base_name = str(management_candidates.get("legacy_candidate") or dry_run_result.get("management_number") or asin).strip()
    items: list[dict[str, Any]] = []
    for index, source_url in enumerate(image_urls, start=1):
        filename = _build_safe_image_name(image_base_name, index)
        item_location = f"/{folder_path}/{filename}" if folder_path else None
        full_url = f"https://image.rakuten.co.jp/{shop_url}/cabinet/{folder_path}/{filename}" if folder_path and shop_url else None
        items.append(
            {
                "order": index,
                "role": "main" if index == 1 else "sub",
                "source_url": source_url,
                "file_name": filename,
                "item_location": item_location,
                "full_url": full_url,
            }
        )
    return {
        "image_count": len(items),
        "main_image_count": sum(1 for item in items if item["role"] == "main"),
        "sub_image_count": sum(1 for item in items if item["role"] == "sub"),
        "cabinet_folder_id": folder_id,
        "cabinet_folder_path": folder_path,
        "shop_url": shop_url,
        "upload_endpoint": IMAGE_UPLOAD_ENDPOINT,
        "method": "POST",
        "content_type": "multipart/form-data",
        "items": items,
        "file_names": [item["file_name"] for item in items],
        "item_locations": [item["item_location"] for item in items],
        "full_urls": [item["full_url"] for item in items],
    }


def _first_variant(item_payload: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not isinstance(item_payload, dict):
        return "", {}
    variants = item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return "", {}
    variant_id = str(next(iter(variants.keys())) or "").strip()
    variant_payload = next(iter(variants.values()))
    return variant_id, variant_payload if isinstance(variant_payload, dict) else {}


def _extract_attribute_value(item_payload: dict[str, Any] | None, name: str) -> str | None:
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if isinstance(attribute, dict) and str(attribute.get("name") or "") == name:
            value = str(attribute.get("value") or "").strip()
            return value or None
    return None


def _requires_representative_color(item_payload: dict[str, Any] | None) -> bool:
    if not isinstance(item_payload, dict):
        return False
    if str(item_payload.get("genreId") or "") == "213661":
        return True
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if isinstance(attribute, dict) and str(attribute.get("name") or "") == "代表カラー":
            return True
    return False


def _build_item_plan(
    dry_run_result: dict[str, Any],
    readiness_result: dict[str, Any],
    image_plan: dict[str, Any],
    management_number: str,
) -> dict[str, Any]:
    item_payload = dry_run_result.get("item_payload") or {}
    _, variant_payload = _first_variant(item_payload if isinstance(item_payload, dict) else None)
    representative_color_mapping = dict(dry_run_result.get("representative_color_mapping") or {})
    return {
        "endpoint": ITEM_UPSERT_ENDPOINT.format(manageNumber=management_number),
        "method": "PUT",
        "manageNumber": management_number,
        "itemNumber": item_payload.get("itemNumber") or management_number,
        "title": item_payload.get("title"),
        "genreId": item_payload.get("genreId"),
        "representative_color": _extract_attribute_value(item_payload, "代表カラー") or _get_check_value(readiness_result, "representative_color_value"),
        "original_representative_color": representative_color_mapping.get("original_value") or _get_check_value(readiness_result, "original_representative_color"),
        "standardPrice": variant_payload.get("standardPrice"),
        "images": [{"location": item["item_location"], "role": item["role"], "order": item["order"]} for item in list(image_plan.get("items") or [])],
    }


def _build_inventory_plan(dry_run_result: dict[str, Any], management_number: str) -> dict[str, Any]:
    inventory_payload = dry_run_result.get("inventory_payload") or {}
    request = build_inventory_request(management_number, inventory_payload if isinstance(inventory_payload, dict) else {}, {})
    return {
        "endpoint": request.url,
        "method": "PUT",
        "manageNumber": request.management_number,
        "variantId": request.variant_id,
        "mode": request.payload.get("mode") or "ABSOLUTE",
        "quantity": request.payload.get("quantity"),
        "shipFromIds": list(request.payload.get("shipFromIds") or []),
        "operationLeadTime": request.payload.get("operationLeadTime"),
    }


def _extract_attribute_value_from_api_payload(item_payload: dict[str, Any] | None, name: str) -> str | None:
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if not isinstance(attribute, dict) or str(attribute.get("name") or "") != name:
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            for raw_value in raw_values:
                value = str(raw_value or "").strip()
                if value:
                    return value
        value = str(attribute.get("value") or "").strip()
        return value or None
    return None


def _build_item_plan_for_api_payload(
    dry_run_result: dict[str, Any],
    readiness_result: dict[str, Any],
    image_plan: dict[str, Any],
    management_number: str,
) -> dict[str, Any]:
    raw_item_payload = dry_run_result.get("item_payload") or {}
    item_payload = dict(raw_item_payload) if isinstance(raw_item_payload, dict) else {}
    item_payload["images"] = [
        {"type": "CABINET", "location": item["item_location"]}
        for item in list(image_plan.get("items") or [])
        if item.get("item_location")
    ]
    request = build_item_request(management_number, item_payload, {})
    api_payload = request.payload
    _, variant_payload = _first_variant(api_payload if isinstance(api_payload, dict) else None)
    representative_color_mapping = dict(dry_run_result.get("representative_color_mapping") or {})
    return {
        "endpoint": request.url,
        "method": "PUT",
        "manageNumber": management_number,
        "itemNumber": api_payload.get("itemNumber") or management_number,
        "title": api_payload.get("title"),
        "genreId": api_payload.get("genreId"),
        "representative_color": _extract_attribute_value_from_api_payload(api_payload, "代表カラー")
        or _extract_attribute_value_from_api_payload(api_payload, "カラー")
        or _get_check_value(readiness_result, "representative_color_value"),
        "original_representative_color": representative_color_mapping.get("original_value") or _get_check_value(readiness_result, "original_representative_color"),
        "standardPrice": variant_payload.get("standardPrice"),
        "images": [
            {"location": item["item_location"], "role": item["role"], "order": item["order"]}
            for item in list(image_plan.get("items") or [])
        ],
        "variants": (api_payload.get("variants") or {}) if isinstance(api_payload, dict) else {},
        "payload": api_payload,
    }


def _build_cleanup_plan(readiness_result: dict[str, Any], management_number: str) -> dict[str, Any]:
    cleanup = dict(readiness_result.get("pilot_cleanup_plan") or {})
    endpoint = str(cleanup.get("endpoint") or ITEM_UPSERT_ENDPOINT).replace("{manageNumber}", management_number)
    return {
        "endpoint": endpoint,
        "method": cleanup.get("method") or "DELETE",
        "manageNumber": management_number,
        "requires_explicit_confirmation": True,
        "search_visibility_can_lag_after_deletion": True,
    }


def _build_execution_history_guard(readiness_result: dict[str, Any], management_number: str) -> dict[str, Any]:
    duplicate_guard = dict(readiness_result.get("duplicate_execution_guard") or {})
    history_path = duplicate_guard.get("history_path") or str(Path("output") / "listing" / "execution_history" / f"{management_number}.json")
    return {
        "history_path": history_path,
        "history_file_will_be_created_on_real_execute": True,
        "block_when_status_in": ["completed", "item_registered", "inventory_registered", "cleanup_pending"],
        "current_duplicate_blocked": bool(duplicate_guard.get("duplicate_blocked")),
    }


def _build_required_guards(
    *,
    asin: str,
    management_number: str,
    store: str,
    readiness_json: str,
) -> dict[str, Any]:
    return {
        "required_flags": [
            "--execute",
            "--approved",
            "--confirm-real-api",
            f"--confirm-asin {asin}",
            f"--confirm-management-number {management_number}",
            f"--confirm-store {store}",
            f"--readiness-json {readiness_json}",
        ],
        "on_missing": {
            "final_status": "blocked",
            "external_actions_performed": False,
            "image_download": False,
            "image_upload": False,
            "item_upsert": False,
            "inventory_upsert": False,
            "cleanup": False,
        },
    }


def _build_sequence() -> list[str]:
    return [
        "readiness再確認",
        "execution_history lock作成予定",
        "Amazon画像download予定",
        "画像validation予定",
        "cabinet.file.insert 画像upload予定",
        "items.upsert予定",
        "inventories.variants.upsert予定",
        "RMS目視確認待ち",
        "items.delete cleanup予定",
        "execution_history更新予定",
    ]


def _validate_plan_inputs(
    *,
    readiness_result: dict[str, Any],
    dry_run_result: dict[str, Any],
    preflight_result: dict[str, Any],
    mock_result: dict[str, Any],
    asin: str,
    management_number: str,
    store: str,
) -> list[str]:
    blocking_reasons: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            blocking_reasons.append(reason)

    require(str(readiness_result.get("asin") or "") == asin, "readiness asin mismatch")
    require(str(readiness_result.get("store_code") or "") == store, "readiness store mismatch")
    require(str(readiness_result.get("management_number") or "") == management_number, "readiness management_number mismatch")
    require(str(dry_run_result.get("asin") or "") == asin, "dry-run asin mismatch")
    require(str(dry_run_result.get("store_code") or "") == store, "dry-run store mismatch")
    require(str(dry_run_result.get("management_number") or "") == management_number, "dry-run management_number mismatch")
    require(str(readiness_result.get("readiness_status") or "") == "ready", "readiness_status must be ready")
    require(bool(readiness_result.get("ready_for_real_execute")) is True, "ready_for_real_execute must be true")
    require(list(readiness_result.get("unresolved_specifications") or []) == [], "unresolved_specifications must be empty")
    require(bool(readiness_result.get("real_execute_spec_ready")) is True, "real_execute_spec_ready must be true")
    require(bool(readiness_result.get("human_confirmation_required")) is False, "human_confirmation_required must be false")
    require(bool((readiness_result.get("duplicate_execution_guard") or {}).get("duplicate_blocked")) is False, "duplicate execution guard must not be blocked")
    require(bool(readiness_result.get("secrets_exposed")) is False, "secrets_exposed must be false")
    require(bool(readiness_result.get("external_actions_performed")) is False, "external_actions_performed must be false")
    require(str(preflight_result.get("preflight_status") or "") in {"passed", "warning"}, "preflight_status must be passed or warning")
    require(str(mock_result.get("final_status") or "") == "completed", "mock_final_status must be completed")
    require(isinstance(dry_run_result.get("item_payload"), dict), "item payload must be present")
    require(isinstance(dry_run_result.get("inventory_payload"), dict), "inventory payload must be present")
    expected_image_count = _planned_image_count(dry_run_result)
    require(len(list(mock_result.get("image_results") or [])) == expected_image_count, f"image result count must be {expected_image_count}")
    representative_color_required = _requires_representative_color(dry_run_result.get("item_payload"))
    representative_color = _extract_attribute_value(dry_run_result.get("item_payload"), "代表カラー") or str((mock_result.get("item_request_summary") or {}).get("representative_color") or "")
    if representative_color_required:
        require(representative_color in {"ブルー", "-"}, "representative_color_value must be ブルー or -")
        original_color = str((dry_run_result.get("representative_color_mapping") or {}).get("original_value") or "")
        if representative_color != "-":
            require(original_color == "クリアブルーラメ", "original_representative_color must be クリアブルーラメ")
    return blocking_reasons


def _planned_image_count(dry_run_result: dict[str, Any]) -> int:
    image_plan = dict(dry_run_result.get("image_download_plan") or {})
    plan_items = [item for item in list(image_plan.get("items") or []) if isinstance(item, dict)]
    if plan_items:
        return len(plan_items)
    return len(list(dry_run_result.get("image_urls") or []))


def _validate_plan_inputs_for_image_limit(
    *,
    readiness_result: dict[str, Any],
    dry_run_result: dict[str, Any],
    preflight_result: dict[str, Any],
    mock_result: dict[str, Any],
    asin: str,
    management_number: str,
    store: str,
) -> list[str]:
    blocking_reasons = _validate_plan_inputs(
        readiness_result=readiness_result,
        dry_run_result=dry_run_result,
        preflight_result=preflight_result,
        mock_result=mock_result,
        asin=asin,
        management_number=management_number,
        store=store,
    )
    expected = _planned_image_count(dry_run_result)
    fixed_reason = f"image result count must be {expected}"
    if fixed_reason in blocking_reasons and len(list(mock_result.get("image_results") or [])) == expected:
        blocking_reasons = [reason for reason in blocking_reasons if reason != fixed_reason]
    return blocking_reasons


def build_real_execute_plan_result(
    *,
    readiness_json: Path,
    dry_run_json: Path,
    preflight_json: Path,
    mock_result_json: Path,
    asin: str,
    management_number: str,
    store: str,
) -> dict[str, Any]:
    readiness_result = load_json(readiness_json)
    dry_run_result = load_json(dry_run_json)
    preflight_result = load_json(preflight_json)
    mock_result = load_json(mock_result_json)

    blocking_reasons = _validate_plan_inputs_for_image_limit(
        readiness_result=readiness_result,
        dry_run_result=dry_run_result,
        preflight_result=preflight_result,
        mock_result=mock_result,
        asin=asin,
        management_number=management_number,
        store=store,
    )
    plan_status = "blocked" if blocking_reasons else "ready"
    image_plan = _build_image_plan(dry_run_result, readiness_result, asin)
    planned_image_count = int(image_plan.get("image_count") or _planned_image_count(dry_run_result))
    item_plan = _build_item_plan_for_api_payload(dry_run_result, readiness_result, image_plan, management_number)
    inventory_plan = _build_inventory_plan(dry_run_result, management_number)
    cleanup_plan = _build_cleanup_plan(readiness_result, management_number)

    return to_jsonable(
        {
            "mode": "real_execute_plan",
            "plan_status": plan_status,
            "would_execute": not blocking_reasons,
            "external_actions_performed": False,
            "secrets_exposed": False,
            "asin": asin,
            "store_code": store,
            "management_number": management_number,
            "readiness_json": str(readiness_json),
            "dry_run_json": str(dry_run_json),
            "preflight_json": str(preflight_json),
            "mock_result_json": str(mock_result_json),
            "readiness_recheck": {
                "readiness_status": readiness_result.get("readiness_status"),
                "ready_for_real_execute": readiness_result.get("ready_for_real_execute"),
                "unresolved_specifications": readiness_result.get("unresolved_specifications") or [],
                "real_execute_spec_ready": readiness_result.get("real_execute_spec_ready"),
                "human_confirmation_required": readiness_result.get("human_confirmation_required"),
                "duplicate_execution_guard": readiness_result.get("duplicate_execution_guard") or {},
                "secrets_exposed": readiness_result.get("secrets_exposed"),
                "external_actions_performed": readiness_result.get("external_actions_performed"),
                "preflight_status": preflight_result.get("preflight_status"),
                "mock_final_status": mock_result.get("final_status"),
                "representative_color_value": (mock_result.get("item_request_summary") or {}).get("representative_color"),
                "original_representative_color": (dry_run_result.get("representative_color_mapping") or {}).get("original_value"),
            },
            "blocking_reasons": blocking_reasons,
            "execution_sequence": _build_sequence(),
            "image_plan": image_plan,
            "item_plan": item_plan,
            "inventory_plan": inventory_plan,
            "cleanup_plan": cleanup_plan,
            "execution_history_guard": _build_execution_history_guard(readiness_result, management_number),
            "retry_modes": {
                "resume_after_image_upload": {
                    "cli_flag": "--resume-after-image-upload",
                    "allowed_when": {
                        "final_status_in": ["image_failed", "item_failed"],
                        "item_registered": False,
                        "inventory_registered": False,
                        "images_uploaded": planned_image_count,
                    },
                }
            },
            "required_real_execute_guards": _build_required_guards(
                asin=asin,
                management_number=management_number,
                store=store,
                readiness_json=str(readiness_json),
            ),
        }
    )


def _extract_attribute_value(item_payload: dict[str, Any] | None, name: str) -> str | None:
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if not isinstance(attribute, dict):
            continue
        if str(attribute.get("name") or "") != name:
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            value = next((str(item or "").strip() for item in raw_values if str(item or "").strip()), "")
        else:
            value = str(attribute.get("value") or "").strip()
        return value or None
    return None


def _extract_attribute_value(item_payload: dict[str, Any] | None, name: str) -> str | None:
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if not isinstance(attribute, dict):
            continue
        attribute_name = str(attribute.get("name") or "")
        if attribute_name != name and ("カラー" not in name or "カラー" not in attribute_name):
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            value = next((str(item or "").strip() for item in raw_values if str(item or "").strip()), "")
        else:
            value = str(attribute.get("value") or "").strip()
        return value or None
    return None


def _build_item_plan(
    dry_run_result: dict[str, Any],
    readiness_result: dict[str, Any],
    image_plan: dict[str, Any],
    management_number: str,
) -> dict[str, Any]:
    raw_item_payload = dry_run_result.get("item_payload") or {}
    item_payload = dict(raw_item_payload) if isinstance(raw_item_payload, dict) else {}
    item_payload["images"] = [
        {"type": "CABINET", "location": item["item_location"]}
        for item in list(image_plan.get("items") or [])
        if item.get("item_location")
    ]
    request = build_item_request(management_number, item_payload, {})
    api_payload = request.payload
    _, variant_payload = _first_variant(api_payload if isinstance(api_payload, dict) else None)
    representative_color_mapping = dict(dry_run_result.get("representative_color_mapping") or {})
    return {
        "endpoint": request.url,
        "method": "PUT",
        "manageNumber": management_number,
        "itemNumber": api_payload.get("itemNumber") or management_number,
        "title": api_payload.get("title"),
        "genreId": api_payload.get("genreId"),
        "representative_color": _extract_attribute_value(api_payload, "代表カラー") or _get_check_value(readiness_result, "representative_color_value"),
        "original_representative_color": representative_color_mapping.get("original_value") or _get_check_value(readiness_result, "original_representative_color"),
        "standardPrice": variant_payload.get("standardPrice"),
        "images": [{"location": item["item_location"], "role": item["role"], "order": item["order"]} for item in list(image_plan.get("items") or [])],
        "variants": (api_payload.get("variants") or {}) if isinstance(api_payload, dict) else {},
        "payload": api_payload,
    }


# Final definitions below intentionally override older generated duplicates above.
def _build_sequence() -> list[str]:
    return [
        "readiness再確認",
        "execution_history lock作成予定",
        "Amazon画像download予定",
        "画像validation予定",
        "cabinet.file.insert 画像upload予定",
        "items.upsert予定",
        "inventories.variants.upsert予定",
        "RMS目視確認待ち",
        "items.delete cleanup予定",
        "execution_history更新予定",
    ]


def _extract_attribute_value(item_payload: dict[str, Any] | None, name: str) -> str | None:
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if not isinstance(attribute, dict):
            continue
        attribute_name = str(attribute.get("name") or "")
        if attribute_name != name and ("カラー" not in name or "カラー" not in attribute_name):
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            value = next((str(item or "").strip() for item in raw_values if str(item or "").strip()), "")
        else:
            value = str(attribute.get("value") or "").strip()
        return value or None
    return None


def _validate_plan_inputs(
    *,
    readiness_result: dict[str, Any],
    dry_run_result: dict[str, Any],
    preflight_result: dict[str, Any],
    mock_result: dict[str, Any],
    asin: str,
    management_number: str,
    store: str,
) -> list[str]:
    blocking_reasons: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            blocking_reasons.append(reason)

    require(str(readiness_result.get("asin") or "") == asin, "readiness asin mismatch")
    require(str(readiness_result.get("store_code") or "") == store, "readiness store mismatch")
    require(str(readiness_result.get("management_number") or "") == management_number, "readiness management_number mismatch")
    require(str(dry_run_result.get("asin") or "") == asin, "dry-run asin mismatch")
    require(str(dry_run_result.get("store_code") or "") == store, "dry-run store mismatch")
    require(str(dry_run_result.get("management_number") or "") == management_number, "dry-run management_number mismatch")
    require(str(readiness_result.get("readiness_status") or "") == "ready", "readiness_status must be ready")
    require(bool(readiness_result.get("ready_for_real_execute")) is True, "ready_for_real_execute must be true")
    require(list(readiness_result.get("unresolved_specifications") or []) == [], "unresolved_specifications must be empty")
    require(bool(readiness_result.get("real_execute_spec_ready")) is True, "real_execute_spec_ready must be true")
    require(bool(readiness_result.get("human_confirmation_required")) is False, "human_confirmation_required must be false")
    require(bool((readiness_result.get("duplicate_execution_guard") or {}).get("duplicate_blocked")) is False, "duplicate execution guard must not be blocked")
    require(bool(readiness_result.get("secrets_exposed")) is False, "secrets_exposed must be false")
    require(bool(readiness_result.get("external_actions_performed")) is False, "external_actions_performed must be false")
    require(str(preflight_result.get("preflight_status") or "") in {"passed", "warning"}, "preflight_status must be passed or warning")
    require(str(mock_result.get("final_status") or "") == "completed", "mock_final_status must be completed")
    require(isinstance(dry_run_result.get("item_payload"), dict), "item payload must be present")
    require(isinstance(dry_run_result.get("inventory_payload"), dict), "inventory payload must be present")
    expected_image_count = _planned_image_count(dry_run_result)
    require(len(list(mock_result.get("image_results") or [])) == expected_image_count, f"image result count must be {expected_image_count}")

    representative_color_required = _requires_representative_color(dry_run_result.get("item_payload"))
    representative_color = _extract_attribute_value(dry_run_result.get("item_payload"), "代表カラー") or str((mock_result.get("item_request_summary") or {}).get("representative_color") or "")
    if representative_color_required:
        require(representative_color in {"ブルー", "-"}, "representative_color_value must be ブルー or -")
        original_color = str((dry_run_result.get("representative_color_mapping") or {}).get("original_value") or "")
        if representative_color != "-":
            require(original_color == "クリアブルーラメ", "original_representative_color must be クリアブルーラメ")
    return blocking_reasons


def _build_item_plan(
    dry_run_result: dict[str, Any],
    readiness_result: dict[str, Any],
    image_plan: dict[str, Any],
    management_number: str,
) -> dict[str, Any]:
    raw_item_payload = dry_run_result.get("item_payload") or {}
    item_payload = dict(raw_item_payload) if isinstance(raw_item_payload, dict) else {}
    item_payload["images"] = [
        {"type": "CABINET", "location": item["item_location"]}
        for item in list(image_plan.get("items") or [])
        if item.get("item_location")
    ]
    request = build_item_request(management_number, item_payload, {})
    api_payload = request.payload
    _, variant_payload = _first_variant(api_payload if isinstance(api_payload, dict) else None)
    representative_color_mapping = dict(dry_run_result.get("representative_color_mapping") or {})
    return {
        "endpoint": request.url,
        "method": "PUT",
        "manageNumber": management_number,
        "itemNumber": api_payload.get("itemNumber") or management_number,
        "title": api_payload.get("title"),
        "genreId": api_payload.get("genreId"),
        "representative_color": _extract_attribute_value(api_payload, "代表カラー") or _get_check_value(readiness_result, "representative_color_value"),
        "original_representative_color": representative_color_mapping.get("original_value") or _get_check_value(readiness_result, "original_representative_color"),
        "standardPrice": variant_payload.get("standardPrice"),
        "images": [{"location": item["item_location"], "role": item["role"], "order": item["order"]} for item in list(image_plan.get("items") or [])],
        "variants": (api_payload.get("variants") or {}) if isinstance(api_payload, dict) else {},
        "payload": api_payload,
    }


def _build_sequence() -> list[str]:
    return [
        "readiness再確認",
        "execution_history lock作成予定",
        "Amazon画像download予定",
        "画像validation予定",
        "cabinet.file.insert 画像upload予定",
        "items.upsert予定",
        "inventories.variants.upsert予定",
        "RMS目視確認待ち",
        "items.delete cleanup予定",
        "execution_history更新予定",
    ]


def _extract_attribute_value(item_payload: dict[str, Any] | None, name: str) -> str | None:
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if not isinstance(attribute, dict):
            continue
        attribute_name = str(attribute.get("name") or "")
        if attribute_name != name and ("カラー" not in name or "カラー" not in attribute_name):
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            value = next((str(item or "").strip() for item in raw_values if str(item or "").strip()), "")
        else:
            value = str(attribute.get("value") or "").strip()
        return value or None
    return None


def _validate_plan_inputs(
    *,
    readiness_result: dict[str, Any],
    dry_run_result: dict[str, Any],
    preflight_result: dict[str, Any],
    mock_result: dict[str, Any],
    asin: str,
    management_number: str,
    store: str,
) -> list[str]:
    blocking_reasons: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            blocking_reasons.append(reason)

    require(str(readiness_result.get("asin") or "") == asin, "readiness asin mismatch")
    require(str(readiness_result.get("store_code") or "") == store, "readiness store mismatch")
    require(str(readiness_result.get("management_number") or "") == management_number, "readiness management_number mismatch")
    require(str(dry_run_result.get("asin") or "") == asin, "dry-run asin mismatch")
    require(str(dry_run_result.get("store_code") or "") == store, "dry-run store mismatch")
    require(str(dry_run_result.get("management_number") or "") == management_number, "dry-run management_number mismatch")
    require(str(readiness_result.get("readiness_status") or "") == "ready", "readiness_status must be ready")
    require(bool(readiness_result.get("ready_for_real_execute")) is True, "ready_for_real_execute must be true")
    require(list(readiness_result.get("unresolved_specifications") or []) == [], "unresolved_specifications must be empty")
    require(bool(readiness_result.get("real_execute_spec_ready")) is True, "real_execute_spec_ready must be true")
    require(bool(readiness_result.get("human_confirmation_required")) is False, "human_confirmation_required must be false")
    require(bool((readiness_result.get("duplicate_execution_guard") or {}).get("duplicate_blocked")) is False, "duplicate execution guard must not be blocked")
    require(bool(readiness_result.get("secrets_exposed")) is False, "secrets_exposed must be false")
    require(bool(readiness_result.get("external_actions_performed")) is False, "external_actions_performed must be false")
    require(str(preflight_result.get("preflight_status") or "") in {"passed", "warning"}, "preflight_status must be passed or warning")
    require(str(mock_result.get("final_status") or "") == "completed", "mock_final_status must be completed")
    require(isinstance(dry_run_result.get("item_payload"), dict), "item payload must be present")
    require(isinstance(dry_run_result.get("inventory_payload"), dict), "inventory payload must be present")
    expected_image_count = _planned_image_count(dry_run_result)
    require(len(list(mock_result.get("image_results") or [])) == expected_image_count, f"image result count must be {expected_image_count}")

    representative_color_required = _requires_representative_color(dry_run_result.get("item_payload"))
    representative_color = _extract_attribute_value(dry_run_result.get("item_payload"), "代表カラー") or str((mock_result.get("item_request_summary") or {}).get("representative_color") or "")
    if representative_color_required:
        require(representative_color in {"ブルー", "-"}, "representative_color_value must be ブルー or -")
        original_color = str((dry_run_result.get("representative_color_mapping") or {}).get("original_value") or "")
        if representative_color != "-":
            require(original_color == "クリアブルーラメ", "original_representative_color must be クリアブルーラメ")
    return blocking_reasons


def _build_item_plan(
    dry_run_result: dict[str, Any],
    readiness_result: dict[str, Any],
    image_plan: dict[str, Any],
    management_number: str,
) -> dict[str, Any]:
    raw_item_payload = dry_run_result.get("item_payload") or {}
    item_payload = dict(raw_item_payload) if isinstance(raw_item_payload, dict) else {}
    item_payload["images"] = [
        {"type": "CABINET", "location": item["item_location"]}
        for item in list(image_plan.get("items") or [])
        if item.get("item_location")
    ]
    request = build_item_request(management_number, item_payload, {})
    api_payload = request.payload
    _, variant_payload = _first_variant(api_payload if isinstance(api_payload, dict) else None)
    representative_color_mapping = dict(dry_run_result.get("representative_color_mapping") or {})
    return {
        "endpoint": request.url,
        "method": "PUT",
        "manageNumber": management_number,
        "itemNumber": api_payload.get("itemNumber") or management_number,
        "title": api_payload.get("title"),
        "genreId": api_payload.get("genreId"),
        "representative_color": _extract_attribute_value(api_payload, "代表カラー") or _get_check_value(readiness_result, "representative_color_value"),
        "original_representative_color": representative_color_mapping.get("original_value") or _get_check_value(readiness_result, "original_representative_color"),
        "standardPrice": variant_payload.get("standardPrice"),
        "images": [{"location": item["item_location"], "role": item["role"], "order": item["order"]} for item in list(image_plan.get("items") or [])],
        "variants": (api_payload.get("variants") or {}) if isinstance(api_payload, dict) else {},
        "payload": api_payload,
    }


def _build_item_plan(
    dry_run_result: dict[str, Any],
    readiness_result: dict[str, Any],
    image_plan: dict[str, Any],
    management_number: str,
) -> dict[str, Any]:
    item_payload = dry_run_result.get("item_payload") or {}
    request = build_item_request(management_number, item_payload if isinstance(item_payload, dict) else {}, {})
    item_payload = request.payload
    _, variant_payload = _first_variant(item_payload if isinstance(item_payload, dict) else None)
    representative_color_mapping = dict(dry_run_result.get("representative_color_mapping") or {})
    return {
        "endpoint": request.url,
        "method": "PUT",
        "manageNumber": management_number,
        "itemNumber": item_payload.get("itemNumber") or management_number,
        "title": item_payload.get("title"),
        "genreId": item_payload.get("genreId"),
        "representative_color": _extract_attribute_value(item_payload, "代表カラー") or _get_check_value(readiness_result, "representative_color_value"),
        "original_representative_color": representative_color_mapping.get("original_value") or _get_check_value(readiness_result, "original_representative_color"),
        "standardPrice": variant_payload.get("standardPrice"),
        "images": [{"location": item["item_location"], "role": item["role"], "order": item["order"]} for item in list(image_plan.get("items") or [])],
        "variants": (item_payload.get("variants") or {}) if isinstance(item_payload, dict) else {},
    }


def _extract_attribute_value(item_payload: dict[str, Any] | None, name: str) -> str | None:
    _, variant_payload = _first_variant(item_payload)
    for attribute in list(variant_payload.get("attributes") or []):
        if not isinstance(attribute, dict):
            continue
        attribute_name = str(attribute.get("name") or "")
        if attribute_name != name and ("カラー" not in name or "カラー" not in attribute_name):
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            value = next((str(item or "").strip() for item in raw_values if str(item or "").strip()), "")
        else:
            value = str(attribute.get("value") or "").strip()
        return value or None
    return None
