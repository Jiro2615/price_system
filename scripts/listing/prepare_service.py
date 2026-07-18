from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from scripts.listing.attribute_resolver import build_resolved_fields
from scripts.listing.common_settings import load_listing_common_settings
from scripts.listing.dry_run_summary import (
    build_blocking_reasons,
    build_execution_summary,
    build_review_checklist,
    build_warnings,
)
from scripts.listing.image_plan import build_image_download_plan
from scripts.listing.listing_evaluator import evaluate_listing
from scripts.listing.management_number import build_management_number_bundle_from_selected, generate_management_number_bundle
from scripts.listing.models import AmazonCheckResult, EvaluationResult, KeepaProductData, ListingCommonSettings, MasterData, StoreSettings
from scripts.listing.rakuten_payload_builder import build_inventory_payload, build_item_payload


T = TypeVar("T")


@dataclass
class PrepareListingRequest:
    asin: str
    store_code: str
    master_dir: Path
    dry_run: bool = False
    offline: bool = False
    skip_amazon: bool = False
    skip_keepa: bool = False
    management_number: str = ""
    allow_missing_master: bool = False
    page_timeout_ms: int = 15000
    store_settings_json: Path | None = None
    amazon_result_json: Path | None = None
    keepa_result_json: Path | None = None


def fetch_keepa_result_sync(asin: str) -> KeepaProductData:
    from scripts.listing.keepa_product_client import KeepaClient, load_keepa_api_key

    keepa_client = KeepaClient(api_key=load_keepa_api_key())
    return keepa_client.fetch_product(asin)


def load_store_settings(store_code: str) -> StoreSettings:
    from scripts.listing.store_config import get_store_settings

    return get_store_settings(store_code)


def load_common_settings(*compatibility_sources: object) -> tuple[ListingCommonSettings, list[str]]:
    return load_listing_common_settings(*compatibility_sources)


def load_master_records(master_dir: Path, allow_missing: bool) -> MasterData:
    from scripts.listing.master_loader import load_master_data

    return load_master_data(master_dir, allow_missing=allow_missing)


def fetch_amazon_result_for_listing(asin: str, page_timeout_ms: int) -> AmazonCheckResult:
    from scripts.listing.amazon_bridge import fetch_amazon_result_sync

    return fetch_amazon_result_sync(asin, page_timeout_ms=page_timeout_ms)


def _load_json_payload(path: Path, label: str) -> dict[str, object]:
    resolved = Path(path)
    if not resolved.exists():
        raise RuntimeError(f"{label} JSON not found: {resolved}")
    return json.loads(resolved.read_text(encoding="utf-8"))


def _extract_embedded_payload(payload: dict[str, object], *, label: str) -> dict[str, object]:
    embedded_key_map = {
        "store settings": "store_settings",
        "Amazon result": "amazon_result",
        "Keepa result": "keepa_result",
    }
    embedded_key = embedded_key_map.get(label)
    if not embedded_key:
        return payload
    embedded = payload.get(embedded_key)
    if isinstance(embedded, dict):
        return embedded
    return payload


def _load_dataclass_from_json(path: Path, cls: type[T], label: str) -> T:
    payload = _load_json_payload(path, label)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON must be an object")
    payload = _extract_embedded_payload(payload, label=label)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} payload must be an object")
    return cls(**payload)


def _resolve_store_settings(
    request: PrepareListingRequest,
    store_settings_loader: Callable[[str], StoreSettings],
) -> StoreSettings:
    if request.offline:
        if request.store_settings_json is None:
            raise RuntimeError("--offline requires --store-settings-json")
        return _load_dataclass_from_json(request.store_settings_json, StoreSettings, "store settings")
    return store_settings_loader(request.store_code)


def _resolve_amazon_result(
    request: PrepareListingRequest,
    asin: str,
    amazon_fetcher: Callable[[str, int], AmazonCheckResult],
    warnings: list[str],
) -> AmazonCheckResult | None:
    if request.offline:
        if request.amazon_result_json is None:
            warnings.append("\u30aa\u30d5\u30e9\u30a4\u30f3\u30e2\u30fc\u30c9: Amazon result JSON \u304c\u6307\u5b9a\u3055\u308c\u3066\u3044\u307e\u305b\u3093")
            return None
        return _load_dataclass_from_json(request.amazon_result_json, AmazonCheckResult, "Amazon result")
    if request.skip_amazon:
        warnings.append("Amazon check skipped by CLI option")
        return None
    return amazon_fetcher(asin, request.page_timeout_ms)


def _resolve_keepa_result(
    request: PrepareListingRequest,
    asin: str,
    keepa_fetcher: Callable[[str], KeepaProductData],
    warnings: list[str],
) -> KeepaProductData | None:
    if request.offline:
        if request.keepa_result_json is None:
            warnings.append("\u30aa\u30d5\u30e9\u30a4\u30f3\u30e2\u30fc\u30c9: Keepa result JSON \u304c\u6307\u5b9a\u3055\u308c\u3066\u3044\u307e\u305b\u3093")
            return None
        return _load_dataclass_from_json(request.keepa_result_json, KeepaProductData, "Keepa result")
    if request.skip_keepa:
        warnings.append("Keepa check skipped by CLI option")
        return None
    return keepa_fetcher(asin)


def _get_text_attr(value: object, name: str) -> str:
    if isinstance(value, dict):
        raw = value.get(name)
    else:
        raw = getattr(value, name, "")
    return str(raw or "").strip()


def _get_bool_attr(value: object, name: str) -> bool:
    if isinstance(value, dict):
        raw = value.get(name)
    else:
        raw = getattr(value, name, False)
    return bool(raw)


def _classify_keepa_fetch_exception(exc: Exception) -> tuple[str, str]:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    if "no products" in lowered or "no product" in lowered or "product not found" in lowered:
        return ("missing_required_data", message)
    return ("system_error", message)


def _classify_keepa_result_value(keepa_result: object) -> tuple[str, str] | None:
    if keepa_result is None or isinstance(keepa_result, KeepaProductData):
        return None
    if _get_bool_attr(keepa_result, "system_error"):
        reason = _get_text_attr(keepa_result, "ng_reason") or _get_text_attr(keepa_result, "error") or "Keepa system error"
        return ("system_error", reason)
    if _get_bool_attr(keepa_result, "business_ng"):
        reason = _get_text_attr(keepa_result, "ng_reason") or _get_text_attr(keepa_result, "error") or "Keepa business NG"
        return ("business_ng", reason)
    if isinstance(keepa_result, dict) and not keepa_result:
        return ("missing_required_data", "Keepa result is empty")
    return None


def _base_result(
    *,
    mode: str,
    asin: str,
    amazon_result: AmazonCheckResult | None,
    keepa_result: KeepaProductData | None,
    listing_status: str,
    listing_reason: str,
    warnings: list[str],
    missing_master_files: list[str],
    master_dir: Path,
    store_settings: StoreSettings,
    common_settings: ListingCommonSettings,
    matched_master_rules: list[object] | None = None,
    management_number: str | None = None,
    management_number_candidates: object | None = None,
    resolved_fields: dict[str, object] | None = None,
    resolved_attributes: dict[str, object] | None = None,
    seller_count_evaluation: dict[str, object] | None = None,
    allowed_phrase_matches: list[dict[str, object]] | None = None,
    matched_forbidden_words: list[dict[str, object]] | None = None,
    required_separate_checks: list[str] | None = None,
    matched_separate_check_phrases: list[dict[str, object]] | None = None,
    legacy_spacing_reviews: list[dict[str, object]] | None = None,
    main_image_url: str | None = None,
    image_urls: list[str] | None = None,
    image_source: str | None = None,
    image_download_plan: dict[str, object] | None = None,
    item_payload: dict[str, object] | None = None,
    inventory_payload: dict[str, object] | None = None,
    image_candidates: list[dict[str, str]] | None = None,
    existing_management_number: str | None = None,
    representative_color_mapping: dict[str, object] | None = None,
    provisional_genre_candidate: dict[str, object] | None = None,
) -> dict[str, object]:
    genre_id_value = None
    if item_payload is not None:
        genre_id_value = item_payload.get("genreId")
    elif isinstance(resolved_fields, dict):
        raw_genre = resolved_fields.get("genre_id")
        if isinstance(raw_genre, dict):
            genre_id_value = raw_genre.get("value")
        else:
            genre_id_value = getattr(raw_genre, "value", None)

    blocking_reasons = build_blocking_reasons(
        listing_status=listing_status,
        listing_reason=listing_reason,
        seller_count_evaluation=seller_count_evaluation,
        existing_management_number=existing_management_number,
    )
    computed_warnings = build_warnings(
        existing_warnings=warnings,
        resolved_attributes=resolved_attributes,
        image_download_plan=image_download_plan,
        legacy_spacing_reviews=legacy_spacing_reviews,
    )
    review_checklist = build_review_checklist(
        store_code=store_settings.store_code,
        asin=asin,
        genre_id=genre_id_value,
        amazon_result=amazon_result,
        keepa_result=keepa_result,
        resolved_attributes=resolved_attributes,
        main_image_url=main_image_url,
        image_urls=list(image_urls or []),
        seller_count_evaluation=seller_count_evaluation,
        listing_status=listing_status,
        listing_reason=listing_reason,
        existing_management_number=existing_management_number,
        management_number=management_number,
        item_payload=item_payload,
        inventory_payload=inventory_payload,
        provisional_genre_candidate=provisional_genre_candidate,
    )
    execution_summary = build_execution_summary(
        listing_status=listing_status,
        blocking_reasons=blocking_reasons,
        warnings=computed_warnings,
        management_number=management_number,
        item_payload=item_payload,
        inventory_payload=inventory_payload,
    )
    return {
        "mode": mode,
        "asin": asin,
        "store_code": store_settings.store_code,
        "amazon_result": amazon_result,
        "keepa_result": keepa_result,
        "matched_master_rules": matched_master_rules or [],
        "listing_status": listing_status,
        "listing_reason": listing_reason,
        "execution_allowed": execution_summary["can_execute_listing"],
        "blocking_reasons": blocking_reasons,
        "management_number": management_number,
        "existing_management_number": existing_management_number,
        "management_number_candidates": management_number_candidates,
        "resolved_fields": resolved_fields,
        "resolved_attributes": resolved_attributes,
        "allowed_phrase_matches": allowed_phrase_matches or [],
        "matched_forbidden_words": matched_forbidden_words or [],
        "required_separate_checks": required_separate_checks or [],
        "matched_separate_check_phrases": matched_separate_check_phrases or [],
        "legacy_spacing_reviews": legacy_spacing_reviews or [],
        "main_image_url": main_image_url,
        "image_urls": image_urls or [],
        "image_source": image_source or "none",
        "image_download_plan": image_download_plan,
        "item_payload": item_payload,
        "inventory_payload": inventory_payload,
        "image_candidates": image_candidates or [],
        "representative_color_mapping": representative_color_mapping or {},
        "provisional_genre_candidate": provisional_genre_candidate or {},
        "warnings": computed_warnings,
        "missing_master_files": missing_master_files,
        "master_dir": str(Path(master_dir).resolve()),
        "common_settings": {
            "min_avg90_new_offer_count": common_settings.min_avg90_new_offer_count,
        },
        "store_settings": {
            "store_code": store_settings.store_code,
            "max_stock": store_settings.max_stock,
            "normal_delivery_date_id": store_settings.normal_delivery_date_id,
            "back_order_delivery_date_id": store_settings.back_order_delivery_date_id,
            "normal_delivery_time_id": store_settings.normal_delivery_time_id,
            "back_order_delivery_time_id": store_settings.back_order_delivery_time_id,
            "ship_from_ids": store_settings.ship_from_ids,
            "cabinet": getattr(store_settings, "cabinet", {}) or {},
        },
        "seller_count_evaluation": seller_count_evaluation,
        "review_checklist": review_checklist,
        "execution_summary": execution_summary,
    }


def _extract_item_attribute_value(item_payload: dict[str, object] | None, attribute_name: str) -> str:
    if not isinstance(item_payload, dict):
        return ""
    variants = item_payload.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return ""
    first_variant = next(iter(variants.values()))
    if not isinstance(first_variant, dict):
        return ""
    for attribute in first_variant.get("attributes") or []:
        if isinstance(attribute, dict) and str(attribute.get("name") or "") == attribute_name:
            raw_values = attribute.get("values")
            if isinstance(raw_values, list):
                for item in raw_values:
                    value = str(item or "").strip()
                    if value:
                        return value
            return str(attribute.get("value") or "").strip()
    return ""


def _build_representative_color_mapping(
    resolved_attributes: dict[str, object] | None,
    item_payload: dict[str, object] | None,
) -> dict[str, object]:
    resolved_attributes = resolved_attributes or {}
    original_value = ""
    raw_field = resolved_attributes.get("代表カラー")
    if isinstance(raw_field, dict):
        original_value = str(raw_field.get("value") or "").strip()
    else:
        original_value = str(getattr(raw_field, "value", "") or "").strip()
    api_value = _extract_item_attribute_value(item_payload, "代表カラー")
    if not original_value and not api_value:
        return {}
    return {
        "original_value": original_value,
        "api_value": api_value,
        "reason": "SELECTIVE attribute for genreId=213661 requires dictionary value" if original_value and api_value and original_value != api_value else "API value matches extracted value",
        "attribute_id": 8 if original_value or api_value else None,
    }


def _classify_amazon_result(asin: str, amazon_result: AmazonCheckResult | None) -> tuple[str, str] | None:
    if amazon_result is None:
        return None
    if amazon_result.system_error:
        return ("system_error", amazon_result.ng_reason or "Amazon確認でシステムエラー")
    if amazon_result.business_ng:
        return ("business_ng", amazon_result.ng_reason or "Amazon確認でNG")
    if amazon_result.page_asin and amazon_result.page_asin != asin:
        return ("business_ng", "ASIN不一致")
    if amazon_result.amazon_price is None or amazon_result.amazon_price <= 0:
        return ("business_ng", "Amazon価格が取得できません")
    if amazon_result.available_qty is None or amazon_result.available_qty <= 0:
        return ("business_ng", "Amazon在庫がありません")
    if amazon_result.gift_available is not True:
        return ("business_ng", "Amazonギフト設定が無効です")
    return None


def prepare_listing(
    request: PrepareListingRequest,
    *,
    store_settings_loader: Callable[[str], StoreSettings] = load_store_settings,
    master_data_loader: Callable[[Path, bool], MasterData] = load_master_records,
    amazon_fetcher: Callable[[str, int], AmazonCheckResult] = fetch_amazon_result_for_listing,
    keepa_fetcher: Callable[[str], KeepaProductData] = fetch_keepa_result_sync,
    resolved_fields_builder: Callable[..., dict[str, object]] = build_resolved_fields,
    image_plan_builder: Callable[..., dict[str, object]] = build_image_download_plan,
    evaluator: Callable[..., EvaluationResult] = evaluate_listing,
    common_settings_loader: Callable[..., tuple[ListingCommonSettings, list[str]]] = load_common_settings,
    management_number_builder: Callable[[str], object] = generate_management_number_bundle,
    item_payload_builder: Callable[..., dict[str, object]] = build_item_payload,
    inventory_payload_builder: Callable[..., dict[str, object]] = build_inventory_payload,
) -> dict[str, object]:
    asin = request.asin.strip().upper()
    warnings: list[str] = []
    mode = "offline" if request.offline else "dry_run"

    if request.offline:
        warnings.append("\u30aa\u30d5\u30e9\u30a4\u30f3\u30e2\u30fc\u30c9: \u30ed\u30fc\u30ab\u30eb fixture JSON \u306e\u307f\u3092\u4f7f\u7528\u3057\u307e\u3059")
    elif not request.dry_run:
        warnings.append("\u3053\u306e\u30b3\u30de\u30f3\u30c9\u306f\u975e\u7834\u58ca\u30e2\u30fc\u30c9\u5c02\u7528\u306e\u305f\u3081\u3001dry-run \u3068\u3057\u3066\u7d9a\u884c\u3057\u307e\u3059")

    store_settings = _resolve_store_settings(request, store_settings_loader)
    common_settings, common_setting_warnings = common_settings_loader(store_settings)
    warnings.extend(common_setting_warnings)
    master_data = master_data_loader(Path(request.master_dir), request.allow_missing_master)

    existing_management_number = master_data.listed_asins.get(asin, "")
    if existing_management_number:
        return _base_result(
            mode=mode,
            asin=asin,
            amazon_result=None,
            keepa_result=None,
            listing_status="already_listed",
            listing_reason=f"既に出品済み: {existing_management_number}",
            warnings=warnings + [f"listed ASIN matched before external checks: {asin}"],
            missing_master_files=master_data.missing_files,
            master_dir=Path(request.master_dir),
            store_settings=store_settings,
            common_settings=common_settings,
            existing_management_number=existing_management_number,
        )

    amazon_result = _resolve_amazon_result(request, asin, amazon_fetcher, warnings)
    amazon_classification = _classify_amazon_result(asin, amazon_result)
    if amazon_classification is not None:
        listing_status, listing_reason = amazon_classification
        return _base_result(
            mode=mode,
            asin=asin,
            amazon_result=amazon_result,
            keepa_result=None,
            listing_status=listing_status,
            listing_reason=listing_reason,
            warnings=warnings,
            missing_master_files=master_data.missing_files,
            master_dir=Path(request.master_dir),
            store_settings=store_settings,
            common_settings=common_settings,
        )

    try:
        keepa_result = _resolve_keepa_result(request, asin, keepa_fetcher, warnings)
    except Exception as exc:
        listing_status, listing_reason = _classify_keepa_fetch_exception(exc)
        return _base_result(
            mode=mode,
            asin=asin,
            amazon_result=amazon_result,
            keepa_result=None,
            listing_status=listing_status,
            listing_reason=listing_reason,
            warnings=warnings,
            missing_master_files=master_data.missing_files,
            master_dir=Path(request.master_dir),
            store_settings=store_settings,
            common_settings=common_settings,
        )

    keepa_classification = _classify_keepa_result_value(keepa_result)
    if keepa_classification is not None:
        listing_status, listing_reason = keepa_classification
        return _base_result(
            mode=mode,
            asin=asin,
            amazon_result=amazon_result,
            keepa_result=None,
            listing_status=listing_status,
            listing_reason=listing_reason,
            warnings=warnings,
            missing_master_files=master_data.missing_files,
            master_dir=Path(request.master_dir),
            store_settings=store_settings,
            common_settings=common_settings,
        )

    resolved_fields = resolved_fields_builder(
        amazon_result=amazon_result,
        keepa_result=keepa_result,
        master_data=master_data,
    )
    main_image_url = keepa_result.image_urls[0] if keepa_result and keepa_result.image_urls else None
    image_urls = list(keepa_result.image_urls) if keepa_result else []
    image_source = keepa_result.image_source if keepa_result else "none"

    evaluation = evaluator(
        asin=asin,
        amazon_result=amazon_result,
        keepa_result=keepa_result,
        master_data=master_data,
        store_settings=store_settings,
        management_number=request.management_number.strip() or "",
        resolved_fields=resolved_fields,
        common_settings=common_settings,
    )

    if evaluation.listing_status != "eligible" or amazon_result is None:
        image_download_plan = image_plan_builder(
            asin=asin,
            image_base_name=request.management_number.strip() or asin,
            image_urls=image_urls,
            image_source=image_source,
            listing_status=evaluation.listing_status,
            max_images=store_settings.listing_image_limit,
        )
        return _base_result(
            mode=mode,
            asin=asin,
            amazon_result=amazon_result,
            keepa_result=keepa_result,
            listing_status=evaluation.listing_status,
            listing_reason=evaluation.listing_reason,
            warnings=warnings + list(evaluation.warnings),
            missing_master_files=master_data.missing_files,
            master_dir=Path(request.master_dir),
            store_settings=store_settings,
            common_settings=common_settings,
            matched_master_rules=evaluation.matched_master_rules,
            resolved_fields=resolved_fields,
            resolved_attributes=evaluation.resolved_attributes,
            seller_count_evaluation=evaluation.seller_count_evaluation,
            allowed_phrase_matches=evaluation.allowed_phrase_matches,
            matched_forbidden_words=evaluation.matched_forbidden_words,
            required_separate_checks=evaluation.required_separate_checks,
            matched_separate_check_phrases=evaluation.matched_separate_check_phrases,
            legacy_spacing_reviews=evaluation.legacy_spacing_reviews,
            main_image_url=main_image_url,
            image_urls=image_urls,
            image_source=image_source,
            image_download_plan=image_download_plan,
            image_candidates=evaluation.image_candidates,
            representative_color_mapping=_build_representative_color_mapping(evaluation.resolved_attributes, None),
            provisional_genre_candidate=evaluation.provisional_genre_candidate,
        )

    requested_management_number = request.management_number.strip()
    management_bundle = (
        build_management_number_bundle_from_selected(requested_management_number)
        if requested_management_number
        else management_number_builder(store_settings.management_suffix)
    )
    management_number = requested_management_number or management_bundle.selected
    image_download_plan = image_plan_builder(
        asin=asin,
        image_base_name=management_bundle.legacy_candidate,
        image_urls=image_urls,
        image_source=image_source,
        listing_status=evaluation.listing_status,
        max_images=store_settings.listing_image_limit,
    )

    item_payload = item_payload_builder(
        management_number=management_number,
        evaluation=evaluation,
        store_settings=store_settings,
        amazon_price=int(amazon_result.amazon_price or 0),
        amazon_point=0,
    )
    inventory_payload = inventory_payload_builder(
        management_number=management_number,
        quantity=int(amazon_result.available_qty or 0),
        store_settings=store_settings,
    )
    representative_color_mapping = _build_representative_color_mapping(evaluation.resolved_attributes, item_payload)

    return _base_result(
        mode=mode,
        asin=asin,
        amazon_result=amazon_result,
        keepa_result=keepa_result,
        listing_status=evaluation.listing_status,
        listing_reason=evaluation.listing_reason,
        warnings=warnings + list(evaluation.warnings),
        missing_master_files=master_data.missing_files,
        master_dir=Path(request.master_dir),
        store_settings=store_settings,
        common_settings=common_settings,
        matched_master_rules=evaluation.matched_master_rules,
        management_number=management_number,
        management_number_candidates=management_bundle,
        resolved_fields=resolved_fields,
        resolved_attributes=evaluation.resolved_attributes,
        seller_count_evaluation=evaluation.seller_count_evaluation,
        allowed_phrase_matches=evaluation.allowed_phrase_matches,
        matched_forbidden_words=evaluation.matched_forbidden_words,
        required_separate_checks=evaluation.required_separate_checks,
        matched_separate_check_phrases=evaluation.matched_separate_check_phrases,
        legacy_spacing_reviews=evaluation.legacy_spacing_reviews,
        main_image_url=main_image_url,
        image_urls=image_urls,
        image_source=image_source,
        image_download_plan=image_download_plan,
        item_payload=item_payload,
        inventory_payload=inventory_payload,
        image_candidates=evaluation.image_candidates,
        representative_color_mapping=representative_color_mapping,
        provisional_genre_candidate=evaluation.provisional_genre_candidate,
    )
