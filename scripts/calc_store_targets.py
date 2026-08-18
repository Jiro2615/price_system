import argparse
import math
from typing import Optional

from db_config import connect_db


def ceil_to_unit(value: int, unit: int) -> int:
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
    if fee_rate < 0 or fee_rate >= 1:
        raise ValueError(f"fee_rate is invalid: {fee_rate}")

    amazon_cost = amazon_price
    if use_amazon_point:
        amazon_cost = max(0, amazon_price - amazon_point)

    fixed_cost = int(fixed_cost or 0)
    rounding_unit = int(rounding_unit or 10)
    profit_mode = (profit_mode or "amount").strip().lower()

    if profit_mode == "rate":
        calculated_profit = math.ceil(amazon_cost * float(profit_rate or 0))
        base_cost = amazon_cost + fixed_cost + calculated_profit
    else:
        base_cost = amazon_cost + fixed_cost + int(profit_amount or 0)

    raw_price = base_cost / (1 - fee_rate)
    return ceil_to_unit(int(math.ceil(raw_price)), rounding_unit)


def parse_asin_args(single_asin: str, asin_list: str) -> list[str] | None:
    asins: list[str] = []

    if single_asin.strip():
        asins.append(single_asin.strip())

    if asin_list.strip():
        for asin in asin_list.split(","):
            value = asin.strip()
            if value:
                asins.append(value)

    if not asins:
        return None

    unique_asins: list[str] = []
    seen = set()
    for asin in asins:
        if asin not in seen:
            seen.add(asin)
            unique_asins.append(asin)
    return unique_asins


def has_table_column(conn, table_name: str, column_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        )
        return cur.fetchone() is not None


def has_table(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        return cur.fetchone() is not None


def apply_rakuten_competitor_price_floor(
    base_target_price: int,
    competitor_price_enabled: bool,
    competitor_lowest_price: Optional[int],
) -> tuple[int, bool]:
    """Prevent unnecessary underpricing without lowering a profit-based target."""
    competitor_price = to_int(competitor_lowest_price)
    if not competitor_price_enabled or competitor_price is None or competitor_price <= base_target_price:
        return base_target_price, False
    return competitor_price, True


def calculate_profit_amount(
    selling_price: int,
    amazon_price: int,
    amazon_point: int,
    use_amazon_point: bool,
    fee_rate: float,
    fixed_cost: int,
) -> int:
    amazon_cost = amazon_price - amazon_point if use_amazon_point else amazon_price
    return int(math.floor(selling_price * (1 - fee_rate) - amazon_cost - fixed_cost))


def apply_rakuten_competitor_price_rules(
    *,
    base_target_price: int,
    competitor_price_enabled: bool,
    competitor_lowest_price: Optional[int],
    competitor_undercut_yen: int,
    competitor_floor_enabled: bool,
    competitor_undercut_enabled: bool,
    competitor_min_profit_amount: int,
    amazon_price: int,
    amazon_point: int,
    use_amazon_point: bool,
    fee_rate: float,
    fixed_cost: int,
) -> tuple[int, str]:
    competitor_price = to_int(competitor_lowest_price)
    if not competitor_price_enabled or competitor_price is None:
        return base_target_price, ""
    market_price = max(1, competitor_price - max(0, int(competitor_undercut_yen or 0)))
    if competitor_undercut_enabled:
        profit = calculate_profit_amount(market_price, amazon_price, amazon_point, use_amazon_point, fee_rate, fixed_cost)
        if profit >= max(0, int(competitor_min_profit_amount or 0)):
            return market_price, f"rakuten_competitor_undercut={market_price}/profit={profit}"
    if competitor_floor_enabled and market_price > base_target_price:
        return market_price, f"rakuten_competitor_floor={market_price}"
    return base_target_price, ""


def resolve_store_max_stock(store_code: str, store_max_stock: Optional[int]) -> int:
    max_stock = to_int(store_max_stock)
    if max_stock is None:
        raise ValueError(f"max_stock is not configured: store_code={store_code}")
    if max_stock < 0:
        raise ValueError(f"max_stock is invalid: store_code={store_code}, max_stock={max_stock}")
    return max_stock


def fetch_calc_targets(conn, store_code: str | None = None, asins: list[str] | None = None):
    where = [
        "sp.enabled = TRUE",
        "sp.asin IS NOT NULL",
    ]
    params = []

    if store_code:
        where.append("s.store_code = %s")
        params.append(store_code)

    if asins:
        where.append("sp.asin = ANY(%s)")
        params.append(asins)

    has_store_max_stock = has_table_column(conn, "stores", "max_stock")
    if not has_store_max_stock:
        raise RuntimeError("stores.max_stock column is required for safe target_stock calculation")

    has_competitor_setting = has_table_column(conn, "store_settings", "rakuten_competitor_price_enabled")
    has_competitor_snapshots = has_table(conn, "rakuten_competitor_price_snapshots")
    competitor_setting_select = (
        "COALESCE(ss.rakuten_competitor_price_enabled, FALSE)"
        if has_competitor_setting
        else "FALSE"
    )
    competitor_settings_join = "LEFT JOIN store_settings ss ON ss.store_id = s.id" if has_competitor_setting else ""
    competitor_snapshot_select = "rcp.item_price" if has_competitor_snapshots else "NULL::integer"
    competitor_snapshot_join = """
        LEFT JOIN LATERAL (
            SELECT rcp.item_price
            FROM rakuten_competitor_price_snapshots rcp
            WHERE rcp.asin = sp.asin
              AND rcp.postage_included = TRUE
              AND rcp.availability = TRUE
              AND rcp.fetched_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
            ORDER BY rcp.item_price, rcp.fetched_at DESC
            LIMIT 1
        ) rcp ON TRUE
    """ if has_competitor_snapshots else ""
    def setting_select(column_name: str, default: str) -> str:
        return f"COALESCE(ss.{column_name}, {default})" if has_table_column(conn, "store_settings", column_name) else default

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
            s.max_stock AS store_max_stock,
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
            pr.fixed_cost AS rule_fixed_cost,
            pr.rounding_unit AS rule_rounding_unit,
            {competitor_setting_select} AS rakuten_competitor_price_enabled,
            {competitor_snapshot_select} AS rakuten_competitor_lowest_price,
            {setting_select('rakuten_competitor_floor_enabled', 'FALSE')} AS rakuten_competitor_floor_enabled,
            {setting_select('rakuten_competitor_undercut_enabled', 'FALSE')} AS rakuten_competitor_undercut_enabled,
            {setting_select('rakuten_competitor_undercut_yen', '0')} AS rakuten_competitor_undercut_yen,
            {setting_select('rakuten_competitor_min_profit_amount', '0')} AS rakuten_competitor_min_profit_amount
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        JOIN amazon_products ap ON ap.asin = sp.asin
        {competitor_settings_join}
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
        {competitor_snapshot_join}
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


def calc_target_for_row(row) -> dict:
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
        store_max_stock,
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
        rule_fixed_cost,
        rule_rounding_unit,
        rakuten_competitor_price_enabled,
        rakuten_competitor_lowest_price,
        rakuten_competitor_floor_enabled,
        rakuten_competitor_undercut_enabled,
        rakuten_competitor_undercut_yen,
        rakuten_competitor_min_profit_amount,
    ) = row

    reason = ""
    target_price: Optional[int] = None
    target_stock = current_stock if current_stock is not None else 0
    max_stock = resolve_store_max_stock(store_code, store_max_stock)

    if force_stop:
        target_stock = 0
        reason = "force_stop"
    elif business_ng:
        target_stock = 0
        reason = f"business_ng: {ng_reason or ''}"
    elif system_error:
        target_price = None
        target_stock = current_stock if current_stock is not None else 0
        reason = f"system_error: {ng_reason or ''}: keep current stock"
    elif amazon_price is None or to_int(amazon_price, 0) <= 0:
        target_price = None
        target_stock = current_stock if current_stock is not None else 0
        reason = "amazon_price missing: keep current stock"
    else:
        target_stock = min(int(available_qty or 0), max_stock)

        if not price_modify_enabled:
            target_price = None
            reason = "price_modify_enabled=OFF / stock only"
        elif rule_id is None:
            target_price = None
            reason = "no price rule / stock only"
        else:
            fee_rate = to_float(rule_fee_rate, to_float(store_fee_rate, 0.116))
            fixed_cost = to_int(rule_fixed_cost, to_int(store_fixed_cost, 0)) or 0
            rounding_unit = to_int(rule_rounding_unit, to_int(store_rounding_unit, 10)) or 10
            selected_profit_amount = to_int(profit_amount, 0) or 0
            selected_profit_rate = to_float(profit_rate, 0.0)

            base_target_price = calc_price(
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
            target_price, competitor_reason = apply_rakuten_competitor_price_rules(
                base_target_price=base_target_price,
                competitor_price_enabled=bool(rakuten_competitor_price_enabled),
                competitor_lowest_price=rakuten_competitor_lowest_price,
                competitor_undercut_yen=to_int(rakuten_competitor_undercut_yen, 0) or 0,
                competitor_floor_enabled=bool(rakuten_competitor_floor_enabled),
                competitor_undercut_enabled=bool(rakuten_competitor_undercut_enabled),
                competitor_min_profit_amount=to_int(rakuten_competitor_min_profit_amount, 0) or 0,
                amazon_price=int(amazon_price),
                amazon_point=int(amazon_point or 0),
                use_amazon_point=bool(use_amazon_point),
                fee_rate=fee_rate,
                fixed_cost=fixed_cost,
            )

            reason = (
                f"OK / rule={rule_name or rule_id} / "
                f"type={price_rule_type or 'default'} / "
                f"mode={profit_mode or 'amount'} / "
                f"point={'ON' if use_amazon_point else 'OFF'}"
            )
            if competitor_reason:
                reason += f" / {competitor_reason}"

        reason += f" / max_stock={max_stock}"

    return {
        "store_product_id": store_product_id,
        "store_code": store_code,
        "asin": asin,
        "mall_item_code": mall_item_code,
        "sku_code": sku_code,
        "amazon_price": amazon_price,
        "current_price": current_price,
        "current_stock": current_stock,
        "target_price": target_price,
        "target_stock": int(target_stock or 0),
        "reason": reason,
    }


def recalc_targets(
    conn,
    store_code: str | None = None,
    asins: list[str] | None = None,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    rows = fetch_calc_targets(conn, store_code=store_code, asins=asins)

    if not rows:
        return {
            "rows": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "targets": [],
        }

    updated = 0
    skipped = 0
    errors = 0
    targets: list[dict] = []

    if verbose:
        print("calculate target_price / target_stock start")
        if dry_run:
            print("dry-run: no DB updates")
        if asins:
            print(f"asin filter: {', '.join(asins)}")
        print("")

    for row in rows:
        result = None
        try:
            result = calc_target_for_row(row)
            if not dry_run:
                update_store_product_target(
                    conn,
                    result["store_product_id"],
                    result["target_price"],
                    result["target_stock"],
                )

            updated += 1
            # Callers which update one ASIN at a time need the exact calculated
            # values to confirm that the transaction reached store_products.
            targets.append(result)

            if verbose:
                print(
                    f"{result['store_code']} / {result['asin']} / "
                    f"Item={result['mall_item_code'] or ''} / SKU={result['sku_code'] or ''} / "
                    f"amazon_price={result['amazon_price']} / "
                    f"target_price={result['target_price']} / "
                    f"stock={result['current_stock']}->{result['target_stock']} / "
                    f"{result['reason']}"
                )
        except Exception as e:
            errors += 1
            skipped += 1
            if verbose:
                if result is None:
                    store_code_value = row[1]
                    asin_value = row[10]
                    item_code_value = row[11] or ""
                    sku_code_value = row[12] or ""
                else:
                    store_code_value = result["store_code"]
                    asin_value = result["asin"]
                    item_code_value = result["mall_item_code"] or ""
                    sku_code_value = result["sku_code"] or ""
                print(
                    f"ERROR / {store_code_value} / {asin_value} / "
                    f"Item={item_code_value} / SKU={sku_code_value} / {e}"
                )

    if dry_run:
        conn.rollback()
    else:
        conn.commit()

    if verbose:
        print("")
        print(f"calculation summary: updated={updated}, skipped={skipped}, errors={errors}")

    return {
        "rows": len(rows),
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "targets": targets,
    }


def recalc_targets_for_asins(
    conn,
    store_code: str,
    asins: list[str],
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    return recalc_targets(
        conn,
        store_code=store_code,
        asins=asins,
        dry_run=dry_run,
        verbose=verbose,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate target_price / target_stock")
    parser.add_argument("--store", default="", help="Store code such as rakuten_1")
    parser.add_argument("--asin", default="", help="Recalculate a single ASIN")
    parser.add_argument("--asin-list", default="", help="Recalculate comma-separated ASINs")
    parser.add_argument("--dry-run", action="store_true", help="Show result without updating DB")
    args = parser.parse_args()

    store_code = args.store.strip() or None
    asins = parse_asin_args(args.asin, args.asin_list)

    conn = connect_db()

    try:
        result = recalc_targets(conn, store_code=store_code, asins=asins, dry_run=args.dry_run, verbose=True)
        if result["rows"] == 0:
            print("No store_products found for calculation.")
            return 0
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
