
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from scripts.db_config import connect_db

from .models import StoreSettings


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"


def _env_names(store_code: str, suffix: str) -> tuple[str, str]:
    prefix = store_code.upper()
    return (f"{prefix}_{suffix}", f"RAKUTEN_LISTING_{suffix}")


def _get_env(store_code: str, suffix: str, default: str = "") -> str:
    load_dotenv(ENV_PATH)
    for name in _env_names(store_code, suffix):
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _to_int(value, default: int) -> int:
    if value is None or value == "":
        return default
    return int(float(value))


def _to_float(value, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _to_bool(value, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_list(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _decimal_to_float(value, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def get_store_settings(store_code: str) -> StoreSettings:
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.id,
                s.store_code,
                s.store_name,
                s.max_stock,
                s.fee_rate,
                s.use_amazon_point,
                s.profit_mode,
                s.fixed_cost,
                s.rounding_unit,
                pr.profit_rate,
                COALESCE(pr.profit_amount, pr.fixed_profit, 0) AS profit_amount,
                pr.fee_rate AS rule_fee_rate,
                pr.fixed_cost AS rule_fixed_cost,
                pr.rounding_unit AS rule_rounding_unit
            FROM stores s
            LEFT JOIN LATERAL (
                SELECT *
                FROM price_rules pr
                WHERE pr.store_id = s.id
                  AND pr.enabled = TRUE
                ORDER BY pr.priority, pr.id
                LIMIT 1
            ) pr ON TRUE
            WHERE s.store_code = %s
            """,
            (store_code,),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError(f"store not found: {store_code}")

    (
        store_id,
        resolved_store_code,
        store_name,
        max_stock,
        fee_rate,
        use_amazon_point,
        profit_mode,
        fixed_cost,
        rounding_unit,
        profit_rate,
        profit_amount,
        rule_fee_rate,
        rule_fixed_cost,
        rule_rounding_unit,
    ) = row

    if max_stock is None or int(max_stock) < 0:
        raise RuntimeError(f"max_stock is not configured safely: store_code={store_code}, max_stock={max_stock}")

    effective_fee_rate = _to_float(_get_env(store_code, "FEE_RATE", ""), _decimal_to_float(rule_fee_rate, _decimal_to_float(fee_rate, 0.15)))
    effective_fixed_cost = _to_int(_get_env(store_code, "FIXED_COST", ""), int(rule_fixed_cost or fixed_cost or 0))
    effective_rounding_unit = _to_int(_get_env(store_code, "ROUNDING_UNIT", ""), int(rule_rounding_unit or rounding_unit or 1))
    effective_profit_rate = _to_float(_get_env(store_code, "PROFIT_RATE", ""), float(profit_rate or 0.0))
    effective_profit_amount = _to_int(_get_env(store_code, "PROFIT_AMOUNT", ""), int(profit_amount or 300))
    min_avg90_sellers = _to_float(_get_env(store_code, "MIN_AVG90_SELLERS", "3.5"), 3.5)

    ship_from_ids = _to_list(_get_env(store_code, "SHIP_FROM_IDS", "1"))
    if not ship_from_ids:
        raise RuntimeError(f"ship_from_ids is empty: store_code={store_code}")

    return StoreSettings(
        store_id=int(store_id),
        store_code=str(resolved_store_code),
        store_name=str(store_name or resolved_store_code),
        max_stock=int(max_stock),
        fee_rate=effective_fee_rate,
        use_amazon_point=_to_bool(_get_env(store_code, "USE_AMAZON_POINT", ""), bool(use_amazon_point)),
        profit_mode=_get_env(store_code, "PROFIT_MODE", str(profit_mode or "amount")),
        profit_rate=effective_profit_rate,
        profit_amount=effective_profit_amount,
        fixed_cost=effective_fixed_cost,
        rounding_unit=max(1, effective_rounding_unit),
        normal_delivery_date_id=_to_int(_get_env(store_code, "NORMAL_DELIVERY_DATE_ID", "1"), 1),
        back_order_delivery_date_id=_to_int(_get_env(store_code, "BACK_ORDER_DELIVERY_DATE_ID", "1"), 1),
        normal_delivery_time_id=_to_int(_get_env(store_code, "NORMAL_DELIVERY_TIME_ID", "1"), 1),
        back_order_delivery_time_id=_to_int(_get_env(store_code, "BACK_ORDER_DELIVERY_TIME_ID", "1"), 1),
        ship_from_ids=ship_from_ids,
        min_avg90_sellers=min_avg90_sellers,
        management_suffix=_get_env(store_code, "MANAGEMENT_SUFFIX", "187") or "187",
    )
