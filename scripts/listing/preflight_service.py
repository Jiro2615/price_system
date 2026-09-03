from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.listing.models import to_jsonable
from scripts.listing.rakuten_inventory_client import build_inventory_request
from scripts.listing.rakuten_item_client import build_item_request
from scripts.listing.rakuten_transport import rakuten_auth_env_status
from scripts.listing.store_config import get_store_cabinet_config


BASE_DIR = Path(__file__).resolve().parents[2]
REPRESENTATIVE_COLOR = "代表カラー"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ensure_output_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _hash_payload(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    normalized = json.dumps(to_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(normalized.encode("utf-8")).hexdigest()


def _path_only(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.path or None


def _build_check(key: str, value: Any, expected: Any, status: str, note: str | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "status": status,
        "value": value,
        "expected": expected,
        "note": note,
    }


def _first_variant(item_payload: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not isinstance(item_payload, dict):
        return "", {}
    variants = item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return "", {}
    variant_key = str(next(iter(variants.keys())) or "").strip()
    variant_payload = next(iter(variants.values()))
    if not isinstance(variant_payload, dict):
        return variant_key, {}
    return variant_key, variant_payload


def _extract_attribute_values(item_payload: dict[str, Any] | None) -> list[dict[str, str]]:
    _, variant_payload = _first_variant(item_payload)
    values: list[dict[str, str]] = []
    for attribute in variant_payload.get("attributes") or []:
        if not isinstance(attribute, dict):
            continue
        raw_values = attribute.get("values")
        value = ""
        if isinstance(raw_values, list):
            for item in raw_values:
                value = str(item or "").strip()
                if value:
                    break
        if not value:
            value = str(attribute.get("value") or "").strip()
        values.append(
            {
                "name": str(attribute.get("name") or "").strip(),
                "value": value,
            }
        )
    return values


def _extract_attribute_value(item_payload: dict[str, Any] | None, attribute_name: str) -> str:
    for attribute in _extract_attribute_values(item_payload):
        if attribute["name"] == attribute_name:
            return attribute["value"]
    return ""


def _extract_required_unresolved_fields(dry_run_result: dict[str, Any]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for name, field in (dry_run_result.get("resolved_attributes") or {}).items():
        if not isinstance(field, dict):
            continue
        if field.get("resolution_action") == "needs_review" or not str(field.get("value") or "").strip():
            unresolved.append(
                {
                    "attribute_name": str(name),
                    "resolution_action": field.get("resolution_action"),
                    "source": field.get("source"),
                    "raw_path": field.get("raw_path"),
                    "evidence": field.get("evidence"),
                }
            )
    return unresolved


def _contains_representative_color(item_payload: dict[str, Any] | None) -> bool:
    return bool(_extract_attribute_value(item_payload, REPRESENTATIVE_COLOR))


def _requires_representative_color(item_payload: dict[str, Any] | None) -> bool:
    if not isinstance(item_payload, dict):
        return False
    if str(item_payload.get("genreId") or "") == "213661":
        return True
    return any(attribute["name"] == REPRESENTATIVE_COLOR for attribute in _extract_attribute_values(item_payload))


def _build_unresolved_specifications(dry_run_result: dict[str, Any]) -> list[dict[str, Any]]:
    item_payload = dry_run_result.get("item_payload")
    if not isinstance(item_payload, dict):
        return []
    image_plan = dry_run_result.get("image_download_plan") or {}
    has_images = bool((image_plan.get("items") or [])) if isinstance(image_plan, dict) else False
    if not has_images:
        return []
    cabinet_config = get_store_cabinet_config(str(dry_run_result.get("store_code") or ""))
    if cabinet_config:
        return []
    return [
        {
            "field": "cabinet_destination",
            "human_confirmation_required": True,
            "reason": "image upload destination requires cabinet_folder_id / cabinet_folder_path / shop_url before real execute",
            "details": {
                "required_runtime_config": ["cabinet_folder_id", "cabinet_folder_path", "shop_url"],
            },
        }
    ]


def _text_issue(field: str, character: str, codepoint: int, position: int, reason: str, severity: str) -> dict[str, Any]:
    return {
        "field": field,
        "character": character,
        "codepoint": f"U+{codepoint:04X}",
        "position": position,
        "reason": reason,
        "severity": severity,
    }


def _validate_text(field: str, text: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for position, character in enumerate(text):
        codepoint = ord(character)
        if character in "\r\n\t":
            continue
        if codepoint < 0x20 or codepoint == 0x7F:
            issues.append(_text_issue(field, character, codepoint, position, "control_character", "blocked"))
        elif 0xD800 <= codepoint <= 0xDFFF:
            issues.append(_text_issue(field, character, codepoint, position, "surrogate_code_point", "blocked"))
        elif 0xE000 <= codepoint <= 0xF8FF or 0xF0000 <= codepoint <= 0xFFFFD or 0x100000 <= codepoint <= 0x10FFFD:
            issues.append(_text_issue(field, character, codepoint, position, "private_use_character", "blocked"))
        elif codepoint == 0xFFFD:
            issues.append(_text_issue(field, character, codepoint, position, "replacement_character", "warning"))
    return issues


def _validate_max_utf8_bytes(field: str, text: str, limit: int) -> list[dict[str, Any]]:
    byte_count = len(text.encode("utf-8"))
    if byte_count <= limit:
        return []
    return [{
        "field": field,
        "character": "",
        "codepoint": "",
        "position": len(text),
        "reason": "max_utf8_bytes_exceeded",
        "severity": "blocked",
        "value": byte_count,
        "expected": limit,
    }]


def _build_text_validation_issues(dry_run_result: dict[str, Any]) -> list[dict[str, Any]]:
    item_payload = dry_run_result.get("item_payload") or {}
    description = item_payload.get("productDescription") or {}
    issues: list[dict[str, Any]] = []
    if isinstance(item_payload, dict):
        issues.extend(_validate_text("title", str(item_payload.get("title") or "")))
    if isinstance(description, dict):
        for field, value in (("description_pc", str(description.get("pc") or "")), ("description_sp", str(description.get("sp") or ""))):
            issues.extend(_validate_text(field, value))
            # Item API 2.0: productDescription.pc / sp are each max 10,240 bytes.
            issues.extend(_validate_max_utf8_bytes(field, value, 10240))
    for attribute in _extract_attribute_values(item_payload):
        issues.extend(_validate_text(f"attribute:{attribute['name']}", attribute["value"]))
    return issues


def _build_management_number_consistency(dry_run_result: dict[str, Any], argument_management_number: str = "") -> dict[str, Any]:
    management_number = str(dry_run_result.get("management_number") or "").strip()
    item_payload = dry_run_result.get("item_payload") or {}
    inventory_payload = dry_run_result.get("inventory_payload") or {}
    variant_key, _ = _first_variant(item_payload)
    item_number = str(item_payload.get("itemNumber") or "").strip() if isinstance(item_payload, dict) else ""
    inventory_variant = inventory_payload.get("variantPath") or {}
    inventory_management = str(inventory_variant.get("managementNumber") or "").strip() if isinstance(inventory_variant, dict) else ""
    inventory_variant_key = str(inventory_variant.get("variantKey") or "").strip() if isinstance(inventory_variant, dict) else ""
    values = [management_number, item_number, variant_key, inventory_management, inventory_variant_key]
    present_values = [value for value in values if value]
    argument_match = (not argument_management_number) or argument_management_number == management_number
    return {
        "dry_run_management_number": management_number,
        "argument_management_number": argument_management_number,
        "item_payload_itemNumber": item_number,
        "item_payload_variant_key": variant_key,
        "inventory_payload_managementNumber": inventory_management,
        "inventory_payload_variantKey": inventory_variant_key,
        "all_match": bool(present_values) and len(set(present_values)) == 1 and argument_match,
        "argument_match": argument_match,
    }


def _build_image_summary(dry_run_result: dict[str, Any]) -> dict[str, Any]:
    image_urls = list(dry_run_result.get("image_urls") or [])
    image_plan = dry_run_result.get("image_download_plan") or {}
    plan_items = list(image_plan.get("items") or []) if isinstance(image_plan, dict) else []
    main_items = [item for item in plan_items if isinstance(item, dict) and str(item.get("role") or "") == "main"]
    sub_items = [item for item in plan_items if isinstance(item, dict) and str(item.get("role") or "") == "sub"]
    return {
        "image_urls_count": len(image_urls),
        "main_image_url": image_urls[0] if image_urls else None,
        "image_plan_count": len(plan_items),
        "main_image_plan_count": len(main_items),
        "sub_image_plan_count": len(sub_items),
        "plan_items": [
            {
                "role": item.get("role"),
                "order": item.get("order"),
                "source_url": item.get("source_url"),
                "planned_filename": item.get("planned_filename"),
                "planned_relative_path": item.get("planned_relative_path"),
            }
            for item in plan_items
            if isinstance(item, dict)
        ],
    }


def _build_item_payload_summary(dry_run_result: dict[str, Any]) -> dict[str, Any]:
    item_payload = dry_run_result.get("item_payload")
    if not isinstance(item_payload, dict):
        return {}
    management_number = str(dry_run_result.get("management_number") or item_payload.get("itemNumber") or "").strip()
    store_code = str(dry_run_result.get("store_code") or "").strip()
    request = build_item_request(management_number, item_payload, {}, store_code=store_code)
    variant_key, variant_payload = _first_variant(item_payload)
    return {
        "itemNumber": request.payload.get("itemNumber"),
        "title": request.payload.get("title"),
        "genreId": request.payload.get("genreId"),
        "standardPrice": ((next(iter((request.payload.get("variants") or {}).values()), {}) or {}).get("standardPrice")),
        "attribute_count": len((next(iter((request.payload.get("variants") or {}).values()), {}) or {}).get("attributes") or []),
        "attributes": (next(iter((request.payload.get("variants") or {}).values()), {}) or {}).get("attributes") or [],
        "variant_key": variant_key,
        "payload_hash": _hash_payload(request.payload),
        "endpoint_path": _path_only(request.url),
    }


def _build_inventory_payload_summary(dry_run_result: dict[str, Any]) -> dict[str, Any]:
    inventory_payload = dry_run_result.get("inventory_payload")
    management_number = str(dry_run_result.get("management_number") or "").strip()
    if not isinstance(inventory_payload, dict) or not management_number:
        return {}
    store_code = str(dry_run_result.get("store_code") or "").strip()
    request = build_inventory_request(management_number, inventory_payload, {}, store_code=store_code)
    return {
        "quantity": request.payload.get("quantity"),
        "variantPath": inventory_payload.get("variantPath"),
        "shipFromIds": request.payload.get("shipFromIds"),
        "operationLeadTime": request.payload.get("operationLeadTime"),
        "payload_hash": _hash_payload(request.payload),
        "endpoint_path": _path_only(request.url),
        "variant_id": request.variant_id,
    }


def _build_auth_configuration_summary(store_code: str) -> dict[str, Any]:
    auth_status = rakuten_auth_env_status(store_code)
    configured = bool(auth_status.get("configured"))
    return {
        "store_code": store_code,
        "store_specific_config_present": bool(store_code),
        "shared_rakuten_api_auth_configured": configured,
        "item_api_auth_configured": configured,
        "inventory_api_auth_configured": configured,
        "image_api_auth_configured": configured,
        "missing_keys": [] if configured else list(auth_status.get("missing_keys") or []),
        "notes": [
            "item / inventory / image transport use store-scoped ESA credentials when store_code is present",
            "real execute still requires cabinet_folder_id / cabinet_folder_path / shop_url runtime config",
        ],
    }


def _severity_status(issues: list[dict[str, Any]]) -> str:
    severities = {str(issue.get("severity") or "") for issue in issues}
    if "blocked" in severities:
        return "blocked"
    if "warning" in severities:
        return "warning"
    return "ok"


def _field_value(field: Any) -> Any:
    """Read a resolved attribute value from its runtime object or JSON form."""
    if isinstance(field, dict):
        return field.get("value")
    return getattr(field, "value", None)


def _required_attribute_check(
    *,
    key: str,
    attribute_name: str,
    item_payload: dict[str, Any],
    resolved_attributes: dict[str, Any],
) -> dict[str, Any]:
    """Validate a named attribute only when the selected genre requires it.

    ``resolved_attributes`` is built from the selected genre's attribute
    definition.  The item payload is also consulted so a malformed payload
    cannot silently omit an attribute that was already resolved.  Attribute
    policy supplies ``-`` for a required but unknown value, therefore an empty
    value here is a payload-generation error rather than a reason to require
    the same field for every genre.
    """
    field = resolved_attributes.get(attribute_name)
    required = attribute_name in resolved_attributes or any(
        attribute["name"] == attribute_name
        for attribute in _extract_attribute_values(item_payload)
    )
    value = _field_value(field)
    if value is None:
        value = _extract_attribute_value(item_payload, attribute_name)
    return _build_check(
        key,
        value,
        "non-empty (genre required)" if required else "not required for this genre",
        "ok" if not required or bool(str(value or "").strip()) else "blocked",
        None,
    )


def _build_checks(
    dry_run_result: dict[str, Any],
    *,
    input_json_path: Path,
    asin: str,
    store: str,
    management_number: str,
    unresolved_specifications: list[dict[str, Any]],
    text_validation_issues: list[dict[str, Any]],
    auth_configuration_summary: dict[str, Any],
    management_consistency: dict[str, Any],
) -> list[dict[str, Any]]:
    item_payload = dry_run_result.get("item_payload") or {}
    keepa_result = dry_run_result.get("keepa_result") or {}
    keepa_ean = keepa_result.get("ean") if isinstance(keepa_result, dict) else getattr(keepa_result, "ean", None)
    resolved_attributes = dry_run_result.get("resolved_attributes") or {}
    representative_color = _extract_attribute_value(item_payload, REPRESENTATIVE_COLOR)
    representative_color_required = _requires_representative_color(item_payload)
    unresolved_required_fields = _extract_required_unresolved_fields(dry_run_result)
    seller_eval = dry_run_result.get("seller_count_evaluation") or {}
    seller_actual = seller_eval.get("actual_value")
    seller_minimum = seller_eval.get("minimum_value")
    seller_passed = seller_eval.get("passed")
    text_status = _severity_status(text_validation_issues)
    auth_ok = (
        auth_configuration_summary.get("item_api_auth_configured")
        and auth_configuration_summary.get("inventory_api_auth_configured")
        and auth_configuration_summary.get("image_api_auth_configured")
    )
    checks = [
        _build_check("input_json_exists", str(input_json_path), True, "ok" if input_json_path.exists() else "blocked", None),
        _build_check("input_json_parsed", True, True, "ok", None),
        _build_check("asin_match", dry_run_result.get("asin"), asin, "ok" if str(dry_run_result.get("asin") or "") == asin else "blocked", None),
        _build_check(
            "store_code_match",
            dry_run_result.get("store_code"),
            store,
            "ok" if (not store or str(dry_run_result.get("store_code") or "") == store) else "blocked",
            None,
        ),
        _build_check("listing_status", dry_run_result.get("listing_status"), "eligible", "ok" if dry_run_result.get("listing_status") == "eligible" else "blocked", None),
        _build_check("execution_allowed", dry_run_result.get("execution_allowed"), True, "ok" if dry_run_result.get("execution_allowed") is True else "blocked", None),
        _build_check(
            "blocking_reasons",
            list(dry_run_result.get("blocking_reasons") or []),
            [],
            "ok" if not list(dry_run_result.get("blocking_reasons") or []) else "blocked",
            None,
        ),
        _build_check(
            "matched_forbidden_words",
            list(dry_run_result.get("matched_forbidden_words") or []),
            [],
            "ok" if not list(dry_run_result.get("matched_forbidden_words") or []) else "blocked",
            None,
        ),
        _build_check(
            "legacy_spacing_reviews",
            list(dry_run_result.get("legacy_spacing_reviews") or []),
            [],
            "ok" if not list(dry_run_result.get("legacy_spacing_reviews") or []) else "blocked",
            None,
        ),
        _build_check(
            "unresolved_required_fields",
            unresolved_required_fields,
            [],
            "ok" if not unresolved_required_fields else "blocked",
            None,
        ),
        _build_check("title_present", str(item_payload.get("title") or ""), "non-empty", "ok" if str(item_payload.get("title") or "").strip() else "blocked", None),
        _build_check(
            "title_contains_legacy_spacing_artifact",
            "ク リア" in str(item_payload.get("title") or ""),
            False,
            "ok" if "ク リア" not in str(item_payload.get("title") or "") else "blocked",
            None,
        ),
        _build_check(
            "description_pc_present",
            str((item_payload.get("productDescription") or {}).get("pc") or ""),
            "non-empty",
            "ok" if str((item_payload.get("productDescription") or {}).get("pc") or "").strip() else "blocked",
            None,
        ),
        _build_check(
            "description_sp_present",
            str((item_payload.get("productDescription") or {}).get("sp") or ""),
            "non-empty",
            "ok" if str((item_payload.get("productDescription") or {}).get("sp") or "").strip() else "blocked",
            None,
        ),
        _build_check("genreId", item_payload.get("genreId"), "non-null", "ok" if item_payload.get("genreId") is not None else "blocked", None),
        _build_check("jan_ean", keepa_ean, "non-empty", "ok" if str(keepa_ean or "").strip() else "blocked", None),
        _required_attribute_check(
            key="brand",
            attribute_name="ブランド名",
            item_payload=item_payload,
            resolved_attributes=resolved_attributes,
        ),
        _required_attribute_check(
            key="model",
            attribute_name="メーカー型番",
            item_payload=item_payload,
            resolved_attributes=resolved_attributes,
        ),
        _build_check(
            "representative_color",
            representative_color,
            "non-empty" if representative_color_required else "not required",
            "ok" if (not representative_color_required or representative_color) else "blocked",
            None,
        ),
        _build_check(
            "seller_count_evaluation",
            {"actual": seller_actual, "minimum": seller_minimum, "passed": seller_passed},
            "actual >= minimum or null-safe existing behavior",
            "ok" if seller_passed is not False else "blocked",
            seller_eval.get("reason"),
        ),
        _build_check(
            "management_number_consistency",
            management_consistency,
            {"all_match": True, "argument_match": True},
            "ok" if management_consistency.get("all_match") else "blocked",
            None,
        ),
        _build_check(
            "image_urls_count",
            len(dry_run_result.get("image_urls") or []),
            ">= 1",
            "ok" if len(dry_run_result.get("image_urls") or []) >= 1 else "blocked",
            None,
        ),
        _build_check(
            "image_download_plan_count",
            len((dry_run_result.get("image_download_plan") or {}).get("items") or []),
            ">= 1",
            "ok" if len((dry_run_result.get("image_download_plan") or {}).get("items") or []) >= 1 else "blocked",
            None,
        ),
        _build_check(
            "text_validation",
            text_validation_issues,
            [],
            text_status,
            "Rakuten 送信前の文字種チェック",
        ),
        _build_check(
            "allowed_phrase_matches",
            list(dry_run_result.get("allowed_phrase_matches") or []),
            "diagnostic only",
            "ok",
            None,
        ),
        _build_check(
            "unresolved_specifications",
            unresolved_specifications,
            [],
            "warning" if unresolved_specifications else "ok",
            "mock execute までは進めるが、real execute 前に人手確認が必要です" if unresolved_specifications else None,
        ),
        _build_check(
            "auth_configuration",
            auth_configuration_summary,
            {"item_api_auth_configured": True, "inventory_api_auth_configured": True, "image_api_auth_configured": True},
            "ok" if auth_ok else "warning",
            "auth 未設定は mock execute では warning、real execute では blocked 扱いです" if not auth_ok else None,
        ),
    ]
    return checks


def _derive_preflight_status(checks: list[dict[str, Any]]) -> str:
    statuses = [str(item.get("status") or "") for item in checks]
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "warning"
    return "passed"


def _build_warnings(
    dry_run_result: dict[str, Any],
    *,
    unresolved_specifications: list[dict[str, Any]],
    auth_configuration_summary: dict[str, Any],
    text_validation_issues: list[dict[str, Any]],
) -> list[str]:
    warnings = list(dry_run_result.get("warnings") or [])
    if unresolved_specifications:
        warnings.append("未確定仕様があります: image CABINET destination runtime config は本番前に要確認です")
    if not auth_configuration_summary.get("item_api_auth_configured"):
        warnings.append("item API 認証は未設定または未確認です")
    if not auth_configuration_summary.get("inventory_api_auth_configured"):
        warnings.append("inventory API 認証は未設定または未確認です")
    if not auth_configuration_summary.get("image_api_auth_configured"):
        warnings.append("image upload 認証は未設定または未確認です")
    for issue in text_validation_issues:
        if issue.get("severity") == "warning":
            warnings.append(f"文字チェック warning: {issue.get('field')} {issue.get('codepoint')} {issue.get('reason')}")
    deduped: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning in seen:
            continue
        deduped.append(warning)
        seen.add(warning)
    return deduped


def _build_blocking_reasons(
    dry_run_result: dict[str, Any],
    *,
    checks: list[dict[str, Any]],
    text_validation_issues: list[dict[str, Any]],
) -> list[str]:
    reasons = list(dry_run_result.get("blocking_reasons") or [])
    for check in checks:
        if check.get("status") != "blocked":
            continue
        reasons.append(f"{check.get('key')}: {check.get('note') or check.get('expected')}")
    for issue in text_validation_issues:
        if issue.get("severity") != "blocked":
            continue
        reasons.append(f"text_validation: {issue.get('field')} {issue.get('codepoint')} {issue.get('reason')}")
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        deduped.append(reason)
        seen.add(reason)
    return deduped


def build_preflight_result(
    dry_run_result: dict[str, Any],
    *,
    input_json_path: Path,
    asin: str,
    store: str,
    management_number: str,
) -> dict[str, Any]:
    unresolved_specifications = _build_unresolved_specifications(dry_run_result)
    text_validation_issues = _build_text_validation_issues(dry_run_result)
    auth_configuration_summary = _build_auth_configuration_summary(str(dry_run_result.get("store_code") or store or ""))
    management_consistency = _build_management_number_consistency(dry_run_result, argument_management_number=management_number)
    checks = _build_checks(
        dry_run_result,
        input_json_path=input_json_path,
        asin=asin,
        store=store,
        management_number=management_number,
        unresolved_specifications=unresolved_specifications,
        text_validation_issues=text_validation_issues,
        auth_configuration_summary=auth_configuration_summary,
        management_consistency=management_consistency,
    )
    preflight_status = _derive_preflight_status(checks)
    warnings = _build_warnings(
        dry_run_result,
        unresolved_specifications=unresolved_specifications,
        auth_configuration_summary=auth_configuration_summary,
        text_validation_issues=text_validation_issues,
    )
    blocking_reasons = _build_blocking_reasons(
        dry_run_result,
        checks=checks,
        text_validation_issues=text_validation_issues,
    )
    ready_for_mock_execute = preflight_status != "blocked"
    ready_for_real_execute = (
        preflight_status != "blocked"
        and not unresolved_specifications
        and bool(auth_configuration_summary.get("item_api_auth_configured"))
        and bool(auth_configuration_summary.get("inventory_api_auth_configured"))
        and bool(auth_configuration_summary.get("image_api_auth_configured"))
    )
    return {
        "asin": dry_run_result.get("asin"),
        "store_code": dry_run_result.get("store_code"),
        "management_number": dry_run_result.get("management_number"),
        "source_json": str(input_json_path),
        "preflight_status": preflight_status,
        "checks": checks,
        "warnings": warnings,
        "blocking_reasons": blocking_reasons,
        "unresolved_specifications": unresolved_specifications,
        "human_confirmation_required": bool(unresolved_specifications),
        "text_validation_issues": text_validation_issues,
        "management_number_consistency": management_consistency,
        "image_summary": _build_image_summary(dry_run_result),
        "item_payload_summary": _build_item_payload_summary(dry_run_result),
        "inventory_payload_summary": _build_inventory_payload_summary(dry_run_result),
        "auth_configuration_summary": auth_configuration_summary,
        "ready_for_mock_execute": ready_for_mock_execute,
        "ready_for_real_execute": ready_for_real_execute,
        "external_actions_performed": False,
        "secrets_exposed": False,
    }
