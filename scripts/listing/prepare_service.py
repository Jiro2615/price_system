from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from .listing_evaluator import evaluate_listing
from .management_number import generate_management_number_bundle
from .models import AmazonCheckResult, KeepaProductData, MasterData, StoreSettings
from .rakuten_payload_builder import build_inventory_payload, build_item_payload


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
    from .keepa_product_client import KeepaClient, load_keepa_api_key

    keepa_client = KeepaClient(api_key=load_keepa_api_key())
    return keepa_client.fetch_product(asin)


def load_store_settings(store_code: str) -> StoreSettings:
    from .store_config import get_store_settings

    return get_store_settings(store_code)


def load_master_records(master_dir: Path, allow_missing: bool) -> MasterData:
    from .master_loader import load_master_data

    return load_master_data(master_dir, allow_missing=allow_missing)


def fetch_amazon_result_for_listing(asin: str, page_timeout_ms: int) -> AmazonCheckResult:
    from .amazon_bridge import fetch_amazon_result_sync

    return fetch_amazon_result_sync(asin, page_timeout_ms=page_timeout_ms)


def _load_json_payload(path: Path, label: str) -> dict[str, object]:
    resolved = Path(path)
    if not resolved.exists():
        raise RuntimeError(f"{label} JSON not found: {resolved}")
    return json.loads(resolved.read_text(encoding="utf-8"))


def _load_dataclass_from_json(path: Path, cls: type[T], label: str) -> T:
    payload = _load_json_payload(path, label)
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


def prepare_listing(
    request: PrepareListingRequest,
    *,
    store_settings_loader: Callable[[str], StoreSettings] = load_store_settings,
    master_data_loader: Callable[[Path, bool], MasterData] = load_master_records,
    amazon_fetcher: Callable[[str, int], AmazonCheckResult] = fetch_amazon_result_for_listing,
    keepa_fetcher: Callable[[str], KeepaProductData] = fetch_keepa_result_sync,
) -> dict[str, object]:
    asin = request.asin.strip().upper()
    warnings: list[str] = []
    mode = "offline" if request.offline else "dry_run"

    if request.offline:
        warnings.append("\u30aa\u30d5\u30e9\u30a4\u30f3\u30e2\u30fc\u30c9: \u30ed\u30fc\u30ab\u30eb fixture JSON \u306e\u307f\u3092\u4f7f\u7528\u3057\u307e\u3059")
    elif not request.dry_run:
        warnings.append("\u3053\u306e\u30b3\u30de\u30f3\u30c9\u306f\u975e\u7834\u58ca\u30e2\u30fc\u30c9\u5c02\u7528\u306e\u305f\u3081\u3001dry-run \u3068\u3057\u3066\u7d9a\u884c\u3057\u307e\u3059")

    store_settings = _resolve_store_settings(request, store_settings_loader)
    master_data = master_data_loader(Path(request.master_dir), request.allow_missing_master)
    management_bundle = generate_management_number_bundle(store_settings.management_suffix)
    management_number = request.management_number.strip() or management_bundle.selected

    amazon_result = _resolve_amazon_result(request, asin, amazon_fetcher, warnings)
    keepa_result = _resolve_keepa_result(request, asin, keepa_fetcher, warnings)

    evaluation = evaluate_listing(
        asin=asin,
        amazon_result=amazon_result,
        keepa_result=keepa_result,
        master_data=master_data,
        store_settings=store_settings,
        management_number=management_number,
    )

    item_payload = None
    inventory_payload = None
    if evaluation.listing_status == "eligible" and amazon_result is not None:
        item_payload = build_item_payload(
            management_number=management_number,
            evaluation=evaluation,
            store_settings=store_settings,
            amazon_price=int(amazon_result.amazon_price or 0),
            amazon_point=0,
        )
        inventory_payload = build_inventory_payload(
            management_number=management_number,
            quantity=int(amazon_result.available_qty or 0),
            store_settings=store_settings,
        )

    return {
        "mode": mode,
        "asin": asin,
        "amazon_result": amazon_result,
        "keepa_result": keepa_result,
        "matched_master_rules": evaluation.matched_master_rules,
        "listing_status": evaluation.listing_status,
        "listing_reason": evaluation.listing_reason,
        "management_number": management_number,
        "management_number_candidates": management_bundle,
        "item_payload": item_payload,
        "inventory_payload": inventory_payload,
        "image_candidates": evaluation.image_candidates,
        "warnings": warnings + list(evaluation.warnings),
        "missing_master_files": master_data.missing_files,
        "master_dir": str(Path(request.master_dir).resolve()),
        "store_settings": {
            "store_code": store_settings.store_code,
            "max_stock": store_settings.max_stock,
            "normal_delivery_date_id": store_settings.normal_delivery_date_id,
            "back_order_delivery_date_id": store_settings.back_order_delivery_date_id,
            "normal_delivery_time_id": store_settings.normal_delivery_time_id,
            "back_order_delivery_time_id": store_settings.back_order_delivery_time_id,
            "ship_from_ids": store_settings.ship_from_ids,
            "min_avg90_sellers": store_settings.min_avg90_sellers,
        },
    }
