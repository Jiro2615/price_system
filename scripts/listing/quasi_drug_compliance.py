from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"


def _normalized(value: object) -> str:
    normalized = re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", str(value or "")).casefold())
    # Manufacturer labels vary between Amazon/Keepa and Rakuten captions
    # (e.g. "(株)井田ラボラトリーズ" vs "株式会社井田ラボラトリーズ").
    return re.sub(r"(?:株式会社|\(?株\)?|\(株\))", "", normalized)


def _configured(store_code: str) -> dict[str, str] | None:
    load_dotenv(ENV_PATH)
    prefix = str(store_code or "").strip().upper()
    if not prefix:
        return None
    values = {
        "advertiser_name": os.getenv(f"{prefix}_COMPLIANCE_ADVERTISER_NAME", "").strip(),
        "advertiser_phone": os.getenv(f"{prefix}_COMPLIANCE_ADVERTISER_PHONE", "").strip(),
    }
    return values if all(values.values()) else None


def _caption_label_value(caption: str, label: str) -> str:
    """Read a fact value from an Ichiba caption label without copying its copy."""
    match = re.search(rf"【\s*{re.escape(label)}\s*】\s*([^【\r\n]+)", str(caption or ""))
    return str(match.group(1) if match else "").strip()


def _rakuten24_first(items: list[object]) -> list[object]:
    """Prefer Rakuten24's caption when the exact-JAN search has one."""
    return sorted(
        items,
        key=lambda item: 0
        if isinstance(item, dict) and "楽天24" in str(item.get("shopName") or "")
        else 1,
    )


def _caption_confirms_category_and_manufacturer(caption: str, manufacturer: str, category: str) -> bool:
    normalized_caption = _normalized(caption)
    normalized_manufacturer = _normalized(manufacturer)
    return bool(
        normalized_manufacturer
        and normalized_manufacturer in normalized_caption
        and category in normalized_caption
    )


def _caption_confirms_japanese_category(caption: str, manufacturer: str, category: str) -> bool:
    if not _caption_confirms_category_and_manufacturer(caption, manufacturer, category):
        return False
    # Ichiba captions commonly use label brackets, for example
    # ``【原産国】日本``.  The old literal ``原産国日本`` check missed that
    # otherwise valid same-JAN evidence.
    compact_caption = re.sub(r"[\s\u3000\[\]【】()（）:：]+", "", _normalized(caption))
    return (
        "日本製" in compact_caption
        or "区分日本" in compact_caption
        or "原産国日本" in compact_caption
        or "製造国日本" in compact_caption
    )


def _product_spec_attributes(item_url: str, timeout: float) -> dict[str, str]:
    """Read only the structured product-spec table from an Ichiba item page."""
    url = str(item_url or "").strip()
    if not url:
        return {}
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return {}

    # Rakuten product pages may declare EUC-JP even when requests assumes UTF-8.
    try:
        html = response.content.decode("euc_jp")
    except UnicodeDecodeError:
        html = response.content.decode(response.encoding or "utf-8", errors="replace")
    match = re.search(r'"attributes"\s*:\s*(\[.*?\])\s*,\s*"shopStatus"', html, re.DOTALL)
    if not match:
        return {}
    try:
        raw_attributes = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw_attributes, list):
        return {}
    return {
        str(item.get("title") or "").strip(): str(item.get("value") or "").strip()
        for item in raw_attributes
        if isinstance(item, dict) and str(item.get("title") or "").strip() and str(item.get("value") or "").strip()
    }


def lookup_japanese_regulated_product_evidence(
    *,
    jan_code: str,
    manufacturer: str,
    store_code: str,
    category: str,
    timeout: float = 15.0,
    fetch_product_spec: bool = False,
) -> dict[str, str] | None:
    """Return minimal compliance evidence from Rakuten's same-JAN search.

    Search-result descriptions are evidence only.  They are never copied into
    the new listing because another shop's wording is not an approval source.
    """
    config = _configured(store_code)
    jan = str(jan_code or "").strip()
    if not config or not jan or not str(manufacturer or "").strip():
        return None

    application_id = os.getenv("RAKUTEN_WEB_SERVICE_APPLICATION_ID", "").strip()
    access_key = os.getenv("RAKUTEN_WEB_SERVICE_ACCESS_KEY", "").strip()
    if not application_id or not access_key:
        return None
    for attempt in range(3):
        try:
            response = requests.get(
                ENDPOINT,
                params={
                    "applicationId": application_id,
                    "keyword": jan,
                    "availability": 1,
                    "hits": 30,
                    "format": "json",
                    "formatVersion": 2,
                },
                headers={"accessKey": access_key},
                timeout=timeout,
            )
        except requests.RequestException:
            return None
        if response.status_code != 429:
            try:
                response.raise_for_status()
            except requests.RequestException:
                return None
            break
        retry_after = response.headers.get("Retry-After", "")
        try:
            delay = max(float(retry_after), 1.0)
        except ValueError:
            delay = float(2 ** (attempt + 1))
        time.sleep(delay)
    else:
        return None

    spec_page_attempts = 0
    items = response.json().get("items") or response.json().get("Items") or []
    for item in _rakuten24_first(items):
        if not isinstance(item, dict):
            continue
        caption = str(item.get("itemCaption") or "")
        if category not in {"医薬部外品", "化粧品"} or not _caption_confirms_category_and_manufacturer(caption, manufacturer, category):
            continue
        # Search API exposes only attribute IDs.  The actual values live in
        # the product-spec JSON on the same item page, so prefer those facts
        # when a detailed attribute update is requested.  Caption-only mode
        # is intentionally supported for fast compliance coverage checks.
        spec_attributes: dict[str, str] = {}
        if fetch_product_spec and spec_page_attempts < 3:
            spec_page_attempts += 1
            spec_attributes = _product_spec_attributes(str(item.get("itemUrl") or ""), timeout)
        country = str(spec_attributes.get("原産国／製造国") or "").strip()
        if country != "日本" and not _caption_confirms_japanese_category(caption, manufacturer, category):
            continue
        caption_brand = _caption_label_value(caption, "ブランド")
        return {
            **config,
            "manufacturer": str(manufacturer).strip(),
            # Rakuten24's caption labels product line as "ブランド", while
            # its structured spec uses the company as "ブランド名".  Keep the
            # two destinations distinct in our own product specification.
            "brand": str(spec_attributes.get("ブランド名") or manufacturer).strip(),
            "series_name": str(spec_attributes.get("シリーズ名") or caption_brand).strip(),
            "color": str(spec_attributes.get("カラー") or "").strip(),
            "model_number": str(spec_attributes.get("メーカー型番") or "").strip(),
            "country_of_origin": "日本",
            "product_category": category,
            "evidence_source": "rakuten_same_jan_product_spec" if country == "日本" else "rakuten_same_jan_search",
            "evidence_item_url": str(item.get("itemUrl") or ""),
            "evidence_shop_name": str(item.get("shopName") or ""),
        }
    return None


def lookup_japanese_quasi_drug_evidence(**kwargs: object) -> dict[str, str] | None:
    return lookup_japanese_regulated_product_evidence(category="医薬部外品", **kwargs)
