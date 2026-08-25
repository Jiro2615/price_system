from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.listing.models import to_jsonable
from scripts.listing.preflight_service import ensure_output_parent, load_json
from scripts.listing.rakuten_api_spec_loader import build_confirmed_specifications, build_unresolved_specifications, load_rakuten_api_spec
from scripts.listing.rakuten_transport import rakuten_auth_env_status
from scripts.listing.store_config import get_store_cabinet_config


BASE_DIR = Path(__file__).resolve().parents[2]
HISTORY_DIR = BASE_DIR / "output" / "listing" / "execution_history"


def _history_path(management_number: str) -> Path:
    return HISTORY_DIR / f"{management_number}.json"


def _build_duplicate_execution_guard(management_number: str) -> dict[str, Any]:
    history_path = _history_path(management_number)
    if not history_path.exists():
        return {
            "history_path": str(history_path),
            "history_exists": False,
            "has_completed_record": False,
            "duplicate_blocked": False,
            "reason": None,
        }

    try:
        history = load_json(history_path)
    except Exception as exc:
        return {
            "history_path": str(history_path),
            "history_exists": True,
            "has_completed_record": False,
            "duplicate_blocked": True,
            "reason": f"execution history could not be parsed: {exc}",
        }

    final_status = str(history.get("final_status") or "").strip()
    has_completed_record = final_status == "completed"
    return {
        "history_path": str(history_path),
        "history_exists": True,
        "has_completed_record": has_completed_record,
        "duplicate_blocked": has_completed_record,
        "reason": "completed history already exists for this management number" if has_completed_record else None,
    }


def _build_auth_configuration_summary(store_code: str) -> dict[str, Any]:
    auth_status = rakuten_auth_env_status(store_code)
    configured = bool(auth_status.get("configured"))
    missing_keys = list(auth_status.get("missing_keys") or [])
    return {
        "store_code": store_code,
        "item_api": {
            "configured": configured,
            "missing_keys": [] if configured else missing_keys,
        },
        "inventory_api": {
            "configured": configured,
            "missing_keys": [] if configured else missing_keys,
        },
        "image_api": {
            "configured": configured,
            "missing_keys": [] if configured else missing_keys,
        },
    }


def _check(key: str, status: str, value: Any, expected: Any, note: str | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "status": status,
        "value": value,
        "expected": expected,
        "note": note,
    }


def _normalize_cabinet_folder_path(path: str | None) -> str:
    return str(path or "").replace("\\", "/").strip().strip("/")


def _normalize_shop_url(shop_url: str | None) -> str:
    value = str(shop_url or "").strip().strip("/")
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.path.strip("/") if parsed.netloc else value


def _build_cabinet_examples(cabinet_config: dict[str, Any]) -> dict[str, str | None]:
    folder_path = _normalize_cabinet_folder_path(str(cabinet_config.get("folder_path") or ""))
    shop_url = _normalize_shop_url(str(cabinet_config.get("shop_url") or ""))
    example_file = "b0cn39x1fc_01.jpg"
    if not folder_path:
        return {
            "example_file_path": example_file,
            "item_location": None,
            "full_url": None,
        }
    item_location = f"/{folder_path}/{example_file}"
    full_url = f"https://image.rakuten.co.jp/{shop_url}/cabinet/{folder_path}/{example_file}" if shop_url else None
    return {
        "example_file_path": example_file,
        "item_location": item_location,
        "full_url": full_url,
    }


def _build_checks(
    dry_run_result: dict[str, Any],
    preflight_result: dict[str, Any],
    mock_result: dict[str, Any],
    *,
    asin: str,
    store: str,
    management_number: str,
    api_spec: dict[str, Any],
    auth_summary: dict[str, Any],
    duplicate_guard: dict[str, Any],
    confirmed_specifications: list[dict[str, Any]],
    unresolved_specifications: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    item_summary = mock_result.get("item_request_summary") or {}
    image_results = list(mock_result.get("image_results") or [])
    image_plan = dry_run_result.get("image_download_plan") or {}
    expected_image_count = len(list((image_plan or {}).get("items") or [])) if isinstance(image_plan, dict) else 0
    if expected_image_count <= 0:
        expected_image_count = len(list(dry_run_result.get("image_urls") or []))
    title = str(item_summary.get("title") or "")
    representative_color = _resolve_representative_color(dry_run_result, mock_result)
    representative_color_mapping = dry_run_result.get("representative_color_mapping") or {}
    original_representative_color = str(representative_color_mapping.get("original_value") or "")
    representative_color_required = _requires_representative_color(dry_run_result)
    return [
        _check("dry_run_present", "ok", bool(dry_run_result), True),
        _check("preflight_present", "ok", bool(preflight_result), True),
        _check("mock_result_present", "ok", bool(mock_result), True),
        _check("asin_match", "ok" if str(dry_run_result.get("asin") or "") == asin == str(mock_result.get("asin") or "") else "blocked", asin, asin),
        _check("store_match", "ok" if str(dry_run_result.get("store_code") or "") == store == str(mock_result.get("store_code") or "") else "blocked", store, store),
        _check(
            "management_number_match",
            "ok" if str(dry_run_result.get("management_number") or "") == management_number == str(mock_result.get("management_number") or "") else "blocked",
            management_number,
            management_number,
        ),
        _check("preflight_status", "ok" if str(preflight_result.get("preflight_status") or "") in {"passed", "warning"} else "blocked", preflight_result.get("preflight_status"), "passed or warning"),
        _check("ready_for_mock_execute", "ok" if preflight_result.get("ready_for_mock_execute") else "blocked", preflight_result.get("ready_for_mock_execute"), True),
        _check("mock_final_status", "ok" if str(mock_result.get("final_status") or "") == "completed" else "blocked", mock_result.get("final_status"), "completed"),
        _check("mock_only", "ok" if mock_result.get("mock_only") is True else "blocked", mock_result.get("mock_only"), True),
        _check("mock_external_actions", "ok" if mock_result.get("external_actions_performed") is False else "blocked", mock_result.get("external_actions_performed"), False),
        _check("listing_status", "ok" if dry_run_result.get("listing_status") == "eligible" else "blocked", dry_run_result.get("listing_status"), "eligible"),
        _check("blocking_reasons", "ok" if not list(dry_run_result.get("blocking_reasons") or []) else "blocked", dry_run_result.get("blocking_reasons") or [], []),
        _check("matched_forbidden_words", "ok" if not list(dry_run_result.get("matched_forbidden_words") or []) else "blocked", dry_run_result.get("matched_forbidden_words") or [], []),
        _check("legacy_spacing_reviews", "ok" if not list(dry_run_result.get("legacy_spacing_reviews") or []) else "blocked", dry_run_result.get("legacy_spacing_reviews") or [], []),
        _check("item_payload_present", "ok" if isinstance(dry_run_result.get("item_payload"), dict) else "blocked", isinstance(dry_run_result.get("item_payload"), dict), True),
        _check("inventory_payload_present", "ok" if isinstance(dry_run_result.get("inventory_payload"), dict) else "blocked", isinstance(dry_run_result.get("inventory_payload"), dict), True),
        _check("image_result_count", "ok" if len(image_results) == expected_image_count else "warning", len(image_results), expected_image_count),
        _check("title_spacing", "ok" if "ク リア" not in title else "blocked", "ク リア" in title, False),
        _check(
            "representative_color_value",
            "ok" if (not representative_color_required or representative_color in {"ブルー", "-"}) else "blocked",
            representative_color,
            "ブルー or -" if representative_color_required else "not required",
        ),
        _check(
            "original_representative_color",
            "ok" if (not representative_color_required or representative_color == "-" or original_representative_color == "クリアブルーラメ") else "warning",
            original_representative_color,
            "クリアブルーラメ (or -)" if representative_color_required else "not required",
        ),
        _check("confirmed_specifications", "ok" if confirmed_specifications else "warning", [item.get("name") for item in confirmed_specifications], "confirmed specification entries"),
        _check("unresolved_specifications", "warning" if unresolved_specifications else "ok", [item.get("name") for item in unresolved_specifications], []),
        _check("item_api_auth", "ok" if (auth_summary.get("item_api") or {}).get("configured") else "warning", auth_summary.get("item_api"), {"configured": True}),
        _check("inventory_api_auth", "ok" if (auth_summary.get("inventory_api") or {}).get("configured") else "warning", auth_summary.get("inventory_api"), {"configured": True}),
        _check("image_api_auth", "ok" if (auth_summary.get("image_api") or {}).get("configured") else "warning", auth_summary.get("image_api"), {"configured": True}),
        _check("duplicate_execution_guard", "blocked" if duplicate_guard.get("duplicate_blocked") else "ok", duplicate_guard, {"duplicate_blocked": False}),
        _check("cleanup_plan_confirmed", "ok" if (api_spec.get("delete_or_hide") or {}).get("confirmed") else "warning", api_spec.get("delete_or_hide"), {"confirmed": True}),
        _check("pilot_log_path_ready", "ok", str(_history_path(management_number)), "output/listing/execution_history/<management_number>.json"),
    ]


def _first_variant_payload(item_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(item_payload, dict):
        return {}
    variants = item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return {}
    first_variant = next(iter(variants.values()))
    return first_variant if isinstance(first_variant, dict) else {}


def _extract_attribute_first_value(item_payload: dict[str, Any] | None, attribute_name: str) -> str:
    variant_payload = _first_variant_payload(item_payload)
    attributes = list(variant_payload.get("attributes") or [])
    for attribute in attributes:
        if not isinstance(attribute, dict):
            continue
        raw_values = attribute.get("values")
        if isinstance(raw_values, list):
            value = next((str(item or "").strip() for item in raw_values if str(item or "").strip()), "")
        else:
            value = str(attribute.get("value") or "").strip()
        if str(attribute.get("name") or "") == attribute_name and value:
            return value
    return ""


def _requires_representative_color(dry_run_result: dict[str, Any]) -> bool:
    item_payload = dry_run_result.get("item_payload") or {}
    if not isinstance(item_payload, dict):
        return False
    if str(item_payload.get("genreId") or "") == "213661":
        return True
    return bool(_extract_attribute_first_value(item_payload, "代表カラー"))


def _resolve_representative_color(dry_run_result: dict[str, Any], mock_result: dict[str, Any]) -> str:
    item_summary = mock_result.get("item_request_summary") or {}
    summary_value = str(item_summary.get("representative_color") or "").strip()
    if summary_value:
        return summary_value
    item_payload = dry_run_result.get("item_payload") or {}
    return _extract_attribute_first_value(item_payload, "代表カラー")


def _derive_readiness_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in checks}
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "warning"
    return "ready"


def _build_pilot_cleanup_plan(api_spec: dict[str, Any]) -> dict[str, Any]:
    delete_or_hide = api_spec.get("delete_or_hide") or {}
    return {
        "confirmed": bool(delete_or_hide.get("confirmed")),
        "method": delete_or_hide.get("method"),
        "endpoint": delete_or_hide.get("endpoint"),
        "recommended_pilot_cleanup": delete_or_hide.get("recommended_pilot_cleanup"),
        "note": "パイロット後 cleanup は未確定のため、本番前にRMSまたは仕様書で要確認です" if not delete_or_hide.get("confirmed") else None,
    }


def _load_cabinet_config(store: str, api_spec: dict[str, Any]) -> dict[str, Any]:
    store_config = get_store_cabinet_config(store)
    if store_config:
        return store_config
    return dict((api_spec.get("image_api") or {}).get("cabinet_destination") or {})


def _has_runtime_cabinet_destination(cabinet_config: dict[str, Any]) -> bool:
    return bool(
        cabinet_config.get("folder_id")
        and _normalize_cabinet_folder_path(str(cabinet_config.get("folder_path") or ""))
        and str(cabinet_config.get("shop_url") or "").strip()
    )


def _resolve_runtime_specifications(
    unresolved_specifications: list[dict[str, Any]], cabinet_config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Treat the per-store Cabinet setting as the runtime confirmation source."""
    if not _has_runtime_cabinet_destination(cabinet_config):
        return unresolved_specifications
    return [item for item in unresolved_specifications if item.get("name") != "cabinet_destination"]


def _build_blocking_reasons(checks: list[dict[str, Any]]) -> list[str]:
    return [f"{check.get('key')}: {check.get('note') or check.get('expected')}" for check in checks if check.get("status") == "blocked"]


def _build_warnings(checks: list[dict[str, Any]], preflight_result: dict[str, Any], mock_result: dict[str, Any]) -> list[str]:
    warnings = list(preflight_result.get("warnings") or []) + list(mock_result.get("warnings") or [])
    for check in checks:
        if check.get("status") == "warning":
            warnings.append(f"{check.get('key')}: {check.get('note') or 'requires confirmation'}")
    if not any(check.get("key") == "unresolved_specifications" and check.get("status") == "warning" for check in checks):
        warnings = [
            item
            for item in warnings
            if "image CABINET destination runtime config" not in str(item)
            and "unresolved_specifications: requires confirmation" not in str(item)
        ]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in warnings:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def build_real_readiness_result(
    *,
    dry_run_json: Path,
    preflight_json: Path,
    mock_result_json: Path,
    api_spec_json: Path,
    asin: str,
    management_number: str,
    store: str,
    allow_existing_update: bool = False,
) -> dict[str, Any]:
    dry_run_result = load_json(dry_run_json)
    preflight_result = load_json(preflight_json)
    mock_result = load_json(mock_result_json)
    api_spec = load_rakuten_api_spec(api_spec_json)
    cabinet_config = _load_cabinet_config(store, api_spec)
    cabinet_examples = _build_cabinet_examples(cabinet_config)

    genre_id = (mock_result.get("item_request_summary") or {}).get("genreId") or ((dry_run_result.get("item_payload") or {}).get("genreId"))
    confirmed_specifications = build_confirmed_specifications(api_spec, genre_id=genre_id)
    if _has_runtime_cabinet_destination(cabinet_config):
        confirmed_specifications = [
            item for item in confirmed_specifications if item.get("scope") != "image_api.cabinet_destination"
        ]
    unresolved_specifications = _resolve_runtime_specifications(
        build_unresolved_specifications(api_spec, genre_id=genre_id), cabinet_config
    )
    if _has_runtime_cabinet_destination(cabinet_config):
        confirmed_specifications.append(
            {
                "scope": "image_api.cabinet_destination",
                "name": "cabinet_destination",
                "details": cabinet_config,
            }
        )
    auth_summary = _build_auth_configuration_summary(store)
    duplicate_guard = _build_duplicate_execution_guard(management_number)
    if allow_existing_update:
        duplicate_guard = {
            **duplicate_guard,
            "duplicate_blocked": False,
            "reason": "existing listing content refresh is allowed",
        }
    checks = _build_checks(
        dry_run_result,
        preflight_result,
        mock_result,
        asin=asin,
        store=store,
        management_number=management_number,
        api_spec=api_spec,
        auth_summary=auth_summary,
        duplicate_guard=duplicate_guard,
        confirmed_specifications=confirmed_specifications,
        unresolved_specifications=unresolved_specifications,
    )
    readiness_status = _derive_readiness_status(checks)
    spec_ready = not unresolved_specifications
    auth_ready = all(bool((auth_summary.get(name) or {}).get("configured")) for name in ("item_api", "inventory_api", "image_api"))
    # Dry-run-only checks (for example image upload verification) remain
    # warnings. They should be visible to the operator but must not conflict
    # with the preflight contract that permits a real execute on warning.
    ready_for_real_execute = readiness_status in {"ready", "warning"} and spec_ready and auth_ready and not duplicate_guard.get("duplicate_blocked")

    return {
        "asin": asin,
        "store_code": store,
        "management_number": management_number,
        "readiness_status": readiness_status,
        "checks": checks,
        "warnings": _build_warnings(checks, preflight_result, mock_result),
        "blocking_reasons": _build_blocking_reasons(checks),
        "confirmed_specifications": confirmed_specifications,
        "unresolved_specifications": unresolved_specifications,
        "real_execute_spec_ready": spec_ready,
        "auth_configuration_summary": auth_summary,
        "cabinet_config": cabinet_config,
        "cabinet_examples": cabinet_examples,
        "pilot_cleanup_plan": _build_pilot_cleanup_plan(api_spec),
        "duplicate_execution_guard": duplicate_guard,
        "ready_for_real_execute": ready_for_real_execute,
        "human_confirmation_required": bool(unresolved_specifications),
        "external_actions_performed": False,
        "secrets_exposed": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": {
            "dry_run_json": str(dry_run_json),
            "preflight_json": str(preflight_json),
            "mock_result_json": str(mock_result_json),
            "api_spec_json": str(api_spec_json),
        },
    }


def save_execution_history_stub(
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
    path = _history_path(management_number)
    ensure_output_parent(path)
    payload = {
        "asin": asin,
        "store_code": store_code,
        "management_number": management_number,
        "started_at": None,
        "completed_at": None,
        "final_status": final_status,
        "item_registered": item_registered,
        "inventory_registered": inventory_registered,
        "images_uploaded": images_uploaded,
        "cleanup_completed": cleanup_completed,
        "manual_image_cleanup_completed": manual_image_cleanup_completed,
        "request_hashes": request_hashes,
        "response_summaries": response_summaries,
    }
    path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2) + "\r\n", encoding="utf-8")
    return path
