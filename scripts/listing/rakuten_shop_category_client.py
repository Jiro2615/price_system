"""Rakuten Category API 2.0 client for shop display-category mappings.

``genreId`` in the Item API is a Rakuten marketplace genre.  It is not the
same as the shop's own category pages.  This module only manages the latter,
using Category API 2.0's item-mappings endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

from scripts.listing.models import sanitize_for_output
from scripts.listing.rakuten_transport import build_rakuten_auth_headers, create_requests_session, summarize_response


CATEGORY_API_BASE = "https://api.rms.rakuten.co.jp/es/2.0/categories"
DEFAULT_COSMETICS_SHOP_CATEGORY_ID = "2"
UNASSIGNED_CATEGORY_ID = "1"


@dataclass
class RakutenShopCategoryResult:
    success: bool
    management_number: str
    http_status: int | None
    response_body_summary: dict[str, Any]
    retryable: bool
    request_summary: dict[str, Any]
    error_type: str | None = None
    error_message: str | None = None


def _mapping_url(management_number: str) -> str:
    return f"{CATEGORY_API_BASE}/item-mappings/manage-numbers/{quote(management_number, safe='')}"


def _category_url(category_id: str) -> str:
    return f"{CATEGORY_API_BASE}/shop-categories/category-ids/{quote(category_id, safe='')}"


def normalize_category_ids(values: Any) -> list[str]:
    """Normalize unique numeric Category API IDs without changing their order."""
    result: list[str] = []
    for value in list(values or []):
        category_id = str(value or "").strip()
        if category_id and category_id.isdecimal() and category_id not in result:
            result.append(category_id)
    return result


def merged_category_ids(existing: Any, target_category_id: str) -> list[str]:
    """Add the target category, treating RMS's synthetic unassigned ``1`` as empty."""
    target = str(target_category_id or "").strip()
    if not target or not target.isdecimal():
        raise ValueError("target_category_id must be a numeric category ID")
    category_ids = normalize_category_ids(existing)
    if category_ids == [UNASSIGNED_CATEGORY_ID]:
        category_ids = []
    if target not in category_ids:
        category_ids.append(target)
    if not 1 <= len(category_ids) <= 5:
        raise ValueError(f"Category API accepts 1 to 5 categories, got {len(category_ids)}")
    return category_ids


def build_mapping_payload(
    existing_mapping: dict[str, Any] | None,
    *,
    target_category_id: str = DEFAULT_COSMETICS_SHOP_CATEGORY_ID,
    target_is_plural: bool = False,
) -> dict[str, Any]:
    """Build an upsert body while retaining current shop-category assignments."""
    current = dict(existing_mapping or {})
    category_ids = merged_category_ids(current.get("categoryIds"), target_category_id)
    payload: dict[str, Any] = {"categoryIds": category_ids}
    current_main = str(current.get("mainPluralCategoryId") or "").strip()
    target = str(target_category_id).strip()
    if target_is_plural:
        payload["mainPluralCategoryId"] = target
    elif current_main and current_main in category_ids:
        payload["mainPluralCategoryId"] = current_main
    return payload


class RakutenShopCategoryClient:
    def __init__(self, *, session_factory: Callable[[], Any] | None = None) -> None:
        self._session_factory = session_factory or create_requests_session

    @staticmethod
    def _headers(store_code: str, *, content_type: str | None = "application/json") -> dict[str, str]:
        return build_rakuten_auth_headers(store_code=store_code, accept="application/json", content_type=content_type)

    def get_item_mapping(self, management_number: str, *, store_code: str) -> RakutenShopCategoryResult:
        url = _mapping_url(management_number)
        response = self._session_factory().get(url, headers=self._headers(store_code), timeout=30)
        success = 200 <= int(response.status_code) < 300
        body = summarize_response(response)
        return RakutenShopCategoryResult(
            success=success,
            management_number=management_number,
            http_status=int(response.status_code),
            response_body_summary=body,
            retryable=int(response.status_code) >= 500 or int(response.status_code) == 429,
            request_summary=sanitize_for_output({"method": "GET", "url": url, "management_number": management_number}),
            error_type=None if success else "http_error",
            error_message=None if success else str(body),
        )

    def get_category(self, category_id: str, *, store_code: str) -> RakutenShopCategoryResult:
        url = _category_url(category_id)
        response = self._session_factory().get(url, headers=self._headers(store_code), timeout=30)
        success = 200 <= int(response.status_code) < 300
        body = summarize_response(response)
        return RakutenShopCategoryResult(
            success=success,
            management_number="",
            http_status=int(response.status_code),
            response_body_summary=body,
            retryable=int(response.status_code) >= 500 or int(response.status_code) == 429,
            request_summary=sanitize_for_output({"method": "GET", "url": url, "category_id": category_id}),
            error_type=None if success else "http_error",
            error_message=None if success else str(body),
        )

    def put_item_mapping(self, management_number: str, payload: dict[str, Any], *, store_code: str) -> RakutenShopCategoryResult:
        url = _mapping_url(management_number)
        response = self._session_factory().put(url, headers=self._headers(store_code), json=payload, timeout=30)
        success = 200 <= int(response.status_code) < 300
        body = summarize_response(response)
        return RakutenShopCategoryResult(
            success=success,
            management_number=management_number,
            http_status=int(response.status_code),
            response_body_summary=body,
            retryable=int(response.status_code) >= 500 or int(response.status_code) == 429,
            request_summary=sanitize_for_output({"method": "PUT", "url": url, "management_number": management_number, "payload": payload}),
            error_type=None if success else "http_error",
            error_message=None if success else str(body),
        )


def response_json(result: RakutenShopCategoryResult) -> dict[str, Any]:
    body = dict(result.response_body_summary or {}).get("body_summary")
    return dict(body) if isinstance(body, dict) else {}
