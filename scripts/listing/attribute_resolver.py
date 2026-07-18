from __future__ import annotations

from dataclasses import replace

from scripts.listing.models import AmazonCheckResult, KeepaProductData, MasterData, ResolvedField


def _none_field(*, value: object = None, evidence: str = "", resolution_action: str = "unresolved") -> ResolvedField:
    return ResolvedField(
        value=value,
        source="none",
        raw_path=None,
        transform="",
        confidence="none",
        evidence=evidence,
        fallback_used=False,
        resolution_action=resolution_action,
    )


def _field(
    *,
    value: object,
    source: str,
    raw_path: str | None,
    transform: str,
    confidence: str,
    evidence: str,
    fallback_used: bool = False,
    resolution_action: str | None = None,
) -> ResolvedField:
    if resolution_action is None:
        if source == "inferred":
            resolution_action = "use_inferred"
        elif source == "none":
            resolution_action = "unresolved"
        else:
            resolution_action = "use_actual"
    return ResolvedField(
        value=value,
        source=source,
        raw_path=raw_path,
        transform=transform,
        confidence=confidence,
        evidence=evidence,
        fallback_used=fallback_used,
        resolution_action=resolution_action,
    )


def clone_field(field: ResolvedField, **changes: object) -> ResolvedField:
    return replace(field, **changes)


def _has_text(value: object) -> bool:
    return bool(str(value or "").strip())


def _resolve_title(amazon_result: AmazonCheckResult | None, keepa_result: KeepaProductData | None) -> ResolvedField:
    if amazon_result and _has_text(amazon_result.title):
        return _field(
            value=amazon_result.title.strip(),
            source="amazon",
            raw_path="amazon_result.title",
            transform="trim",
            confidence="high",
            evidence="Amazon title",
        )
    if keepa_result and _has_text(keepa_result.title):
        return _field(
            value=keepa_result.title.strip(),
            source="keepa",
            raw_path="products[0].title",
            transform="trim",
            confidence="high",
            evidence="Keepa title",
            fallback_used=True,
        )
    return _none_field()


def _resolve_brand(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and _has_text(keepa_result.brand):
        return _field(
            value=keepa_result.brand.strip(),
            source="keepa",
            raw_path="products[0].brand",
            transform="trim",
            confidence="high",
            evidence="Keepa brand",
        )
    if keepa_result and _has_text(keepa_result.manufacturer):
        return _field(
            value=keepa_result.manufacturer.strip(),
            source="keepa",
            raw_path="products[0].manufacturer",
            transform="trim",
            confidence="high",
            evidence="Keepa manufacturer fallback",
            fallback_used=True,
        )
    return _none_field()


def _resolve_manufacturer(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and _has_text(keepa_result.manufacturer):
        return _field(
            value=keepa_result.manufacturer.strip(),
            source="keepa",
            raw_path="products[0].manufacturer",
            transform="trim",
            confidence="high",
            evidence="Keepa manufacturer",
        )
    return _none_field()


def _resolve_model_number(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and _has_text(keepa_result.model):
        return _field(
            value=keepa_result.model.strip(),
            source="keepa",
            raw_path="products[0].model",
            transform="trim",
            confidence="high",
            evidence="Keepa model",
        )
    if keepa_result and _has_text(keepa_result.part_number):
        return _field(
            value=keepa_result.part_number.strip(),
            source="keepa",
            raw_path="products[0].partNumber",
            transform="trim",
            confidence="high",
            evidence="Keepa partNumber fallback",
            fallback_used=True,
        )
    return _none_field()


def _resolve_ean(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and _has_text(keepa_result.ean):
        return _field(
            value=keepa_result.ean.strip(),
            source="keepa",
            raw_path="products[0].eanList[0]",
            transform="trim",
            confidence="high",
            evidence="Keepa ean/eanList",
        )
    return _none_field()


def _resolve_category_id(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and keepa_result.category_id is not None:
        return _field(
            value=int(keepa_result.category_id),
            source="keepa",
            raw_path="products[0].categoryTree[-1].catId",
            transform="int",
            confidence="high",
            evidence="Keepa leaf category id",
        )
    return _none_field()


def _resolve_genre_id(keepa_result: KeepaProductData | None, master_data: MasterData | None) -> ResolvedField:
    if keepa_result is None or keepa_result.category_id is None or master_data is None:
        return _none_field()
    genre_id = master_data.category_map.get(int(keepa_result.category_id))
    if genre_id is None:
        return _none_field(evidence="No Rakuten genre mapping for Keepa category id")
    return _field(
        value=int(genre_id),
        source="master",
        raw_path=f"master.category_map[{int(keepa_result.category_id)}]",
        transform="category_id -> genre_id",
        confidence="high",
        evidence="catlist_rakuten mapping",
    )


def _resolve_description_candidate(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and _has_text(keepa_result.description):
        return _field(
            value=keepa_result.description.strip(),
            source="keepa",
            raw_path="products[0].description",
            transform="trim",
            confidence="high",
            evidence="Keepa description",
        )
    if keepa_result and keepa_result.features:
        joined = "\n".join(item.strip() for item in keepa_result.features if _has_text(item))
        if joined:
            return _field(
                value=joined,
                source="keepa",
                raw_path="products[0].features",
                transform="join_newlines",
                confidence="medium",
                evidence="Keepa features fallback",
                fallback_used=True,
            )
    return _none_field()


def _resolve_simple_keepa_text(
    keepa_result: KeepaProductData | None,
    *,
    value: str,
    raw_path: str,
    evidence: str,
) -> ResolvedField:
    if _has_text(value):
        return _field(
            value=value.strip(),
            source="keepa",
            raw_path=raw_path,
            transform="trim",
            confidence="high",
            evidence=evidence,
        )
    return _none_field()


def _resolve_main_image(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and keepa_result.image_urls:
        raw_path = (
            "products[0].images[].l|products[0].images[].m"
            if keepa_result.image_source == "keepa_images"
            else "products[0].imagesCSV"
        )
        return _field(
            value=keepa_result.image_urls[0],
            source="keepa",
            raw_path=raw_path,
            transform="select_first_image_url",
            confidence="high",
            evidence=f"Keepa image source: {keepa_result.image_source}",
            fallback_used=keepa_result.image_source == "keepa_images_csv",
        )
    return _none_field()


def _resolve_image_urls(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and keepa_result.image_urls:
        raw_path = (
            "products[0].images[].l|products[0].images[].m"
            if keepa_result.image_source == "keepa_images"
            else "products[0].imagesCSV"
        )
        return _field(
            value=list(keepa_result.image_urls),
            source="keepa",
            raw_path=raw_path,
            transform="dedupe_preserve_order",
            confidence="high",
            evidence=f"Keepa image source: {keepa_result.image_source}",
            fallback_used=keepa_result.image_source == "keepa_images_csv",
        )
    return _none_field()


def _resolve_image_source(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and keepa_result.image_source != "none":
        raw_path = (
            "products[0].images[].l|products[0].images[].m"
            if keepa_result.image_source == "keepa_images"
            else "products[0].imagesCSV"
        )
        return _field(
            value=keepa_result.image_source,
            source="keepa",
            raw_path=raw_path,
            transform="enum",
            confidence="high",
            evidence="Keepa image source classification",
            fallback_used=keepa_result.image_source == "keepa_images_csv",
        )
    return _none_field()


def _resolve_optional_numeric(
    value: int | float | None,
    *,
    raw_path: str,
    evidence: str,
) -> ResolvedField:
    if value is None:
        return _none_field()
    return _field(
        value=value,
        source="keepa",
        raw_path=raw_path,
        transform="numeric",
        confidence="high",
        evidence=evidence,
    )


def _resolve_is_adult(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result is None:
        return _none_field(value="unknown", evidence="Keepa result unavailable")
    source_map = {
        "isAdultProduct": "products[0].isAdultProduct",
        "isAdult": "products[0].isAdult",
    }
    if keepa_result.is_adult_source in source_map and keepa_result.is_adult is not None:
        return _field(
            value=bool(keepa_result.is_adult),
            source="keepa",
            raw_path=source_map[keepa_result.is_adult_source],
            transform="bool",
            confidence="high",
            evidence=f"Keepa {keepa_result.is_adult_source}",
        )
    return _none_field(value="unknown", evidence="Keepa is_adult unavailable")


def _resolve_hazardous_materials(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and keepa_result.hazardous_materials:
        return _field(
            value=list(keepa_result.hazardous_materials),
            source="keepa",
            raw_path="products[0].hazardousMaterials",
            transform="normalize_value_list",
            confidence="high",
            evidence="Keepa hazardous materials",
        )
    return _none_field()


def _resolve_heat_sensitive(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and keepa_result.is_heat_sensitive is not None:
        return _field(
            value=bool(keepa_result.is_heat_sensitive),
            source="keepa",
            raw_path="products[0].isHeatSensitive",
            transform="bool",
            confidence="high",
            evidence="Keepa heat sensitivity",
        )
    return _none_field()


def _resolve_scent(keepa_result: KeepaProductData | None) -> ResolvedField:
    if keepa_result and _has_text(keepa_result.scent):
        return _field(
            value=keepa_result.scent.strip(),
            source="keepa",
            raw_path="products[0].scent",
            transform="trim",
            confidence="high",
            evidence="Keepa scent",
        )
    return _none_field()


def _resolve_country_of_origin_candidate(
    amazon_result: AmazonCheckResult | None,
    keepa_result: KeepaProductData | None,
) -> ResolvedField:
    candidates = [
        ("amazon_result.title", amazon_result.title if amazon_result else ""),
        ("products[0].title", keepa_result.title if keepa_result else ""),
        ("products[0].description", keepa_result.description if keepa_result else ""),
    ]
    for raw_path, text in candidates:
        normalized = str(text or "").strip()
        if "日本製" in normalized:
            return _field(
                value="日本製",
                source="inferred",
                raw_path=raw_path,
                transform="keyword_extract",
                confidence="medium",
                evidence='Found explicit text "日本製"',
            )
    return _none_field()


def build_resolved_fields(
    *,
    amazon_result: AmazonCheckResult | None,
    keepa_result: KeepaProductData | None,
    master_data: MasterData | None,
) -> dict[str, ResolvedField]:
    return {
        "title": _resolve_title(amazon_result, keepa_result),
        "brand": _resolve_brand(keepa_result),
        "manufacturer": _resolve_manufacturer(keepa_result),
        "model_number": _resolve_model_number(keepa_result),
        "ean": _resolve_ean(keepa_result),
        "category_id": _resolve_category_id(keepa_result),
        "genre_id": _resolve_genre_id(keepa_result, master_data),
        "description_candidate": _resolve_description_candidate(keepa_result),
        "size": _resolve_simple_keepa_text(
            keepa_result,
            value=keepa_result.size if keepa_result else "",
            raw_path="products[0].size",
            evidence="Keepa size",
        ),
        "color": _resolve_simple_keepa_text(
            keepa_result,
            value=keepa_result.color if keepa_result else "",
            raw_path="products[0].color",
            evidence="Keepa color",
        ),
        "style": _resolve_simple_keepa_text(
            keepa_result,
            value=keepa_result.style if keepa_result else "",
            raw_path="products[0].style",
            evidence="Keepa style",
        ),
        "main_image": _resolve_main_image(keepa_result),
        "image_urls": _resolve_image_urls(keepa_result),
        "image_source": _resolve_image_source(keepa_result),
        "current_new_offer_count": _resolve_optional_numeric(
            keepa_result.current_new_offer_count if keepa_result else None,
            raw_path="products[0].stats.current[11]",
            evidence="Keepa current new offer count",
        ),
        "avg90_new_offer_count": _resolve_optional_numeric(
            keepa_result.avg90_new_offer_count if keepa_result else None,
            raw_path="products[0].stats.avg90[11]",
            evidence="Keepa avg90 new offer count",
        ),
        "is_adult": _resolve_is_adult(keepa_result),
        "hazardous_materials": _resolve_hazardous_materials(keepa_result),
        "is_heat_sensitive": _resolve_heat_sensitive(keepa_result),
        "scent": _resolve_scent(keepa_result),
        "country_of_origin_candidate": _resolve_country_of_origin_candidate(amazon_result, keepa_result),
    }
