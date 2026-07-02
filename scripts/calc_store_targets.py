import argparse
import math
from typing import Optional

from db_config import connect_db


# =========================
# 計算ユーティリティ
# =========================
def ceil_to_unit(value: int, unit: int) -> int:
    """指定単位で切り上げ。unit=10なら1円単位計算後に10円単位へ切り上げ。"""
    if unit <= 1:
        return int(value)
    return int(math.ceil(value / unit) * unit)


def to_int(value, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def to_float(value, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def calc_price(
    *,
    amazon_price: int,
    amazon_point: int,
    use_amazon_point: bool,
    fee_rate: float,
    profit_mode: str,
    profit_rate: float,
    profit_amount: int,
    fixed_cost: int,
    rounding_unit: int,
) -> int:
    """
    楽天販売予定価格を計算する。

    profit_mode:
      amount: Amazon原価 + 固定コスト + 利益額 を、楽天手数料で割り戻す
      rate  : Amazon原価に利益率を乗せた利益額を足し、楽天手数料で割り戻す

    use_amazon_point:
      True  : Amazon価格 - Amazonポイント を仕入原価として扱う
      False : Amazon価格のみを仕入原価として扱う
    """
    if fee_rate < 0 or fee_rate >= 1:
        raise ValueError(f"fee_rate が不正です: {fee_rate}")

    amazon_cost = amazon_price
    if use_amazon_point:
        amazon_cost = max(0, amazon_price - amazon_point)

    fixed_cost = int(fixed_cost or 0)
    rounding_unit = int(rounding_unit or 10)
    profit_mode = (profit_mode or "amount").strip().lower()

    if profit_mode == "rate":
        # 旧システム互換を想定し、利益率は「Amazon原価に対する利益率」として扱う。
        # 例: amazon_cost=3000, profit_rate=0.20 -> 利益額600円
        calculated_profit = math.ceil(amazon_cost * float(profit_rate or 0))
        base_cost = amazon_cost + fixed_cost + calculated_profit
    else:
        base_cost = amazon_cost + fixed_cost + int(profit_amount or 0)

    raw_price = base_cost / (1 - fee_rate)
    return ceil_to_unit(math.ceil(raw_price), rounding_unit)


# =========================
# DB処理
# =========================
def fetch_calc_targets(conn, store_code: str | None):
    where = [
        "sp.enabled = TRUE",
        "sp.asin IS NOT NULL",
    ]
    params = []

    if store_code:
        where.append("s.store_code = %s")
        params.append(store_code)

    # 価格帯ルールは、商品ごとに必ず1件だけ選ぶ。
    # default : Amazon価格帯に一致するprice_rulesをpriority順で1件
    # uniform : price_rulesの先頭1件を一律ルールとして使う
    #
    # default時は min_amazon_price IS NOT NULL のルールだけを価格帯ルール扱いする。
    # これにより、昔の一律ルール(min/max NULL)が混ざっても誤爆しにくくする。
    sql = f"""
        SELECT
            sp.id AS store_product_id,
            s.store_code,
            s.price_modify_enabled,
            s.price_rule_type,
            s.profit_mode,
            s.use_amazon_point,
            s.fee_rate AS store_fee_rate,
            s.rounding_unit AS store_rounding_unit,
            s.fixed_cost AS store_fixed_cost,
            sp.asin,
            sp.mall_item_code,
            sp.sku_code,
            sp.current_price,
            sp.current_stock,
            sp.force_stop,
            ap.amazon_price,
            ap.amazon_point,
            ap.available_qty,
            ap.business_ng,
            ap.system_error,
            ap.ng_reason,
            ap.checked_at,
            pr.id AS rule_id,
            pr.rule_name,
            pr.priority AS rule_priority,
            pr.min_amazon_price,
            pr.max_amazon_price,
            pr.profit_rate,
            pr.profit_amount,
            pr.fee_rate AS rule_fee_rate,
            pr.fixed_profit AS rule_fixed_profit,
            pr.fixed_cost AS rule_fixed_cost,
            pr.rounding_unit AS rule_rounding_unit
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        JOIN amazon_products ap ON ap.asin = sp.asin
        LEFT JOIN LATERAL (
            SELECT pr.*
            FROM price_rules pr
            WHERE pr.store_id = sp.store_id
              AND pr.enabled = TRUE
              AND (
                    (
                        s.price_rule_type = 'uniform'
                    )
                    OR
                    (
                        COALESCE(s.price_rule_type, 'default') = 'default'
                        AND ap.amazon_price IS NOT NULL
                        AND pr.min_amazon_price IS NOT NULL
                        AND ap.amazon_price >= pr.min_amazon_price
                        AND (pr.max_amazon_price IS NULL OR ap.amazon_price <= pr.max_amazon_price)
                    )
                  )
            ORDER BY pr.priority, pr.id
            LIMIT 1
        ) pr ON TRUE
        WHERE {" AND ".join(where)}
        ORDER BY s.store_code, sp.id;
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def update_store_product_target(conn, store_product_id: int, target_price: Optional[int], target_stock: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE store_products
            SET
                target_price = %s,
                target_stock = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (target_price, target_stock, store_product_id),
        )


# =========================
# メイン
# =========================
def main() -> int:
    parser = argparse.ArgumentParser(description="店舗別 target_price / target_stock を計算します。")
    parser.add_argument("--store", default="", help="rakuten_1 など。空なら全店舗")
    parser.add_argument("--dry-run", action="store_true", help="DB更新せず計算結果だけ表示")
    args = parser.parse_args()

    store_code = args.store.strip() or None

    conn = connect_db()

    try:
        rows = fetch_calc_targets(conn, store_code)

        if not rows:
            print("計算対象の store_products がありません。")
            return 0

        updated = 0
        skipped = 0
        errors = 0

        print("店舗別 target_price / target_stock 計算開始")
        if args.dry_run:
            print("dry-run: DB更新しません")
        print("")

        for row in rows:
            (
                store_product_id,
                store_code,
                price_modify_enabled,
                price_rule_type,
                profit_mode,
                use_amazon_point,
                store_fee_rate,
                store_rounding_unit,
                store_fixed_cost,
                asin,
                mall_item_code,
                sku_code,
                current_price,
                current_stock,
                force_stop,
                amazon_price,
                amazon_point,
                available_qty,
                business_ng,
                system_error,
                ng_reason,
                checked_at,
                rule_id,
                rule_name,
                rule_priority,
                min_amazon_price,
                max_amazon_price,
                profit_rate,
                profit_amount,
                rule_fee_rate,
                rule_fixed_profit,
                rule_fixed_cost,
                rule_rounding_unit,
            ) = row

            reason = ""
            target_price: Optional[int] = None
            target_stock = current_stock if current_stock is not None else 0

            try:
                if force_stop:
                    target_stock = 0
                    reason = "force_stop"

                elif business_ng:
                    target_stock = 0
                    reason = f"business_ng: {ng_reason or ''}"

                elif system_error:
                    # 一時的な取得失敗で即停止しない。現状維持。
                    target_price = None
                    target_stock = current_stock if current_stock is not None else 0
                    reason = f"system_error: {ng_reason or ''}: 現状維持"

                elif amazon_price is None or to_int(amazon_price, 0) <= 0:
                    # Amazon価格未取得の商品は、楽天側の在庫を勝手に0にしない。
                    target_price = None
                    target_stock = current_stock if current_stock is not None else 0
                    reason = "amazon_priceなし: 現状維持"

                else:
                    # Amazon取得OKなら在庫はAmazon取得可能数へ寄せる。
                    target_stock = int(available_qty or 0)

                    if not price_modify_enabled:
                        target_price = None
                        reason = "価格改定OFF / stockのみ"

                    elif rule_id is None:
                        target_price = None
                        reason = "価格ルールなし / stockのみ"

                    else:
                        fee_rate = to_float(rule_fee_rate, to_float(store_fee_rate, 0.116))
                        fixed_cost = to_int(rule_fixed_cost, to_int(store_fixed_cost, 0)) or 0
                        rounding_unit = to_int(rule_rounding_unit, to_int(store_rounding_unit, 10)) or 10

                        # profit_amountは新カラム優先。未設定なら既存 fixed_profit を互換利用。
                        selected_profit_amount = to_int(profit_amount, to_int(rule_fixed_profit, 0)) or 0
                        selected_profit_rate = to_float(profit_rate, 0.0)

                        target_price = calc_price(
                            amazon_price=int(amazon_price),
                            amazon_point=int(amazon_point or 0),
                            use_amazon_point=bool(use_amazon_point),
                            fee_rate=fee_rate,
                            profit_mode=str(profit_mode or "amount"),
                            profit_rate=selected_profit_rate,
                            profit_amount=selected_profit_amount,
                            fixed_cost=fixed_cost,
                            rounding_unit=rounding_unit,
                        )

                        reason = (
                            f"OK / rule={rule_name or rule_id} / "
                            f"type={price_rule_type or 'default'} / "
                            f"mode={profit_mode or 'amount'} / "
                            f"point={'ON' if use_amazon_point else 'OFF'}"
                        )

                if not args.dry_run:
                    update_store_product_target(conn, store_product_id, target_price, int(target_stock or 0))

                updated += 1

                print(
                    f"{store_code} / {asin} / "
                    f"Item={mall_item_code or ''} / SKU={sku_code or ''} / "
                    f"amazon_price={amazon_price} / "
                    f"target_price={target_price} / "
                    f"stock={current_stock}->{target_stock} / "
                    f"{reason}"
                )

            except Exception as e:
                errors += 1
                skipped += 1
                print(
                    f"ERROR / {store_code} / {asin} / "
                    f"Item={mall_item_code or ''} / SKU={sku_code or ''} / {e}"
                )

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

        print("")
        print(f"計算完了: updated={updated}, skipped={skipped}, errors={errors}")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
