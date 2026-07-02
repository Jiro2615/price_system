import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg


DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "price_system"
DB_USER = "price_app"
DB_PASSWORD = "price_app_2026"

BASE_DIR = Path(r"C:\price_system")
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_csv"


HEADERS_PRICE = [
    "商品管理番号（商品URL）",
    "選択肢タイプ",
    "SKU管理番号",
    "通常購入販売価格",
]

HEADERS_PRICE_STOCK = [
    "商品管理番号（商品URL）",
    "選択肢タイプ",
    "SKU管理番号",
    "通常購入販売価格",
    "在庫数",
]


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        s = str(value).replace(",", "").strip()
        if not s:
            return default
        return int(float(s))
    except Exception:
        return default


def fetch_rows(store_code: str, limit: int, include_stock: bool) -> list[dict[str, Any]]:
    where = [
        "s.mall = 'rakuten'",
        "s.store_code = %s",
        "sp.enabled = TRUE",
        "sp.mall_item_code IS NOT NULL",
        "sp.sku_code IS NOT NULL",
        "sp.current_price IS NOT NULL",
        "sp.current_price > 0",
    ]
    params: list[Any] = [store_code]

    sql = f"""
        SELECT
            sp.id AS store_product_id,
            sp.asin,
            sp.mall_item_code,
            sp.sku_code,
            sp.item_name,
            sp.current_price,
            sp.current_stock
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        WHERE {" AND ".join(where)}
        ORDER BY sp.id
        LIMIT %s
    """
    params.append(limit)

    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [desc.name for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def write_csv(path: Path, rows: list[dict[str, Any]], include_product_rows: bool, include_stock: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = HEADERS_PRICE_STOCK if include_stock else HEADERS_PRICE

    with path.open("w", encoding="cp932", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            manage_number = str(row["mall_item_code"]).strip()
            sku_code = str(row["sku_code"]).strip()
            current_price = to_int(row["current_price"])
            current_stock = to_int(row.get("current_stock"), 0)

            if include_product_rows:
                if include_stock:
                    writer.writerow([manage_number, "", "", "", ""])
                else:
                    writer.writerow([manage_number, "", "", ""])

            if include_stock:
                writer.writerow([manage_number, "", sku_code, current_price, current_stock])
            else:
                writer.writerow([manage_number, "", sku_code, current_price])


def write_check_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "store_product_id",
        "ASIN",
        "商品管理番号",
        "SKU管理番号",
        "商品名",
        "現在価格",
        "現在在庫",
    ]

    with path.open("w", encoding="cp932", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            writer.writerow([
                row.get("store_product_id"),
                row.get("asin") or "",
                row.get("mall_item_code") or "",
                row.get("sku_code") or "",
                row.get("item_name") or "",
                row.get("current_price") if row.get("current_price") is not None else "",
                row.get("current_stock") if row.get("current_stock") is not None else "",
            ])


def print_preview(rows: list[dict[str, Any]], max_rows: int = 10) -> None:
    print("")
    print("===== no-op CSV出力対象プレビュー =====")
    print("")
    for row in rows[:max_rows]:
        print(
            f"[{row.get('store_product_id')}] "
            f"ASIN={row.get('asin')} "
            f"Item={row.get('mall_item_code')} "
            f"SKU={row.get('sku_code')}"
        )
        print(f"  price: {row.get('current_price')} -> {row.get('current_price')}  ※同額")
        print(f"  stock: {row.get('current_stock')}")
        print(f"  name : {str(row.get('item_name') or '')[:80]}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天CSV処理時間テスト用に、価格を変えない normal-item no-op CSV を出力します。")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--limit", type=int, default=100, help="出力SKU件数")
    parser.add_argument("--output", default="", help="CSV出力先。未指定なら自動生成")
    parser.add_argument("--check-output", default="", help="確認用CSV出力先。未指定なら自動生成")
    parser.add_argument("--sku-only", action="store_true", help="商品レベル行を出さず、SKUレベル行だけ出力する")
    parser.add_argument("--include-stock", action="store_true", help="在庫数も同額CSVに含める")
    parser.add_argument("--dry-run", action="store_true", help="CSVを書き出さず対象だけ表示")
    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit は1以上にしてください。")
        return 2

    rows = fetch_rows(
        store_code=args.store,
        limit=args.limit,
        include_stock=args.include_stock,
    )

    print_preview(rows)
    print(f"no-op CSV出力対象SKU件数: {len(rows)}")

    if args.dry_run:
        print("")
        print("dry-run のためCSVは出力しません。")
        return 0

    if not rows:
        print("出力対象がありません。")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_DIR / f"normal-item_noop_{timestamp}.csv"

    if args.check_output:
        check_path = Path(args.check_output)
    else:
        check_path = OUTPUT_DIR / f"normal-item_noop_check_{timestamp}.csv"

    write_csv(
        output_path,
        rows,
        include_product_rows=not args.sku_only,
        include_stock=args.include_stock,
    )
    write_check_csv(check_path, rows)

    print("")
    print("no-op CSV出力完了")
    print(f"  楽天アップロード用: {output_path}")
    print(f"  確認用CSV        : {check_path}")
    print("")
    print("このCSVは current_price と同じ価格を出すため、楽天側の処理時間検証用です。")
    print("販売価格を実質変更しない想定ですが、まずは少件数で確認してください。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
