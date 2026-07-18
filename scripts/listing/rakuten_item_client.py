from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

from scripts.listing.models import sanitize_for_output
from scripts.listing.rakuten_transport import build_rakuten_auth_headers, create_requests_session, summarize_response
from scripts.listing.text_sanitizer import sanitize_payload_text_for_rakuten_api


@dataclass
class RakutenItemRequest:
    management_number: str
    payload: dict[str, Any]
    headers: dict[str, str]
    timeout_seconds: float = 30.0
    url: str = ""


@dataclass
class RakutenItemResult:
    success: bool
    management_number: str
    http_status: int | None
    response_body_summary: dict[str, Any]
    retryable: bool
    request_summary: dict[str, Any]
    error_type: str | None = None
    error_message: str | None = None


def sanitize_item_payload_for_api(payload: dict[str, Any], *, management_number: str = "") -> dict[str, Any]:
    sanitized = sanitize_payload_text_for_rakuten_api(copy.deepcopy(payload or {}))
    if not isinstance(sanitized, dict):
        return {}

    if management_number and not str(sanitized.get("itemNumber") or "").strip():
        sanitized["itemNumber"] = management_number

    genre_id = sanitized.get("genreId")
    if genre_id is not None and str(genre_id).strip():
        sanitized["genreId"] = str(genre_id).strip()

    payment = sanitized.get("payment")
    if isinstance(payment, dict) and "taxRate" in payment and payment.get("taxRate") is not None and str(payment.get("taxRate")).strip():
        payment["taxRate"] = str(payment.get("taxRate")).strip()

    sanitized_images: list[dict[str, Any]] = []
    for image in list(sanitized.get("images") or []):
        if not isinstance(image, dict):
            continue
        image_type = str(image.get("type") or "").strip()
        location = str(image.get("location") or "").strip()
        if not image_type or not location:
            continue
        image_payload = {"type": image_type, "location": location}
        alt = str(image.get("alt") or "").strip()
        if alt:
            image_payload["alt"] = alt
        sanitized_images.append(image_payload)
    if sanitized_images:
        sanitized["images"] = sanitized_images
    else:
        sanitized.pop("images", None)

    variants = sanitized.get("variants")
    if isinstance(variants, dict):
        normalized_variants: dict[str, Any] = {}
        for variant_id, raw_variant in variants.items():
            if not isinstance(raw_variant, dict):
                continue
            variant = copy.deepcopy(raw_variant)
            standard_price = variant.get("standardPrice")
            if standard_price is not None and str(standard_price).strip():
                variant["standardPrice"] = str(standard_price).strip()
            article_number = variant.get("articleNumber")
            if isinstance(article_number, dict):
                exemption_reason = article_number.get("exemptionReason")
                if exemption_reason is not None and str(exemption_reason).strip():
                    variant["articleNumber"] = {"exemptionReason": int(exemption_reason)}
                else:
                    variant.pop("articleNumber", None)
            else:
                variant.pop("articleNumber", None)

            normalized_attributes: list[dict[str, Any]] = []
            for attribute in list(variant.get("attributes") or []):
                if not isinstance(attribute, dict):
                    continue
                name = str(attribute.get("name") or "").strip()
                if not name:
                    continue
                raw_values = attribute.get("values")
                values: list[str] = []
                if isinstance(raw_values, list):
                    values = [str(item).strip() for item in raw_values if str(item).strip()]
                else:
                    fallback_value = str(attribute.get("value") or "").strip()
                    if fallback_value:
                        values = [fallback_value]
                if not values:
                    continue
                normalized_attributes.append({"name": name, "values": values})
            if normalized_attributes:
                variant["attributes"] = normalized_attributes
            else:
                variant.pop("attributes", None)
            normalized_variants[str(variant_id)] = variant
        sanitized["variants"] = normalized_variants

    return sanitized


def build_item_request(management_number: str, payload: dict[str, Any], headers: dict[str, str], *, timeout_seconds: float = 30.0) -> RakutenItemRequest:
    sanitized_payload = sanitize_item_payload_for_api(payload, management_number=management_number)
    return RakutenItemRequest(
        management_number=management_number,
        payload=sanitized_payload,
        headers=dict(headers),
        timeout_seconds=timeout_seconds,
        url=f"https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/{management_number}",
    )


def build_item_request_summary(request: RakutenItemRequest) -> dict[str, Any]:
    return sanitize_for_output(
        {
            "management_number": request.management_number,
            "url": request.url,
            "timeout_seconds": request.timeout_seconds,
            "headers": request.headers,
            "payload_keys": sorted(request.payload.keys()),
            "variant_keys": sorted((request.payload.get("variants") or {}).keys()),
            "payload": request.payload,
        }
    )


class RakutenItemClient:
    def __init__(
        self,
        *,
        sender: Callable[[RakutenItemRequest], RakutenItemResult] | None = None,
    ) -> None:
        self._sender = sender

    def put_item(self, request: RakutenItemRequest) -> RakutenItemResult:
        if self._sender is None:
            return send_item_via_requests(request)
        return self._sender(request)


def send_item_via_requests(request: RakutenItemRequest) -> RakutenItemResult:
    session = create_requests_session()
    headers = build_rakuten_auth_headers(accept="application/json", content_type="application/json", extra_headers=request.headers)
    response = session.put(request.url, headers=headers, json=request.payload, timeout=request.timeout_seconds)
    success = 200 <= int(response.status_code) < 300
    return RakutenItemResult(
        success=success,
        management_number=request.management_number,
        http_status=int(response.status_code),
        response_body_summary=summarize_response(response),
        retryable=int(response.status_code) >= 500 or int(response.status_code) == 429,
        request_summary=build_item_request_summary(request),
        error_type=None if success else "http_error",
        error_message=None if success else str(summarize_response(response)),
    )
