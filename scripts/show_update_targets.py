import argparse
import csv
from pathlib import Path

from db_config import connect_db


def to_int_or_none(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def needs_update(current_price, current_stock, target_price, target_stock) -> bool:
    cp = to_int_or_none(current_price)
    cs = to_int_or_none(current_stock)
    tp = to_int_or_none(target_price)
    ts = to_int_or_none(target_stock)

    # target_price が None の場合は、価格更新はしない。
    # ただし target_stock は比較する。
    price_changed = tp is not None and cp != tp
    stock_changed = ts is not None and cs != ts

    return price_changed or stock_changed


def fetch_update_targets(mall: str | None, store_code: str | None, limit: int):
    where = [
        "sp.enabled = TRUE",
        """
        (
            (sp.target_price IS NOT NULL AND COALESCE(sp.current_price, -1) <> sp.target_price)
            OR
            (sp.target_stock IS NOT NULL AND COALESCE(sp.current_stock, -999999) <> sp.target_stock)
        )
        """
    ]
    params = []

    if mall:
        where.append("s.mall = %s")
        params.append(mall)

    if store_code:
        where.append("s.store_code = %s")
        params.append(store_code)

    sql = f"""
        SELECT
            s.mall,
            s.store_code,
            sp.id AS store_product_id,
            sp.asin,
            sp.mall_item_code,
            sp.sku_code,
            sp.current_price,
            sp.target_price,
            sp.current_stock,
            sp.target_stock,
            sp.force_stop,
            ap.amazon_price,
            ap.amazon_point,
            ap.available_qty,
            ap.business_ng,
            ap.system_error,
            ap.ng_reason,
            ap.checked_at
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        JOIN amazon_products ap ON ap.asin = sp.asin
        WHERE {" AND ".join(where)}
        ORDER BY s.mall, s.store_code, sp.id
        LIMIT %s;
    """

    params.append(limit)

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def print_targets(rows):
    if not rows:
        print("更新対象はありません。")
        return

    print("")
    print("===== 更新対象 =====")
    print("")

    for row in rows:
        (
            mall,
            store_code,
            store_product_id,
            asin,
            mall_item_code,
            sku_code,
            current_price,
            target_price,
            current_stock,
            target_stock,
            force_stop,
            amazon_price,
            amazon_point,
            available_qty,
            business_ng,
            system_error,
            ng_reason,
            checked_at,
        ) = row

        price_mark = ""
        stock_mark = ""

        if target_price is not None and current_price != target_price:
            price_mark = "価格変更"

        if target_stock is not None and current_stock != target_stock:
            stock_mark = "在庫変更"

        marks = " / ".join([m for m in [price_mark, stock_mark] if m])

        print(
            f"[{mall}:{store_code}] "
            f"ASIN={asin} "
            f"Item={mall_item_code or ''} "
            f"SKU={sku_code or ''} "
            f"{marks}"
        )
        print(f"  price: {current_price} -> {target_price}")
        print(f"  stock: {current_stock} -> {target_stock}")
        print(f"  amazon: price={amazon_price}, point={amazon_point}, qty={available_qty}")
        print(f"  ng: business={business_ng}, system={system_error}, reason={ng_reason or ''}")
        print(f"  checked_at: {checked_at}")
        print("")


def export_csv(rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "mall",
        "store_code",
        "store_product_id",
        "asin",
        "mall_item_code",
        "sku_code",
        "current_price",
        "target_price",
        "current_stock",
        "target_stock",
        "force_stop",
        "amazon_price",
        "amazon_point",
        "available_qty",
        "business_ng",
        "system_error",
        "ng_reason",
        "checked_at",
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"CSV出力しました: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="モール更新が必要な商品を表示します。")
    parser.add_argument("--mall", default="", help="qoo10 / rakuten など。空なら全モール")
    parser.add_argument("--store", default="", help="qoo10_1 / rakuten_1 など。空なら全店舗")
    parser.add_argument("--limit", type=int, default=100, help="表示する最大件数")
    parser.add_argument("--csv", default="", help="CSV出力先パス。指定時のみ出力")
    args = parser.parse_args()

    mall = args.mall.strip() or None
    store_code = args.store.strip() or None

    rows = fetch_update_targets(
        mall=mall,
        store_code=store_code,
        limit=args.limit,
    )

    print_targets(rows)

    print(f"更新対象件数: {len(rows)}")

    if args.csv:
        export_csv(rows, Path(args.csv))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
