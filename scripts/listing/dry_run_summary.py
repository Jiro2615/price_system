from __future__ import annotations

from typing import Any

from scripts.listing.models import AmazonCheckResult, KeepaProductData, ResolvedField


def _status_for_boolean(value: bool) -> str:
    return "ok" if value else "blocked"


def build_blocking_reasons(
    *,
    listing_status: str,
    listing_reason: str,
    seller_count_evaluation: dict[str, Any] | None,
    existing_management_number: str | None,
) -> list[str]:
    reasons: list[str] = []
    if listing_status == "eligible":
        return reasons
    if listing_status == "already_listed" and existing_management_number:
        reasons.append(f"already_listed: {existing_management_number}")
    elif listing_status:
        reasons.append(f"{listing_status}: {listing_reason}")
    if seller_count_evaluation and seller_count_evaluation.get("passed") is False:
        reasons.append(
            f"seller_count_below_threshold: {seller_count_evaluation.get('actual_value')} < {seller_count_evaluation.get('minimum_value')}"
        )
    return reasons


def build_warnings(
    *,
    existing_warnings: list[str],
    resolved_attributes: dict[str, ResolvedField] | None,
    image_download_plan: dict[str, Any] | None,
    legacy_spacing_reviews: list[dict[str, Any]] | None = None,
    rakuten_api_called: bool = False,
    image_uploaded: bool = False,
) -> list[str]:
    warnings = list(existing_warnings)
    for attr_name, field in (resolved_attributes or {}).items():
        if field.resolution_action == "use_legacy_dash":
            warnings.append(f"{attr_name}: legacy dash fallback used")
        elif field.resolution_action == "use_inferred":
            warnings.append(f"{attr_name}: inferred value used (confidence={field.confidence})")
        elif field.resolution_action == "needs_review":
            warnings.append(f"{attr_name}: requires human review")
        elif field.confidence in {"low", "medium"}:
            warnings.append(f"{attr_name}: confidence={field.confidence}")

    if image_download_plan is not None:
        warnings.append("image download not performed in dry-run")
        warnings.append("image upload not performed in dry-run")
        if image_download_plan.get("items"):
            warnings.append("image validation not checked")

    for review in legacy_spacing_reviews or []:
        field = review.get("field") or "unknown"
        source = review.get("source") or "replacelist_rakuten.txt"
        warnings.append(f"legacy spacing replacement pending migration: field={field}, source={source}")

    if not rakuten_api_called:
        warnings.append("Rakuten API not called in dry-run")
    if not image_uploaded:
        warnings.append("Rakuten image upload not performed")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in warnings:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def build_review_checklist(
    *,
    store_code: str,
    asin: str,
    genre_id: int | None,
    amazon_result: AmazonCheckResult | None,
    keepa_result: KeepaProductData | None,
    resolved_attributes: dict[str, ResolvedField] | None,
    main_image_url: str | None,
    image_urls: list[str],
    seller_count_evaluation: dict[str, Any] | None,
    listing_status: str,
    listing_reason: str,
    existing_management_number: str | None,
    management_number: str | None,
    item_payload: dict[str, Any] | None,
    inventory_payload: dict[str, Any] | None,
    provisional_genre_candidate: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    resolved_attributes = resolved_attributes or {}
    amazon_business_ng = bool(amazon_result.business_ng) if amazon_result else False
    keepa_available = keepa_result is not None
    attribute_keys = ["カラー", "シリーズ名", "ブランド名", "メーカー型番", "原産国／製造国"]

    checklist: list[dict[str, Any]] = [
        {"key": "store_code", "label": "店舗コード", "value": store_code, "status": "ok", "note": ""},
        {"key": "asin", "label": "ASIN", "value": asin, "status": "ok", "note": ""},
        {
            "key": "genre_id",
            "label": "genreId",
            "value": genre_id,
            "status": "ok" if genre_id is not None else "blocked",
            "note": "",
        },
        {
            "key": "amazon_price",
            "label": "Amazon価格",
            "value": None if amazon_result is None else amazon_result.amazon_price,
            "status": "ok" if amazon_result and amazon_result.amazon_price else "blocked",
            "note": "",
        },
        {
            "key": "available_qty",
            "label": "在庫数",
            "value": None if amazon_result is None else amazon_result.available_qty,
            "status": "ok" if amazon_result and amazon_result.available_qty else "blocked",
            "note": "",
        },
        {
            "key": "jan_ean",
            "label": "JAN/EAN",
            "value": None if keepa_result is None else keepa_result.ean,
            "status": "ok" if keepa_result and keepa_result.ean else "warning",
            "note": "pilot item payload sends articleNumber.exemptionReason=5 without articleNumber.value",
        },
    ]

    if provisional_genre_candidate:
        checklist.append(
            {
                "key": "provisional_genre",
                "label": "仮ジャンル",
                "value": provisional_genre_candidate.get("genre_id"),
                "status": "warning",
                "note": provisional_genre_candidate.get("reason", "RMSで確認・必要なら編集してください"),
            }
        )

    for attr_name in attribute_keys:
        field = resolved_attributes.get(attr_name)
        status = "not_checked"
        note = ""
        value = None if field is None else field.value
        if field is not None:
            if field.resolution_action == "needs_review" or not value:
                status = "blocked"
            elif field.resolution_action in {"use_inferred", "use_legacy_dash"} or field.confidence in {"low", "medium"}:
                status = "warning"
                note = field.evidence
            else:
                status = "ok"
        checklist.append({"key": f"attribute_{attr_name}", "label": attr_name, "value": value, "status": status, "note": note})

    checklist.extend(
        [
            {
                "key": "image_count",
                "label": "画像数",
                "value": len(image_urls),
                "status": "ok" if image_urls else "blocked",
                "note": "",
            },
            {
                "key": "main_image_url",
                "label": "メイン画像URL",
                "value": main_image_url,
                "status": "ok" if main_image_url else "blocked",
                "note": "",
            },
            {
                "key": "seller_count_actual",
                "label": "出品者数実値",
                "value": None if not seller_count_evaluation else seller_count_evaluation.get("actual_value"),
                "status": "ok" if not seller_count_evaluation or seller_count_evaluation.get("passed") else "blocked",
                "note": None if not seller_count_evaluation else seller_count_evaluation.get("reason", ""),
            },
            {
                "key": "seller_count_threshold",
                "label": "出品者数閾値",
                "value": None if not seller_count_evaluation else seller_count_evaluation.get("minimum_value"),
                "status": "ok",
                "note": "",
            },
            {
                "key": "amazon_business_ng",
                "label": "Amazon business NG",
                "value": amazon_business_ng,
                "status": "blocked" if amazon_business_ng else "ok",
                "note": None if amazon_result is None else amazon_result.ng_reason,
            },
            {
                "key": "keepa_available",
                "label": "Keepa取得",
                "value": keepa_available,
                "status": "ok" if keepa_available else "blocked",
                "note": "",
            },
            {
                "key": "listing_status",
                "label": "出品判定",
                "value": listing_status,
                "status": "ok" if listing_status == "eligible" else "blocked",
                "note": listing_reason,
            },
            {
                "key": "existing_management_number",
                "label": "既存出品",
                "value": existing_management_number,
                "status": "blocked" if existing_management_number else "ok",
                "note": "",
            },
            {
                "key": "management_number",
                "label": "management number",
                "value": management_number,
                "status": "ok" if management_number else "not_checked",
                "note": "",
            },
            {
                "key": "item_payload_generated",
                "label": "item payload生成",
                "value": item_payload is not None,
                "status": "ok" if item_payload is not None else "not_checked",
                "note": "",
            },
            {
                "key": "inventory_payload_generated",
                "label": "inventory payload生成",
                "value": inventory_payload is not None,
                "status": "ok" if inventory_payload is not None else "not_checked",
                "note": "",
            },
            {
                "key": "image_upload_performed",
                "label": "画像upload",
                "value": False,
                "status": "not_checked",
                "note": "not performed in dry-run",
            },
            {
                "key": "rakuten_api_called",
                "label": "楽天API",
                "value": False,
                "status": "not_checked",
                "note": "not performed in dry-run",
            },
        ]
    )
    return checklist


def build_execution_summary(
    *,
    listing_status: str,
    blocking_reasons: list[str],
    warnings: list[str],
    management_number: str | None,
    item_payload: dict[str, Any] | None,
    inventory_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    can_execute_listing = (
        listing_status == "eligible"
        and not blocking_reasons
        and management_number is not None
        and item_payload is not None
        and inventory_payload is not None
    )
    return {
        "can_execute_listing": can_execute_listing,
        "requires_human_review": bool(blocking_reasons or warnings),
        "external_actions_performed": False,
        "rakuten_api_called": False,
        "image_uploaded": False,
        "db_updated": False,
    }
