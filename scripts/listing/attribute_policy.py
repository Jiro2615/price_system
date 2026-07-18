from __future__ import annotations

import re

from scripts.listing.attribute_resolver import clone_field
from scripts.listing.models import AmazonCheckResult, KeepaProductData, ResolvedField


ATTR_COLOR = "\u30ab\u30e9\u30fc"
ATTR_REP_COLOR = "\u4ee3\u8868\u30ab\u30e9\u30fc"
ATTR_SERIES = "\u30b7\u30ea\u30fc\u30ba\u540d"
ATTR_BRAND = "\u30d6\u30e9\u30f3\u30c9\u540d"
ATTR_MODEL = "\u30e1\u30fc\u30ab\u30fc\u578b\u756a"
ATTR_COUNTRY = "\u539f\u7523\u56fd\uff0f\u88fd\u9020\u56fd"

SERIES_PATTERN = re.compile(r"([A-Za-z0-9]+)[\uff08(]\u9999\u308a[\uff09)](?:\u300d)?\u30b7\u30ea\u30fc\u30ba")
LEGACY_DASH_EVIDENCE = (
    'Legacy fallback precedent only: old real Rakuten item JSON "items_get_20251111221917_187.json" '
    "(manageNumber=20251111221917_187, genreId=210724) used '-' for the same attribute names. "
    "Different genre from 111120 and not a full API guarantee; confirm with dry-run payload and one pilot item."
)

GENERIC_ATTRIBUTE_FIELD_MAP = {
    ATTR_COLOR: "color",
    ATTR_BRAND: "brand",
    ATTR_MODEL: "model_number",
    ATTR_SERIES: "style",
    ATTR_COUNTRY: "country_of_origin_candidate",
    "\u30b5\u30a4\u30ba": "size",
    "\u30b9\u30bf\u30a4\u30eb": "style",
    "EAN\u30b3\u30fc\u30c9": "ean",
    "JAN\u30b3\u30fc\u30c9": "ean",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _none_field(*, evidence: str = "", resolution_action: str = "unresolved") -> ResolvedField:
    return ResolvedField(
        value=None,
        source="none",
        raw_path=None,
        transform="",
        confidence="none",
        evidence=evidence,
        fallback_used=False,
        resolution_action=resolution_action,
    )


def _needs_review(evidence: str) -> ResolvedField:
    return _none_field(evidence=evidence, resolution_action="needs_review")


def _legacy_dash_field(attr_name: str) -> ResolvedField:
    return ResolvedField(
        value="-",
        source="legacy_fallback",
        raw_path=None,
        transform="legacy_dash",
        confidence="low",
        evidence=f"{LEGACY_DASH_EVIDENCE} attribute={attr_name}",
        fallback_used=True,
        resolution_action="use_legacy_dash",
    )


def _clone_if_present(field: ResolvedField | None) -> ResolvedField:
    if field is None:
        return _none_field()
    return clone_field(field)


def _resolve_series_name(
    keepa_result: KeepaProductData | None,
) -> ResolvedField:
    for feature in (keepa_result.features if keepa_result else []):
        text = _text(feature)
        if not text:
            continue
        match = SERIES_PATTERN.search(text)
        if match:
            value = match.group(1)
            return ResolvedField(
                value=value,
                source="inferred",
                raw_path="products[0].features",
                transform="explicit_series_phrase_extract",
                confidence="medium",
                evidence=f"Detected explicit series phrase in feature: {text}",
                fallback_used=False,
                resolution_action="use_inferred",
            )
    return _needs_review("No explicit '<name>(香り)シリーズ' phrase found in Keepa features")


def _resolve_country(
    resolved_fields: dict[str, ResolvedField],
) -> ResolvedField:
    candidate = resolved_fields.get("country_of_origin_candidate")
    if candidate and _text(candidate.value) == "\u65e5\u672c\u88fd":
        return clone_field(candidate, resolution_action="use_inferred")
    return _needs_review('Exact text "日本製" was not found in title/description candidates')


def _resolve_brand(
    resolved_fields: dict[str, ResolvedField],
) -> ResolvedField:
    brand = resolved_fields.get("brand")
    if brand and _text(brand.value):
        return clone_field(brand)
    return _needs_review("Brand and manufacturer fallback were both empty")


def _resolve_color(
    resolved_fields: dict[str, ResolvedField],
) -> ResolvedField:
    color = resolved_fields.get("color")
    if color and _text(color.value):
        return clone_field(color)
    return _legacy_dash_field(ATTR_COLOR)


def _resolve_representative_color(
    resolved_fields: dict[str, ResolvedField],
) -> ResolvedField:
    del resolved_fields
    return _legacy_dash_field(ATTR_REP_COLOR)


def _resolve_model(
    resolved_fields: dict[str, ResolvedField],
) -> ResolvedField:
    model = resolved_fields.get("model_number")
    if model and _text(model.value):
        return clone_field(model)
    return _legacy_dash_field(ATTR_MODEL)


def _resolve_generic_attribute(
    attr_name: str,
    resolved_fields: dict[str, ResolvedField],
    asin: str,
) -> ResolvedField:
    if attr_name in {"ASIN", "\u5546\u54c1\u7ba1\u7406\u756a\u53f7"}:
        return ResolvedField(
            value=asin,
            source="derived",
            raw_path=None,
            transform="identity",
            confidence="high",
            evidence=f"Derived from requested ASIN for {attr_name}",
            fallback_used=False,
            resolution_action="use_actual",
        )

    field_name = GENERIC_ATTRIBUTE_FIELD_MAP.get(attr_name)
    if field_name is None:
        return _needs_review(f"No attribute policy mapping for {attr_name}")

    field = resolved_fields.get(field_name)
    if field and _text(field.value):
        return clone_field(field)
    return _needs_review(f"Resolved field '{field_name}' was empty for {attr_name}")


def resolve_required_attributes(
    *,
    genre_id: int | None,
    attr_names: list[str],
    resolved_fields: dict[str, ResolvedField],
    keepa_result: KeepaProductData | None,
    amazon_result: AmazonCheckResult | None,
    asin: str,
) -> dict[str, ResolvedField]:
    del amazon_result

    results: dict[str, ResolvedField] = {}
    if genre_id == 111120:
        special = {
            ATTR_BRAND: _resolve_brand(resolved_fields),
            ATTR_SERIES: _resolve_series_name(keepa_result),
            ATTR_COUNTRY: _resolve_country(resolved_fields),
            ATTR_COLOR: _resolve_color(resolved_fields),
            ATTR_MODEL: _resolve_model(resolved_fields),
        }
        for attr_name in attr_names:
            results[attr_name] = _clone_if_present(special.get(attr_name)) if attr_name in special else _resolve_generic_attribute(
                attr_name,
                resolved_fields,
                asin,
            )
        return results

    if genre_id == 213661:
        special = {
            ATTR_REP_COLOR: _resolve_representative_color(resolved_fields),
        }
        for attr_name in attr_names:
            results[attr_name] = _clone_if_present(special.get(attr_name)) if attr_name in special else _resolve_generic_attribute(
                attr_name,
                resolved_fields,
                asin,
            )
        return results

    for attr_name in attr_names:
        if attr_name == ATTR_REP_COLOR:
            results[attr_name] = _resolve_representative_color(resolved_fields)
        else:
            results[attr_name] = _resolve_generic_attribute(attr_name, resolved_fields, asin)
    return results
