from __future__ import annotations

from dataclasses import asdict
from typing import Any

from scripts.listing.keepa_product_client import parse_keepa_product
from scripts.listing.models import KeepaProductData


IMAGE_URL_TEMPLATE = "https://m.media-amazon.com/images/I/{image_id}"


def sanitize_request_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if str(key).lower() != "key"}


def summarize_value(value: Any, *, max_items: int = 3, max_chars: int = 120) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": type(value).__name__,
        "is_null": value is None,
    }

    if isinstance(value, dict):
        summary["key_count"] = len(value)
        summary["keys"] = list(value.keys())[:max_items]
        return summary

    if isinstance(value, list):
        summary["length"] = len(value)
        summary["first_items"] = value[:max_items]
        summary["last_items"] = value[-max_items:] if len(value) > max_items else value[:]
        return summary

    if isinstance(value, str):
        normalized = value.replace("\r", "\\r").replace("\n", "\\n")
        summary["sample"] = normalized[:max_chars]
        summary["length"] = len(value)
        return summary

    summary["sample"] = value
    return summary


def _get_path(payload: Any, path: str) -> Any:
    current = payload
    for token in path.split("."):
        if token.endswith("]") and "[" in token:
            name, _, index_part = token.partition("[")
            raw_index = index_part[:-1]
            if name:
                current = current.get(name) if isinstance(current, dict) else None
            if raw_index == "":
                if not isinstance(current, list):
                    return None
                current = [item for item in current]
                continue
            index = int(raw_index)
            if index == -1:
                if not isinstance(current, list) or not current:
                    return None
                current = current[-1]
                continue
            if not isinstance(current, list) or len(current) <= index:
                return None
            current = current[index]
            continue

        if isinstance(current, list):
            collected = []
            for item in current:
                if isinstance(item, dict) and token in item:
                    collected.append(item.get(token))
            current = collected
        elif isinstance(current, dict):
            current = current.get(token)
        else:
            return None
    return current


def _mapping_entry(
    *,
    rakuten_field: str,
    raw_candidates: list[str],
    recommended_source: str | None,
    transform: str,
    current_value: Any,
    diagnosis: str,
    reason: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    resolved_candidates = []
    for path in raw_candidates:
        value = _get_path(raw_payload, path)
        resolved_candidates.append(
            {
                "path": path,
                "summary": summarize_value(value),
            }
        )

    return {
        "rakuten_field": rakuten_field,
        "raw_candidates": resolved_candidates,
        "recommended_source": recommended_source,
        "transform": transform,
        "current_value": current_value,
        "diagnosis": diagnosis,
        "reason": reason,
    }


def build_candidate_image_urls(images_csv: str) -> list[str]:
    image_ids = [item.strip() for item in str(images_csv or "").split(",") if item.strip()]
    return [IMAGE_URL_TEMPLATE.format(image_id=image_id) for image_id in image_ids]


def summarize_hazardous_materials(product: dict[str, Any]) -> dict[str, Any]:
    materials = product.get("hazardousMaterials") or []
    if not isinstance(materials, list):
        materials = [materials]
    sample: list[Any] = []
    for material in materials[:5]:
        if isinstance(material, dict):
            sample.append(material.get("value") or material.get("aspect") or material)
        else:
            sample.append(material)
    return {
        "count": len(materials),
        "sample": sample,
        "isHeatSensitive": product.get("isHeatSensitive"),
        "itemForm": product.get("itemForm"),
        "scent": product.get("scent"),
        "unitCount": product.get("unitCount"),
    }


def _recommend_image_source(product: dict[str, Any]) -> str | None:
    images = product.get("images")
    if isinstance(images, list):
        if any(isinstance(item, dict) and str(item.get("l") or "").strip() for item in images):
            return "products[0].images[].l"
        if any(isinstance(item, dict) and str(item.get("m") or "").strip() for item in images):
            return "products[0].images[].m"
    if str(product.get("imagesCSV") or "").strip():
        return "products[0].imagesCSV"
    return None


def build_keepa_field_report(
    raw_response: dict[str, Any],
    parsed_product: KeepaProductData,
    request_meta: dict[str, Any],
) -> dict[str, Any]:
    product = ((raw_response or {}).get("products") or [{}])[0]
    paths = [
        "products[0].title",
        "products[0].brand",
        "products[0].manufacturer",
        "products[0].model",
        "products[0].partNumber",
        "products[0].color",
        "products[0].size",
        "products[0].style",
        "products[0].binding",
        "products[0].productGroup",
        "products[0].productType",
        "products[0].features",
        "products[0].description",
        "products[0].ean",
        "products[0].eanList",
        "products[0].upc",
        "products[0].upcList",
        "products[0].categoryId",
        "products[0].rootCategory",
        "products[0].categoryTree",
        "products[0].imagesCSV",
        "products[0].images",
        "products[0].stats",
        "products[0].stats.current",
        "products[0].stats.avg30",
        "products[0].stats.avg90",
        "products[0].stats.avg180",
        "products[0].stats.totalOfferCount",
        "products[0].stats.offerCountFBA",
        "products[0].stats.offerCountFBM",
        "products[0].csv",
        "products[0].offers",
        "products[0].offerCount",
        "products[0].stats.buyBoxPrice",
        "products[0].stats.buyBoxShipping",
        "products[0].isAdultProduct",
        "products[0].isAdult",
        "products[0].hazardousMaterials",
        "products[0].isHeatSensitive",
        "products[0].itemForm",
        "products[0].scent",
        "products[0].unitCount",
        "products[0].reviewCount",
        "products[0].reviews",
        "products[0].rating",
        "products[0].variations",
        "products[0].itemDimensions",
        "products[0].packageDimensions",
        "products[0].itemWeight",
        "products[0].packageWeight",
    ]

    parser_paths = {
        "products[0].title",
        "products[0].brand",
        "products[0].manufacturer",
        "products[0].model",
        "products[0].partNumber",
        "products[0].eanList",
        "products[0].categoryTree",
        "products[0].imagesCSV",
        "products[0].images",
        "products[0].features",
        "products[0].description",
        "products[0].style",
        "products[0].size",
        "products[0].color",
        "products[0].stats.buyBoxPrice",
        "products[0].stats.buyBoxShipping",
        "products[0].stats.current",
        "products[0].stats.avg90",
        "products[0].stats.totalOfferCount",
        "products[0].stats.offerCountFBA",
        "products[0].stats.offerCountFBM",
        "products[0].isAdultProduct",
        "products[0].isAdult",
    }

    entries = []
    envelope = {"products": [product]}
    for path in paths:
        value = _get_path(envelope, path)
        entries.append(
            {
                "json_path": path,
                "used_by_current_parser": path in parser_paths,
                "summary": summarize_value(value),
            }
        )

    return {
        "request": request_meta,
        "response_meta": {
            "top_level_keys": list((raw_response or {}).keys()),
            "product_count": len((raw_response or {}).get("products") or []),
        },
        "current_keepa_product_data": asdict(parsed_product),
        "hazardous_materials_summary": summarize_hazardous_materials(product),
        "fields": entries,
    }


def build_keepa_mapping_report(
    asin: str,
    raw_response: dict[str, Any],
    parsed_product: KeepaProductData,
    request_meta: dict[str, Any],
) -> dict[str, Any]:
    product = ((raw_response or {}).get("products") or [{}])[0]
    product_payload = {"products": [product]}
    recommended_image_source = _recommend_image_source(product)
    image_diagnosis = "ok"
    if recommended_image_source in {"products[0].images[].l", "products[0].images[].m"}:
        if parsed_product.image_source == "keepa_images":
            image_diagnosis = "ok"
        elif parsed_product.image_source == "keepa_images_csv":
            image_diagnosis = "parser_wrong_path"
        else:
            image_diagnosis = "parser_dropped_value"
    elif recommended_image_source == "products[0].imagesCSV" and parsed_product.image_source != "keepa_images_csv":
        image_diagnosis = "parser_dropped_value"

    avg90_index_11 = _get_path(product_payload, "products[0].stats.avg90[11]")
    avg90_index_12 = _get_path(product_payload, "products[0].stats.avg90[12]")
    count_diagnosis = "unknown"
    if parsed_product.avg90_new_offer_count == avg90_index_11:
        count_diagnosis = "ok"
    elif parsed_product.avg90_new_offer_count == avg90_index_12:
        count_diagnosis = "parser_wrong_index"

    mappings = [
        _mapping_entry(
            rakuten_field="title",
            raw_candidates=["products[0].title"],
            recommended_source="products[0].title",
            transform="trim",
            current_value=parsed_product.title,
            diagnosis="ok" if parsed_product.title else "unknown",
            reason="Current parser reads Keepa title directly.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="variants.attributes.ブランド名",
            raw_candidates=["products[0].brand", "products[0].manufacturer"],
            recommended_source="products[0].brand",
            transform="trim",
            current_value={"brand": parsed_product.brand, "manufacturer": parsed_product.manufacturer},
            diagnosis="ok" if parsed_product.brand or parsed_product.manufacturer else "unknown",
            reason="Brand is primary and manufacturer is fallback only when brand is blank.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="variants.attributes.メーカー型番",
            raw_candidates=["products[0].model", "products[0].partNumber"],
            recommended_source="products[0].model",
            transform="trim",
            current_value={"model": parsed_product.model, "part_number": parsed_product.part_number},
            diagnosis="ok" if parsed_product.model or parsed_product.part_number else "unknown",
            reason="Model is primary and partNumber is fallback only when model is blank.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="variants.articleNumber",
            raw_candidates=["products[0].ean", "products[0].eanList[0]", "products[0].upc", "products[0].upcList[0]"],
            recommended_source="products[0].eanList[0]",
            transform="trim",
            current_value=parsed_product.ean,
            diagnosis="ok" if parsed_product.ean else "unknown",
            reason="Current parser uses eanList first value and does not read bare ean/upc fields.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="genreId source",
            raw_candidates=["products[0].categoryTree[-1].catId", "products[0].categoryId", "products[0].rootCategory"],
            recommended_source="products[0].categoryTree[-1].catId",
            transform="int",
            current_value=parsed_product.category_id,
            diagnosis="ok" if parsed_product.category_id is not None else "unknown",
            reason="Current parser uses the last categoryTree node catId.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="image_candidates",
            raw_candidates=["products[0].images[].l", "products[0].images[].m", "products[0].imagesCSV"],
            recommended_source=recommended_image_source,
            transform="keepa image filename -> media URL",
            current_value={
                "images_csv": parsed_product.images_csv,
                "image_urls": parsed_product.image_urls,
                "image_source": parsed_product.image_source,
            },
            diagnosis=image_diagnosis,
            reason="Parser should prefer images[].l, then images[].m, and only fall back to imagesCSV when images are unavailable.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="buy_box_price",
            raw_candidates=["products[0].stats.buyBoxPrice", "products[0].offers"],
            recommended_source="products[0].stats.buyBoxPrice",
            transform="normalize keepa price",
            current_value=parsed_product.buy_box_price,
            diagnosis="ok" if parsed_product.buy_box_price is not None else "unknown",
            reason="Current parser reads stats.buyBoxPrice and does not inspect offers.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="new_offer_counts",
            raw_candidates=[
                "products[0].stats.current[11]",
                "products[0].stats.avg90[11]",
                "products[0].stats.avg90[12]",
                "products[0].stats.totalOfferCount",
                "products[0].stats.offerCountFBA",
                "products[0].stats.offerCountFBM",
                "products[0].offers",
            ],
            recommended_source="products[0].stats.avg90[11]",
            transform="Keepa COUNT_NEW",
            current_value={
                "current_new_offer_count": parsed_product.current_new_offer_count,
                "avg90_new_offer_count": parsed_product.avg90_new_offer_count,
                "avg90_seller_count": parsed_product.avg90_seller_count,
                "total_offer_count": parsed_product.total_offer_count,
                "offer_count_fba": parsed_product.offer_count_fba,
                "offer_count_fbm": parsed_product.offer_count_fbm,
            },
            diagnosis=count_diagnosis,
            reason="COUNT_NEW index 11 is used for current and avg90. avg90_seller_count is kept only as a compatibility mirror of avg90_new_offer_count.",
            raw_payload=product_payload,
        ),
        _mapping_entry(
            rakuten_field="is_adult",
            raw_candidates=["products[0].isAdultProduct", "products[0].isAdult"],
            recommended_source=(
                "products[0].isAdultProduct"
                if parsed_product.is_adult_source == "isAdultProduct"
                else "products[0].isAdult"
                if parsed_product.is_adult_source == "isAdult"
                else None
            ),
            transform="bool",
            current_value={"is_adult": parsed_product.is_adult, "source": parsed_product.is_adult_source},
            diagnosis="ok" if parsed_product.is_adult_source != "unknown" else "unknown",
            reason="Parser prefers isAdultProduct and falls back to legacy isAdult only for compatibility.",
            raw_payload=product_payload,
        ),
    ]

    return {
        "asin": asin,
        "request": request_meta,
        "current_keepa_product_data": asdict(parsed_product),
        "hazardous_materials_summary": summarize_hazardous_materials(product),
        "image_analysis": {
            "image_source_path": recommended_image_source,
            "image_source": parsed_product.image_source,
            "image_ids": [url.rsplit("/", 1)[-1] for url in parsed_product.image_urls],
            "candidate_urls": parsed_product.image_urls,
            "main_image_candidate": parsed_product.image_urls[0] if parsed_product.image_urls else None,
        },
        "mappings": mappings,
    }


def analyze_keepa_response(
    *,
    asin: str,
    raw_response: dict[str, Any],
    request_params: dict[str, Any],
) -> tuple[KeepaProductData, dict[str, Any], dict[str, Any]]:
    products = raw_response.get("products") or []
    if not products:
        raise RuntimeError(f"Keepa returned no products for ASIN: {asin}")

    parsed_product = parse_keepa_product(asin, products[0])
    request_meta = {
        "domain": request_params.get("domain"),
        "asin": request_params.get("asin"),
        "requested_options": sanitize_request_params(request_params),
    }
    field_report = build_keepa_field_report(raw_response, parsed_product, request_meta)
    mapping_report = build_keepa_mapping_report(asin, raw_response, parsed_product, request_meta)
    return parsed_product, field_report, mapping_report
