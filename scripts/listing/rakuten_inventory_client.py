from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

from scripts.listing.models import sanitize_for_output
from scripts.listing.rakuten_transport import build_rakuten_auth_headers, create_requests_session, summarize_response


@dataclass
class RakutenInventoryRequest:
    management_number: str
    variant_id: str
    payload: dict[str, Any]
    headers: dict[str, str]
    store_code: str = ""
    timeout_seconds: float = 30.0
    url: str = ""


@dataclass
class RakutenInventoryResult:
    success: bool
    management_number: str
    http_status: int | None
    response_body_summary: dict[str, Any]
    retryable: bool
    request_summary: dict[str, Any]
    error_type: str | None = None
    error_message: str | None = None


def sanitize_inventory_payload_for_api(payload: dict[str, Any]) -> dict[str, Any]:
    source = copy.deepcopy(payload or {})
    if not isinstance(source, dict):
        return {}

    sanitized: dict[str, Any] = {}

    mode = str(source.get("mode") or "").strip()
    if mode:
        sanitized["mode"] = mode

    quantity = source.get("quantity")
    if quantity is not None and str(quantity).strip():
        sanitized["quantity"] = int(quantity)

    operation = source.get("operationLeadTime")
    if isinstance(operation, dict):
        normalized_operation: dict[str, int] = {}
        if operation.get("normalDeliveryTimeId") is not None and str(operation.get("normalDeliveryTimeId")).strip():
            normalized_operation["normalDeliveryTimeId"] = int(operation.get("normalDeliveryTimeId"))
        if operation.get("backOrderDeliveryTimeId") is not None and str(operation.get("backOrderDeliveryTimeId")).strip():
            normalized_operation["backOrderDeliveryTimeId"] = int(operation.get("backOrderDeliveryTimeId"))
        if normalized_operation:
            sanitized["operationLeadTime"] = normalized_operation

    ship_from_ids = source.get("shipFromIds")
    if isinstance(ship_from_ids, list):
        normalized_ship_from_ids = [int(item) for item in ship_from_ids if str(item).strip()]
        if normalized_ship_from_ids:
            sanitized["shipFromIds"] = normalized_ship_from_ids

    return sanitized


def extract_inventory_path_parts(management_number: str, payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    variant_path = payload.get("variantPath") if isinstance(payload, dict) else None
    if not isinstance(variant_path, dict):
        variant_path = {}
    request_management_number = str(variant_path.get("managementNumber") or management_number or "").strip()
    request_variant_id = str(variant_path.get("variantKey") or management_number or "").strip()
    return request_management_number, request_variant_id, variant_path


def build_inventory_request(management_number: str, payload: dict[str, Any], headers: dict[str, str], *, store_code: str = "", timeout_seconds: float = 30.0) -> RakutenInventoryRequest:
    request_management_number, request_variant_id, _ = extract_inventory_path_parts(management_number, payload)
    sanitized_payload = sanitize_inventory_payload_for_api(payload)
    return RakutenInventoryRequest(
        management_number=request_management_number,
        variant_id=request_variant_id,
        payload=sanitized_payload,
        headers=dict(headers),
        store_code=store_code,
        timeout_seconds=timeout_seconds,
        url=(
            "https://api.rms.rakuten.co.jp/es/2.1/inventories/"
            f"manage-numbers/{request_management_number}/variants/{request_variant_id}"
        ),
    )


def build_inventory_request_summary(request: RakutenInventoryRequest) -> dict[str, Any]:
    return sanitize_for_output(
        {
            "management_number": request.management_number,
            "store_code": request.store_code,
            "variant_id": request.variant_id,
            "url": request.url,
            "timeout_seconds": request.timeout_seconds,
            "headers": request.headers,
            "payload_keys": sorted(request.payload.keys()),
            "payload": request.payload,
        }
    )


class RakutenInventoryClient:
    def __init__(
        self,
        *,
        sender: Callable[[RakutenInventoryRequest], RakutenInventoryResult] | None = None,
    ) -> None:
        self._sender = sender

    def put_inventory(self, request: RakutenInventoryRequest) -> RakutenInventoryResult:
        if self._sender is None:
            return send_inventory_via_requests(request)
        return self._sender(request)


def send_inventory_via_requests(request: RakutenInventoryRequest) -> RakutenInventoryResult:
    session = create_requests_session()
    headers = build_rakuten_auth_headers(store_code=request.store_code, accept="application/json", content_type="application/json", extra_headers=request.headers)
    response = session.put(request.url, headers=headers, json=request.payload, timeout=request.timeout_seconds)
    success = 200 <= int(response.status_code) < 300
    return RakutenInventoryResult(
        success=success,
        management_number=request.management_number,
        http_status=int(response.status_code),
        response_body_summary=summarize_response(response),
        retryable=int(response.status_code) >= 500 or int(response.status_code) == 429,
        request_summary=build_inventory_request_summary(request),
        error_type=None if success else "http_error",
        error_message=None if success else str(summarize_response(response)),
    )
