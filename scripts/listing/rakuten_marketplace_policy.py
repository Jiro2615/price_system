from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
SENSITIVE_MARKERS = (
    "医療", "医薬", "薬", "コンドーム", "性", "育毛", "殺菌", "除菌", "治療", "効能", "効果",
    "治癒", "予防", "疲労回復", "老化防止", "血液サラサラ", "バストアップ", "デトックス",
    "脂肪燃焼", "代謝促進", "病気", "成人病", "便秘", "精力剤", "性的機能",
)
ALCOHOL_WORD = "アルコール"
COSMETICS_CATEGORY_MARKERS = ("ビューティー", "beauty", "化粧品", "cosmetics")


def is_cosmetics_category(category_tree: list[dict[str, Any]] | None) -> bool:
    """Whether Keepa classifies the item in a beauty/cosmetics category."""
    for category in category_tree or []:
        name = str(category.get("name") or "").casefold()
        if any(marker.casefold() in name for marker in COSMETICS_CATEGORY_MARKERS):
            return True
    return False


def has_sensitive_forbidden_word(matches: list[dict[str, Any]], *, cosmetics_category: bool = False) -> bool:
    """Return true for hard-guard matches, with a cosmetics-only alcohol exception.

    ``アルコール`` and ``ノンアルコール`` may use the same-JAN Rakuten
    marketplace confirmation path only for cosmetics.  Medical, efficacy,
    adult, and sterilisation-related words remain hard guards for every genre.
    """
    for item in matches:
        word = str(item.get("word") or "")
        if word == ALCOHOL_WORD:
            if cosmetics_category:
                continue
            return True
        if any(marker in word for marker in SENSITIVE_MARKERS):
            return True
    return False


def rakuten_listing_exists_for_jan(jan_code: str, timeout: float = 15.0) -> bool:
    """Read-only Rakuten Ichiba lookup; true only for an in-stock, postage-included item."""
    jan = str(jan_code or "").strip()
    if not jan:
        return False
    load_dotenv(ENV_PATH)
    application_id = os.getenv("RAKUTEN_WEB_SERVICE_APPLICATION_ID", "").strip()
    access_key = os.getenv("RAKUTEN_WEB_SERVICE_ACCESS_KEY", "").strip()
    if not application_id or not access_key:
        return False
    try:
        response = requests.get(ENDPOINT, params={"applicationId": application_id, "keyword": jan, "postageFlag": 1, "availability": 1, "hits": 1, "format": "json", "formatVersion": 2}, headers={"accessKey": access_key}, timeout=timeout)
        if not response.ok:
            return False
        return bool(response.json().get("items") or response.json().get("Items"))
    except requests.RequestException:
        return False
