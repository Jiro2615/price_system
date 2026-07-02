import argparse
import csv
from datetime import datetime
from pathlib import Path

from db_config import connect_db




def fetch_rakuten_update_targets(store_code: str | None, limit: int):
    where = [
        "s.mall = 'rakuten'",
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

    if store_code:
        where.append("s.store_code = %s")
        params.append(store_code)

    sql = f"""
        SELECT
            s.store_code,
            sp.id AS store_product_id,
            sp.asin,
            sp.mall_item_code,
            sp.sku_code,
            sp.current_price,
            sp.target_price,
            sp.current_stock,
            sp.target_stock,
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
        ORDER BY s.store_code, sp.id
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


def build_reason(current_price, target_price, current_stock, target_stock, business_ng, system_error, ng_reason):
    reasons = []

    if target_price is not None and current_price != target_price:
        reasons.append("価格変更")

    if target_stock is not None and current_stock != target_stock:
        reasons.append("在庫変更")

    if business_ng:
        reasons.append(f"業務NG:{ng_reason or ''}")

    if system_error:
        reasons.append(f"システムエラー:{ng_reason or ''}")

    return " / ".join(reasons)


def export_csv(rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "店舗コード",
        "store_product_id",
        "ASIN",
        "楽天商品管理番号",
        "楽天SKU管理番号",
        "現在価格",
        "更新予定価格",
        "現在在庫",
        "更新予定在庫",
        "Amazon価格",
        "Amazonポイント",
        "Amazon在庫数",
        "業務NG",
        "システムエラー",
        "NG理由",
        "Amazon確認日時",
        "更新理由",
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            (
                store_code,
                store_product_id,
                asin,
                mall_item_code,
                sku_code,
                current_price,
                target_price,
                current_stock,
                target_stock,
                amazon_price,
                amazon_point,
                available_qty,
                business_ng,
                system_error,
                ng_reason,
                checked_at,
            ) = row

            reason = build_reason(
                current_price=current_price,
                target_price=target_price,
                current_stock=current_stock,
                target_stock=target_stock,
                business_ng=business_ng,
                system_error=system_error,
                ng_reason=ng_reason,
            )

            writer.writerow([
                store_code,
                store_product_id,
                asin,
                mall_item_code or "",
                sku_code or "",
                current_price if current_price is not None else "",
                target_price if target_price is not None else "",
                current_stock if current_stock is not None else "",
                target_stock if target_stock is not None else "",
                amazon_price if amazon_price is not None else "",
                amazon_point if amazon_point is not None else "",
                available_qty if available_qty is not None else "",
                "1" if business_ng else "0",
                "1" if system_error else "0",
                ng_reason or "",
                checked_at or "",
                reason,
            ])


def print_rows(rows):
    if not rows:
        print("楽天更新対象はありません。")
        return

    print("")
    print("===== 楽天更新対象 =====")
    print("")

    for row in rows:
        (
            store_code,
            store_product_id,
            asin,
            mall_item_code,
            sku_code,
            current_price,
            target_price,
            current_stock,
            target_stock,
            amazon_price,
            amazon_point,
            available_qty,
            business_ng,
            system_error,
            ng_reason,
            checked_at,
        ) = row

        reason = build_reason(
            current_price=current_price,
            target_price=target_price,
            current_stock=current_stock,
            target_stock=target_stock,
            business_ng=business_ng,
            system_error=system_error,
            ng_reason=ng_reason,
        )

        print(f"[{store_code}] {asin}")
        print(f"  楽天商品管理番号: {mall_item_code or ''}")
        print(f"  楽天SKU管理番号 : {sku_code or ''}")
        print(f"  price: {current_price} -> {target_price}")
        print(f"  stock: {current_stock} -> {target_stock}")
        print(f"  amazon: price={amazon_price}, point={amazon_point}, qty={available_qty}")
        print(f"  reason: {reason}")
        print(f"  checked_at: {checked_at}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天の価格/在庫更新確認CSVを出力します。")
    parser.add_argument("--store", default="", help="rakuten_1 など。空なら楽天全店舗")
    parser.add_argument("--limit", type=int, default=1000, help="出力最大件数")
    parser.add_argument("--output", default="", help="出力CSVパス")
    args = parser.parse_args()

    store_code = args.store.strip() or None

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(r"C:\price_system\output") / f"rakuten_update_targets_{timestamp}.csv"

    rows = fetch_rakuten_update_targets(
        store_code=store_code,
        limit=args.limit,
    )

    print_rows(rows)
    print(f"楽天更新対象件数: {len(rows)}")

    export_csv(rows, output_path)
    print(f"CSV出力完了: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())