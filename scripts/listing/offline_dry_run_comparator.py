from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIELDS_COMPARED = [
    "asin",
    "store_code",
    "listing_status",
    "execution_allowed",
    "blocking_reasons",
    "warnings",
    "amazon_result",
    "keepa_result",
    "resolved_fields",
    "resolved_attributes",
    "genre_id",
    "seller_count",
    "minimum_seller_count",
    "allowed_phrase_matches",
    "matched_forbidden_words",
    "legacy_spacing_reviews",
    "image_urls",
    "image_download_plan",
    "item_payload",
    "inventory_payload",
    "title",
    "description_pc",
    "description_sp",
    "standardPrice",
    "inventory_quantity",
    "management_number",
]

DYNAMIC_FIELDS = {
    "management_number",
}

ORDER_INSENSITIVE_FIELDS = {
    "blocking_reasons",
    "warnings",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalized(inner) for key, inner in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_normalized(inner) for inner in value]
    return value


def _normalize_field(name: str, value: Any) -> Any:
    normalized = _normalized(value)
    if name in ORDER_INSENSITIVE_FIELDS and isinstance(normalized, list):
        return sorted(normalized, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return normalized


def _extract_field_map(payload: dict[str, Any]) -> dict[str, Any]:
    item_payload = payload.get("item_payload") or {}
    inventory_payload = payload.get("inventory_payload") or {}
    seller_eval = payload.get("seller_count_evaluation") or {}
    evaluation = payload.get("evaluation") or {}
    return {
        "asin": payload.get("asin"),
        "store_code": payload.get("store_code"),
        "listing_status": payload.get("listing_status"),
        "execution_allowed": payload.get("execution_allowed"),
        "blocking_reasons": payload.get("blocking_reasons") or [],
        "warnings": payload.get("warnings") or [],
        "amazon_result": payload.get("amazon_result"),
        "keepa_result": payload.get("keepa_result"),
        "resolved_fields": payload.get("resolved_fields"),
        "resolved_attributes": payload.get("resolved_attributes"),
        "genre_id": item_payload.get("genreId") if item_payload else ((payload.get("resolved_fields") or {}).get("genre_id") or {}).get("value"),
        "seller_count": seller_eval.get("actual_value"),
        "minimum_seller_count": seller_eval.get("minimum_value"),
        "allowed_phrase_matches": payload.get("allowed_phrase_matches") or [],
        "matched_forbidden_words": payload.get("matched_forbidden_words") or [],
        "legacy_spacing_reviews": payload.get("legacy_spacing_reviews") or [],
        "image_urls": payload.get("image_urls") or [],
        "image_download_plan": payload.get("image_download_plan"),
        "item_payload": item_payload or None,
        "inventory_payload": inventory_payload or None,
        "title": item_payload.get("title") if item_payload else evaluation.get("title"),
        "description_pc": item_payload.get("productDescription", {}).get("pc") if item_payload else evaluation.get("description_pc"),
        "description_sp": item_payload.get("productDescription", {}).get("sp") if item_payload else evaluation.get("description_sp"),
        "standardPrice": item_payload.get("standardPrice") if item_payload else None,
        "inventory_quantity": inventory_payload.get("inventoryType", {}).get("normalInventory") if inventory_payload else None,
        "management_number": payload.get("management_number"),
    }


def _management_consistency(payload: dict[str, Any]) -> dict[str, Any]:
    management_number = payload.get("management_number")
    item_payload = payload.get("item_payload") or {}
    inventory_payload = payload.get("inventory_payload") or {}
    inventory_variant = inventory_payload.get("variantPath") or {}
    checks = {
        "top_level_matches_item_payload": (
            item_payload.get("managementNumber") == management_number
            or item_payload.get("itemNumber") == management_number
        )
        if item_payload
        else management_number is None,
        "top_level_matches_inventory_payload": (
            inventory_payload.get("managementNumber") == management_number
            or inventory_variant.get("managementNumber") == management_number
            or inventory_variant.get("variantKey") == management_number
        )
        if inventory_payload
        else management_number is None,
    }
    return checks


def compare_offline_dry_runs(source_path: Path, offline_path: Path) -> dict[str, Any]:
    source = _load_json(source_path)
    offline = _load_json(offline_path)
    source_fields = _extract_field_map(source)
    offline_fields = _extract_field_map(offline)

    equal_fields: list[str] = []
    different_fields: list[dict[str, Any]] = []
    ignored_dynamic_fields: list[str] = []
    business_logic_differences: list[dict[str, Any]] = []
    missing_fields: list[dict[str, Any]] = []
    unexpected_differences: list[dict[str, Any]] = []

    for field in FIELDS_COMPARED:
        source_value = source_fields.get(field)
        offline_value = offline_fields.get(field)

        if source_value is None and offline_value is None:
            equal_fields.append(field)
            continue
        if source_value is None or offline_value is None:
            missing_fields.append(
                {
                    "field": field,
                    "source_present": source_value is not None,
                    "offline_present": offline_value is not None,
                    "classification": "missing_field",
                }
            )
            continue

        left = _normalize_field(field, source_value)
        right = _normalize_field(field, offline_value)
        if left == right:
            equal_fields.append(field)
            continue

        if field in DYNAMIC_FIELDS:
            ignored_dynamic_fields.append(field)
            different_fields.append(
                {
                    "field": field,
                    "classification": "expected_dynamic_difference",
                    "source_value": source_value,
                    "offline_value": offline_value,
                }
            )
            continue

        classification = "business_logic_difference"
        entry = {
            "field": field,
            "classification": classification,
            "source_value": source_value,
            "offline_value": offline_value,
        }
        different_fields.append(entry)
        business_logic_differences.append(entry)

    comparison_status = "equivalent"
    if business_logic_differences or missing_fields or unexpected_differences:
        comparison_status = "different"
    elif ignored_dynamic_fields:
        comparison_status = "equivalent_with_dynamic_differences"

    review_required = comparison_status == "different"
    return {
        "source_dry_run_path": str(Path(source_path)),
        "offline_dry_run_path": str(Path(offline_path)),
        "comparison_status": comparison_status,
        "fields_compared": list(FIELDS_COMPARED),
        "equal_fields": equal_fields,
        "different_fields": different_fields,
        "ignored_dynamic_fields": ignored_dynamic_fields,
        "business_logic_differences": business_logic_differences,
        "missing_fields": missing_fields,
        "unexpected_differences": unexpected_differences,
        "review_required": review_required,
        "source_management_consistency": _management_consistency(source),
        "offline_management_consistency": _management_consistency(offline),
    }
