from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

from scripts.listing.models import AmazonCheckResult


BASE_DIR = Path(__file__).resolve().parents[2]
LOCAL_MODULE_PATH = BASE_DIR / "scripts" / "price_check_one_asin_db.py"


_amazon_module = None


def _load_amazon_module():
    global _amazon_module
    if _amazon_module is not None:
        return _amazon_module

    if not LOCAL_MODULE_PATH.exists():
        raise RuntimeError(f"Amazon checker not found in current worktree: {LOCAL_MODULE_PATH}")

    module = importlib.import_module("scripts.price_check_one_asin_db")
    _amazon_module = module
    return module


async def fetch_amazon_result(
    asin: str,
    *,
    page_timeout_ms: int = 15000,
    debug_html: bool = False,
) -> AmazonCheckResult:
    module = _load_amazon_module()
    captured: dict[str, object] = {}
    original_logger = module.log_result_summary

    def capture_logger(requested_asin: str, page_asin: str, current_url: str, result: dict[str, object]) -> None:
        captured["requested_asin"] = requested_asin
        captured["page_asin"] = page_asin
        captured["current_url"] = current_url
        return original_logger(requested_asin, page_asin, current_url, result)

    module.log_result_summary = capture_logger
    try:
        result = await module.check_amazon_one(
            asin.strip().upper(),
            page_timeout_ms=page_timeout_ms,
            debug_html=debug_html,
        )
    finally:
        module.log_result_summary = original_logger

    return AmazonCheckResult(
        requested_asin=str(captured.get("requested_asin", asin.strip().upper())),
        page_asin=str(captured.get("page_asin", "")),
        title=str(result.get("title", "") or ""),
        amazon_price=result.get("amazon_price"),
        available_qty=result.get("available_qty"),
        gift_available=result.get("gift_available"),
        shipping_status=str(result.get("shipping_status", "") or ""),
        business_ng=bool(result.get("business_ng")),
        system_error=bool(result.get("system_error")),
        ng_reason=str(result.get("ng_reason", "") or ""),
        current_url=str(captured.get("current_url", "") or ""),
    )


def fetch_amazon_result_sync(
    asin: str,
    *,
    page_timeout_ms: int = 15000,
    debug_html: bool = False,
) -> AmazonCheckResult:
    return asyncio.run(fetch_amazon_result(asin, page_timeout_ms=page_timeout_ms, debug_html=debug_html))
