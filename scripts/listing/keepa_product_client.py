
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


def _extract_avg90_seller_count(stats: dict[str, Any]) -> Optional[float]:
    avg90 = stats.get("avg90") if isinstance(stats, dict) else None
    if not isinstance(avg90, list) or len(avg90) <= 12:
        return None
    value = avg90[12]
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric < 0:
        return None
    return numeric


def parse_keepa_product(asin: str, product: dict[str, Any]) -> KeepaProductData:
    stats = product.get("stats") or {}
    features = product.get("features") or []
    if isinstance(features, str):
        features = [features]

    return KeepaProductData(
        asin=asin,
        title=_coerce_text(product.get("title")),
        brand=_coerce_text(product.get("brand")),
        model=_coerce_text(product.get("model")),
        ean=_first_ean(product),
        images_csv=_coerce_text(product.get("imagesCSV")),
        category_id=_extract_leaf_category_id(product),
        features=[_coerce_text(item) for item in features if _coerce_text(item)],
        description=_coerce_text(product.get("description")),
        style=_coerce_text(product.get("style")),
        size=_coerce_text(product.get("size")),
        color=_coerce_text(product.get("color")),
        buy_box_price=_normalize_keepa_price(stats.get("buyBoxPrice")),
        buy_box_shipping=_normalize_keepa_price(stats.get("buyBoxShipping")),
        avg90_seller_count=_extract_avg90_seller_count(stats),
        is_adult=bool(product.get("isAdult")),
        raw_summary={
            "category_id": _extract_leaf_category_id(product),
            "ean": _first_ean(product),
            "avg90_seller_count": _extract_avg90_seller_count(stats),
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

    def fetch_product(self, asin: str) -> KeepaProductData:
        params = {
            "key": self.api_key,
            "domain": self.domain,
            "asin": asin,
            "stats": 90,
            "history": 0,
            "offers": 20,
        }

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
            return parse_keepa_product(asin, products[0])
