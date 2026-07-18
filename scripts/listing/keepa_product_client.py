
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from scripts.listing.models import KeepaProductData


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
KEEPA_API_ENDPOINT = "https://api.keepa.com/product"


def load_keepa_api_key() -> str:
    load_dotenv(ENV_PATH)
    for name in ("KEEPA_API_KEY", "PRICE_SYSTEM_KEEPA_API_KEY"):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    raise RuntimeError("Keepa API key is not set (KEEPA_API_KEY or PRICE_SYSTEM_KEEPA_API_KEY)")


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_coerce_text(item) for item in value if item not in (None, ""))
    return str(value).strip()


def _normalize_keepa_price(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        price = int(value)
    except Exception:
        return None
    if price < 0:
        return None
    if price >= 10000 and price % 100 == 0:
        return price // 100
    return price


def _first_ean(product: dict[str, Any]) -> str:
    ean_list = product.get("eanList") or []
    if isinstance(ean_list, list) and ean_list:
        return str(ean_list[0]).strip()
    return ""


def _extract_leaf_category_id(product: dict[str, Any]) -> Optional[int]:
    category_tree = product.get("categoryTree") or []
    if not isinstance(category_tree, list) or not category_tree:
        return None
    last_node = category_tree[-1]
    if not isinstance(last_node, dict):
        return None
    category_id = last_node.get("catId")
    try:
        return int(category_id)
    except Exception:
        return None


def _extract_category_tree(product: dict[str, Any]) -> list[dict[str, Any]]:
    category_tree = product.get("categoryTree") or []
    if not isinstance(category_tree, list):
        return []
    result: list[dict[str, Any]] = []
    for node in category_tree:
        if not isinstance(node, dict):
            continue
        category_id = node.get("catId")
        try:
            normalized_id = int(category_id) if category_id is not None else None
        except Exception:
            normalized_id = None
        name = _coerce_text(node.get("name"))
        if normalized_id is None and not name:
            continue
        result.append({"catId": normalized_id, "name": name})
    return result


def _extract_avg90_seller_count(stats: dict[str, Any]) -> Optional[float]:
    # Compatibility field only: this mirrors Keepa COUNT_NEW avg90[11],
    # not a strict unique seller count.
    return _extract_avg90_new_offer_count(stats)


def _normalize_count_value(value: Any) -> Optional[int]:
    if value in (None, -1):
        return None
    try:
        numeric = int(value)
    except Exception:
        return None
    if numeric < 0:
        return None
    return numeric


def _normalize_float_count_value(value: Any) -> Optional[float]:
    if value in (None, -1):
        return None
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric < 0:
        return None
    return numeric


def _extract_stat_index(stats: dict[str, Any], field_name: str, index: int) -> Any:
    values = stats.get(field_name) if isinstance(stats, dict) else None
    if not isinstance(values, list) or len(values) <= index:
        return None
    return values[index]


def _extract_current_new_offer_count(stats: dict[str, Any]) -> Optional[int]:
    return _normalize_count_value(_extract_stat_index(stats, "current", 11))


def _extract_avg90_new_offer_count(stats: dict[str, Any]) -> Optional[float]:
    return _normalize_float_count_value(_extract_stat_index(stats, "avg90", 11))


def _extract_total_offer_count(stats: dict[str, Any]) -> Optional[int]:
    return _normalize_count_value(stats.get("totalOfferCount") if isinstance(stats, dict) else None)


def _extract_offer_count_fba(stats: dict[str, Any]) -> Optional[int]:
    return _normalize_count_value(stats.get("offerCountFBA") if isinstance(stats, dict) else None)


def _extract_offer_count_fbm(stats: dict[str, Any]) -> Optional[int]:
    return _normalize_count_value(stats.get("offerCountFBM") if isinstance(stats, dict) else None)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _image_url_from_token(token: Any) -> str:
    value = str(token or "").strip()
    if not value:
        return ""
    return f"https://m.media-amazon.com/images/I/{value}"


def _extract_hazardous_materials(product: dict[str, Any]) -> list[str]:
    materials = product.get("hazardousMaterials") or []
    if not isinstance(materials, list):
        materials = [materials]
    normalized: list[str] = []
    for material in materials:
        if isinstance(material, dict):
            value = _coerce_text(material.get("value") or material.get("aspect"))
        else:
            value = _coerce_text(material)
        if value:
            normalized.append(value)
    return _dedupe_preserve_order(normalized)


def extract_keepa_image_urls(product: dict[str, Any]) -> tuple[list[str], str]:
    images = product.get("images")
    if isinstance(images, list):
        image_urls: list[str] = []
        for image in images:
            if not isinstance(image, dict):
                continue
            preferred = _image_url_from_token(image.get("l"))
            if preferred:
                image_urls.append(preferred)
                continue
            medium = _image_url_from_token(image.get("m"))
            if medium:
                image_urls.append(medium)
        image_urls = _dedupe_preserve_order(image_urls)
        if image_urls:
            return image_urls, "keepa_images"

    images_csv = _coerce_text(product.get("imagesCSV"))
    csv_urls = _dedupe_preserve_order([_image_url_from_token(item) for item in images_csv.split(",")])
    if csv_urls:
        return csv_urls, "keepa_images_csv"
    return [], "none"


def _extract_is_adult(product: dict[str, Any]) -> tuple[Optional[bool], str]:
    if "isAdultProduct" in product:
        value = product.get("isAdultProduct")
        if value is None:
            return None, "isAdultProduct"
        return bool(value), "isAdultProduct"
    if "isAdult" in product:
        value = product.get("isAdult")
        if value is None:
            return None, "isAdult"
        return bool(value), "isAdult"
    return None, "unknown"


def parse_keepa_product(asin: str, product: dict[str, Any]) -> KeepaProductData:
    stats = product.get("stats") or {}
    features = product.get("features") or []
    if isinstance(features, str):
        features = [features]
    raw_images_csv = _coerce_text(product.get("imagesCSV"))
    image_urls, image_source = extract_keepa_image_urls(product)
    category_tree = _extract_category_tree(product)
    current_new_offer_count = _extract_current_new_offer_count(stats)
    avg90_new_offer_count = _extract_avg90_new_offer_count(stats)
    is_adult, is_adult_source = _extract_is_adult(product)
    hazardous_materials = _extract_hazardous_materials(product)
    scent = _coerce_text(product.get("scent"))
    heat_sensitive = product.get("isHeatSensitive")

    return KeepaProductData(
        asin=asin,
        title=_coerce_text(product.get("title")),
        brand=_coerce_text(product.get("brand")),
        manufacturer=_coerce_text(product.get("manufacturer")),
        model=_coerce_text(product.get("model")),
        part_number=_coerce_text(product.get("partNumber")),
        ean=_first_ean(product),
        images_csv=raw_images_csv,
        image_urls=image_urls,
        image_source=image_source,
        category_id=_extract_leaf_category_id(product),
        category_tree=category_tree,
        features=[_coerce_text(item) for item in features if _coerce_text(item)],
        description=_coerce_text(product.get("description")),
        style=_coerce_text(product.get("style")),
        size=_coerce_text(product.get("size")),
        color=_coerce_text(product.get("color")),
        buy_box_price=_normalize_keepa_price(stats.get("buyBoxPrice")),
        buy_box_shipping=_normalize_keepa_price(stats.get("buyBoxShipping")),
        current_new_offer_count=current_new_offer_count,
        avg90_new_offer_count=avg90_new_offer_count,
        avg90_seller_count=_extract_avg90_seller_count(stats),
        total_offer_count=_extract_total_offer_count(stats),
        offer_count_fba=_extract_offer_count_fba(stats),
        offer_count_fbm=_extract_offer_count_fbm(stats),
        hazardous_materials=hazardous_materials,
        is_heat_sensitive=bool(heat_sensitive) if heat_sensitive is not None else None,
        scent=scent,
        is_adult=is_adult,
        is_adult_source=is_adult_source,
        raw_summary={
            "category_id": _extract_leaf_category_id(product),
            "category_tree": category_tree,
            "ean": _first_ean(product),
            "image_source": image_source,
            "image_count": len(image_urls),
            "current_new_offer_count": current_new_offer_count,
            "avg90_new_offer_count": avg90_new_offer_count,
            "avg90_seller_count": _extract_avg90_seller_count(stats),
            "total_offer_count": _extract_total_offer_count(stats),
            "offer_count_fba": _extract_offer_count_fba(stats),
            "offer_count_fbm": _extract_offer_count_fbm(stats),
            "hazardous_materials": hazardous_materials,
            "is_heat_sensitive": bool(heat_sensitive) if heat_sensitive is not None else None,
            "scent": scent,
            "is_adult_source": is_adult_source,
        },
    )


@dataclass
class KeepaClient:
    api_key: str
    domain: int = 5
    max_retries: int = 3
    max_wait_seconds: int = 30
    timeout_seconds: int = 30
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()

    def build_product_request_params(self, asin: str) -> dict[str, Any]:
        return {
            "key": self.api_key,
            "domain": self.domain,
            "asin": asin,
            "stats": 90,
            "history": 0,
            "offers": 20,
        }

    def fetch_product_raw(self, asin: str) -> dict[str, Any]:
        params = self.build_product_request_params(asin)

        attempt = 0
        total_waited = 0.0
        while True:
            response = self.session.get(KEEPA_API_ENDPOINT, params=params, timeout=self.timeout_seconds)
            if response.status_code == 429:
                if attempt >= self.max_retries:
                    raise RuntimeError("Keepa rate limit exceeded and max retries reached")
                wait_seconds = min(self.max_wait_seconds, 5)
                time.sleep(wait_seconds)
                total_waited += wait_seconds
                attempt += 1
                continue

            response.raise_for_status()
            data = response.json()

            refill_in_ms = data.get("refillIn")
            tokens_left = data.get("tokensLeft")
            if tokens_left == 0 and refill_in_ms and attempt < self.max_retries:
                wait_seconds = min(float(refill_in_ms) / 1000.0, float(self.max_wait_seconds))
                if total_waited + wait_seconds > self.max_wait_seconds:
                    raise RuntimeError("Keepa refill wait exceeded max_wait_seconds")
                time.sleep(wait_seconds)
                total_waited += wait_seconds
                attempt += 1
                continue

            products = data.get("products") or []
            if not products:
                raise RuntimeError(f"Keepa returned no products for ASIN: {asin}")
            return data

    def fetch_product(self, asin: str) -> KeepaProductData:
        data = self.fetch_product_raw(asin)
        products = data.get("products") or []
        return parse_keepa_product(asin, products[0])
