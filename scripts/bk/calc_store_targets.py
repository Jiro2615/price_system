import math
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from db_config import connect_db




def ceil_to_unit(value: int, unit: int) -> int:
    if unit <= 1:
        return int(value)
    return int(math.ceil(value / unit) * unit)


def calc_price(
    amazon_price: int,
    amazon_point: int,
    fee_rate: float,
    fixed_profit: int,
    fixed_cost: int,
    rounding_unit: int,
) -> int:
    base_cost = max(0, amazon_price - amazon_point) + fixed_profit + fixed_cost

    if fee_rate >= 1:
        raise ValueError(f"fee_rate が不正です: {fee_rate}")

    raw_price = base_cost / (1 - fee_rate)
    return ceil_to_unit(math.ceil(raw_price), rounding_unit)


def main() -> int:
    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    sp.id,
                    s.store_code,
                    sp.asin,
                    sp.current_stock,
                    sp.force_stop,
                    ap.amazon_price,
                    ap.amazon_point,
                    ap.available_qty,
                    ap.business_ng,
                    ap.system_error,
                    ap.ng_reason,
                    pr.fee_rate,
                    pr.fixed_profit,
                    pr.fixed_cost,
                    pr.rounding_unit
                FROM store_products sp
                JOIN stores s ON s.id = sp.store_id
                JOIN amazon_products ap ON ap.asin = sp.asin
                JOIN price_rules pr ON pr.store_id = sp.store_id
                WHERE sp.enabled = TRUE
                  AND pr.enabled = TRUE
                ORDER BY sp.id, pr.priority;
                """
            )

            rows = cur.fetchall()

            if not rows:
                print("計算対象の store_products がありません。")
                return 0

            updated = 0
            skipped = 0

            print("店舗別 target_price / target_stock 計算開始")
            print("")

            for row in rows:
                (
                    store_product_id,
                    store_code,
                    asin,
                    current_stock,
                    force_stop,
                    amazon_price,
                    amazon_point,
                    available_qty,
                    business_ng,
                    system_error,
                    ng_reason,
                    fee_rate,
                    fixed_profit,
                    fixed_cost,
                    rounding_unit,
                ) = row

                reason = ""
                target_price = None
                target_stock = current_stock if current_stock is not None else 0

                if force_stop:
                    target_stock = 0
                    reason = "force_stop"
                elif business_ng:
                    target_stock = 0
                    reason = f"business_ng: {ng_reason}"
                elif system_error:
                    # 一時的な取得失敗で即停止しない。現状維持。
                    target_stock = current_stock if current_stock is not None else 0
                    reason = f"system_error: {ng_reason}"
                elif amazon_price is None or amazon_price <= 0:
                    # Amazon価格未取得の商品は、楽天側の在庫を勝手に0にしない。
                    # まだ未チェックなだけの可能性があるため、現状維持にする。
                    target_price = None
                    target_stock = current_stock if current_stock is not None else 0
                    reason = "amazon_priceなし: 現状維持"
                else:
                    target_price = calc_price(
                        amazon_price=int(amazon_price),
                        amazon_point=int(amazon_point or 0),
                        fee_rate=float(fee_rate),
                        fixed_profit=int(fixed_profit or 0),
                        fixed_cost=int(fixed_cost or 0),
                        rounding_unit=int(rounding_unit or 10),
                    )
                    target_stock = int(available_qty or 0)
                    reason = "OK"

                cur.execute(
                    """
                    UPDATE store_products
                    SET
                        target_price = %s,
                        target_stock = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (
                        target_price,
                        target_stock,
                        store_product_id,
                    ),
                )

                updated += 1

                print(
                    f"{store_code} / {asin} / "
                    f"target_price={target_price} / "
                    f"target_stock={target_stock} / "
                    f"{reason}"
                )

            conn.commit()

            print("")
            print(f"計算完了: updated={updated}, skipped={skipped}")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())