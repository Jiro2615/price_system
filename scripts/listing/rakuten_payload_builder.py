
from __future__ import annotations

import math

from scripts.listing.models import EvaluationResult, StoreSettings
from scripts.listing.text_sanitizer import sanitize_payload_text_for_rakuten_api


CUSTOMIZATION_OPTION_AMAZON_MCF_NOTICE = (
    "◆当店ではAmazonマルチチャネルサービスを利用しての発送となり、"
    "その際無地のダンボールではない場合がございます。この点、"
    "ご了承いただけますでしょうか？"
)
CUSTOMIZATION_OPTION_ACCEPT_VALUE = "了承の上購入する"

REPRESENTATIVE_COLOR_ALLOWED_VALUES = {
    "-",
    "ブラック",
    "グレー",
    "ホワイト",
    "ブラウン",
    "ベージュ",
    "カーキグリーン",
    "ピンク",
    "ワインレッド",
    "レッド",
    "オレンジ",
    "イエロー",
    "グリーン",
    "ブルー",
    "ネイビー",
    "パープル",
    "ゴールド",
    "シルバー",
    "透明",
    "マルチカラー",
}

REPRESENTATIVE_COLOR_API_MAPPING = {
    "クリアブルーラメ": "ブルー",
}


CATALOG_ID_EXEMPTION_REASON_NO_APPLICABLE_PRODUCT_CODE = 5


def calc_listing_price(
    *,
    amazon_price: int,
    amazon_point: int,
    store_settings: StoreSettings,
) -> int:
    if amazon_price <= 0:
        raise ValueError("amazon_price must be positive")
    if store_settings.fee_rate < 0 or store_settings.fee_rate >= 1:
        raise ValueError(f"fee_rate is invalid: {store_settings.fee_rate}")

    amazon_cost = amazon_price - amazon_point if store_settings.use_amazon_point else amazon_price
    amazon_cost = max(0, int(amazon_cost))

    if str(store_settings.profit_mode or "amount").lower() == "rate":
        calculated_profit = math.ceil(amazon_cost * float(store_settings.profit_rate or 0.0))
    else:
        calculated_profit = int(store_settings.profit_amount or 0)

    base_cost = amazon_cost + int(store_settings.fixed_cost or 0) + calculated_profit
    raw_price = base_cost / (1 - float(store_settings.fee_rate))
    rounded = int(math.ceil(raw_price))
    unit = max(1, int(store_settings.rounding_unit or 1))
    if unit > 1:
        rounded = int(math.ceil(rounded / unit) * unit)
    return rounded


def build_customization_options() -> list[dict[str, object]]:
    return [
        {
            "displayName": CUSTOMIZATION_OPTION_AMAZON_MCF_NOTICE,
            "inputType": "MULTIPLE_SELECTION",
            "required": True,
            "selections": [
                {
                    "displayValue": CUSTOMIZATION_OPTION_ACCEPT_VALUE,
                }
            ],
        }
    ]


def _normalize_attribute_value_for_api(*, genre_id: int, name: str, value: str) -> str:
    if genre_id == 213661 and name == "代表カラー":
        if value in REPRESENTATIVE_COLOR_ALLOWED_VALUES:
            return value
        return REPRESENTATIVE_COLOR_API_MAPPING.get(value, "")
    return value


def _build_api_attributes(evaluation: EvaluationResult) -> list[dict[str, object]]:
    genre_id = int(evaluation.genre_id or 0)
    attributes: list[dict[str, object]] = []
    for attribute in evaluation.attributes:
        name = str(attribute.get("name") or "")
        value = str(attribute.get("value") or "")
        api_value = _normalize_attribute_value_for_api(genre_id=genre_id, name=name, value=value)
        if not name or not api_value:
            continue
        attributes.append({"name": name, "values": [api_value]})
    return attributes


def build_item_payload(
    *,
    management_number: str,
    evaluation: EvaluationResult,
    store_settings: StoreSettings,
    amazon_price: int,
    amazon_point: int,
) -> dict[str, object]:
    standard_price = calc_listing_price(
        amazon_price=amazon_price,
        amazon_point=amazon_point,
        store_settings=store_settings,
    )

    variant = {
        "standardPrice": str(standard_price),
        "normalDeliveryDateId": int(store_settings.normal_delivery_date_id),
        "backOrderDeliveryDateId": int(store_settings.back_order_delivery_date_id),
        "shipping": {
            "postageIncluded": True,
        },
        "articleNumber": {
            "exemptionReason": CATALOG_ID_EXEMPTION_REASON_NO_APPLICABLE_PRODUCT_CODE,
        },
        "attributes": _build_api_attributes(evaluation),
    }

    payload = {
        "itemNumber": management_number,
        "title": evaluation.title,
        "itemType": "NORMAL",
        "genreId": str(int(evaluation.genre_id or 0)),
        "productDescription": {
            "pc": evaluation.description_pc,
            "sp": evaluation.description_sp,
        },
        "payment": {
            "taxRate": "0.1",
        },
        "features": {
            "inventoryDisplay": "DISPLAY_ABSOLUTE_STOCK_COUNT",
        },
        "images": [
            {
                "type": "CABINET",
                "location": f"/{management_number}_1.jpg",
            }
        ],
        "customizationOptions": build_customization_options(),
        "variants": {
            management_number: variant,
        },
    }
    return sanitize_payload_text_for_rakuten_api(payload)


def build_inventory_payload(
    *,
    management_number: str,
    quantity: int,
    store_settings: StoreSettings,
) -> dict[str, object]:
    safe_quantity = min(max(0, int(quantity)), int(store_settings.max_stock))
    payload: dict[str, object] = {
        "mode": "ABSOLUTE",
        "quantity": safe_quantity,
        "variantPath": {
            "managementNumber": management_number,
            "variantKey": management_number,
        },
    }
    if bool(getattr(store_settings, "send_inventory_delivery_ids", False)):
        normal_id = int(store_settings.normal_delivery_time_id or 0)
        back_order_id = int(store_settings.back_order_delivery_time_id or 0)
        ship_from_ids = [int(item) for item in list(store_settings.ship_from_ids) if str(item).strip()]
        if normal_id > 0 or back_order_id > 0:
            operation: dict[str, int] = {}
            if normal_id > 0:
                operation["normalDeliveryTimeId"] = normal_id
            if back_order_id > 0:
                operation["backOrderDeliveryTimeId"] = back_order_id
            payload["operationLeadTime"] = operation
        if ship_from_ids:
            payload["shipFromIds"] = ship_from_ids
    return payload
