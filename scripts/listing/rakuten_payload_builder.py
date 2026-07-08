
from __future__ import annotations

import math

from .models import EvaluationResult, StoreSettings


CUSTOMIZATION_OPTIONS = [
    "【ストアからのお知らせ】をご確認頂き、在庫確保ができない場合、キャンセルをさせて頂く場合がございますが、ご了承いただけますでしょうか？",
    "【Amazon倉庫から届くことについてご了承いただけますでしょうか？】弊社では一日でも早くお客様に商品をお届けする為、Amazonマルチチャネル(配送代行サービス)と提携しております。その際お荷物にAmazonのロゴや置き配となる場合がございます。",
    "【配達時間指定不可】配達時間の指定はできません。置配希望の方はご指定下さい。",
]


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
    options: list[dict[str, object]] = []
    for title in CUSTOMIZATION_OPTIONS:
        options.append(
            {
                "displayName": title,
                "inputType": "SINGLE_SELECTION",
                "required": True,
                "selections": [
                    {
                        "displayValue": "了承の上購入する",
                    }
                ],
            }
        )
    return options


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
        "standardPrice": standard_price,
        "normalDeliveryDateId": int(store_settings.normal_delivery_date_id),
        "backOrderDeliveryDateId": int(store_settings.back_order_delivery_date_id),
        "shipping": {
            "postageIncluded": True,
        },
        "articleNumber": evaluation.article_number,
        "attributes": evaluation.attributes,
    }

    return {
        "itemNumber": management_number,
        "title": evaluation.title,
        "itemType": "NORMAL",
        "genreId": int(evaluation.genre_id or 0),
        "productDescription": {
            "pc": evaluation.description_pc,
            "sp": evaluation.description_sp,
        },
        "payment": {
            "taxRate": 0.1,
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


def build_inventory_payload(
    *,
    management_number: str,
    quantity: int,
    store_settings: StoreSettings,
) -> dict[str, object]:
    safe_quantity = min(max(0, int(quantity)), int(store_settings.max_stock))
    return {
        "mode": "ABSOLUTE",
        "quantity": safe_quantity,
        "operationLeadTime": {
            "normalDeliveryTimeId": int(store_settings.normal_delivery_time_id),
            "backOrderDeliveryTimeId": int(store_settings.back_order_delivery_time_id),
        },
        "shipFromIds": list(store_settings.ship_from_ids),
        "variantPath": {
            "managementNumber": management_number,
            "variantKey": management_number,
        },
    }
