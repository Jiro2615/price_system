from __future__ import annotations

import math
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

from scripts.listing.models import ListingCommonSettings


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR.parent / ".env"

DEFAULT_MIN_AVG90_NEW_OFFER_COUNT = 3.5
ENV_MIN_AVG90_NEW_OFFER_COUNT = "RAKUTEN_LISTING_MIN_AVG90_NEW_OFFER_COUNT"
# Legacy compatibility only. New code should use avg90_new_offer_count / min_avg90_new_offer_count.
LEGACY_ENV_MIN_AVG90_SELLERS = "RAKUTEN_LISTING_MIN_AVG90_SELLERS"
NEW_SETTING_NAME = "min_avg90_new_offer_count"
LEGACY_SETTING_NAME = "min_avg90_sellers"


def _read_candidate(source: object, name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _coerce_non_negative_float(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not accepted")
    if value is None:
        raise ValueError("value is missing")
    if isinstance(value, Decimal):
        number = float(value)
    elif isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("empty string is not accepted")
        number = float(stripped)
    else:
        raise ValueError(f"unsupported type: {type(value).__name__}")
    if not math.isfinite(number):
        raise ValueError("non-finite number is not accepted")
    if number < 0:
        raise ValueError("negative number is not accepted")
    return number


def resolve_min_avg90_new_offer_count(
    *compatibility_sources: object,
) -> tuple[float, list[str]]:
    load_dotenv(ENV_PATH)
    warnings: list[str] = []

    raw_env_new = os.getenv(ENV_MIN_AVG90_NEW_OFFER_COUNT)
    if raw_env_new is not None:
        try:
            return _coerce_non_negative_float(raw_env_new), warnings
        except ValueError:
            warnings.append(
                f"{ENV_MIN_AVG90_NEW_OFFER_COUNT} is invalid; fallback to default {DEFAULT_MIN_AVG90_NEW_OFFER_COUNT}"
            )
            return DEFAULT_MIN_AVG90_NEW_OFFER_COUNT, warnings

    raw_env_legacy = os.getenv(LEGACY_ENV_MIN_AVG90_SELLERS)
    if raw_env_legacy is not None:
        try:
            return _coerce_non_negative_float(raw_env_legacy), warnings
        except ValueError:
            warnings.append(
                f"{LEGACY_ENV_MIN_AVG90_SELLERS} is invalid; fallback to default {DEFAULT_MIN_AVG90_NEW_OFFER_COUNT}"
            )
            return DEFAULT_MIN_AVG90_NEW_OFFER_COUNT, warnings

    candidates: list[tuple[str, Any]] = []
    for source in compatibility_sources:
        candidates.append((NEW_SETTING_NAME, _read_candidate(source, NEW_SETTING_NAME)))
        candidates.append((LEGACY_SETTING_NAME, _read_candidate(source, LEGACY_SETTING_NAME)))

    for name, raw_value in candidates:
        if raw_value is None:
            continue
        try:
            return _coerce_non_negative_float(raw_value), warnings
        except ValueError:
            warnings.append(f"{name} is invalid; fallback to default {DEFAULT_MIN_AVG90_NEW_OFFER_COUNT}")
            return DEFAULT_MIN_AVG90_NEW_OFFER_COUNT, warnings

    return DEFAULT_MIN_AVG90_NEW_OFFER_COUNT, warnings


def load_listing_common_settings(
    *compatibility_sources: object,
) -> tuple[ListingCommonSettings, list[str]]:
    value, warnings = resolve_min_avg90_new_offer_count(*compatibility_sources)
    return ListingCommonSettings(min_avg90_new_offer_count=value), warnings


def build_seller_count_evaluation(
    *,
    actual_value: float | None,
    minimum_value: float,
) -> dict[str, object]:
    passed = actual_value is None or actual_value >= minimum_value
    if actual_value is None:
        reason = "過去90日の新品出品者数平均が未取得のため、この条件では判定しません"
    elif passed:
        reason = "過去90日の新品出品者数平均が基準以上です"
    else:
        reason = "過去90日の新品出品者数平均が基準未満"
    return {
        "metric": "avg90_new_offer_count",
        "keepa_csv_type": "COUNT_NEW",
        "raw_path": "products[0].stats.avg90[11]",
        "actual_value": actual_value,
        "minimum_value": minimum_value,
        "passed": passed,
        "reason": reason,
    }
