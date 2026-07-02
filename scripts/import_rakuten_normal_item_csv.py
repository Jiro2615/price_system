import argparse
import csv
from pathlib import Path

from db_config import connect_db




def clean(value: Any) -> str:
    return str(value or "").strip()


def to_int(value: Any, default: int | None = None) -> int | None:
    s = clean(value).replace(",", "")
    if s == "":
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def read_csv_with_fallback(path: Path):
    """
    楽天CSVは基本Shift-JIS/CP932想定。
    文字化けやBOM対策で複数候補を試す。
    """
    encodings = ["cp932", "utf-8-sig", "utf-8"]

    last_error = None
    for enc in encodings:
        try:
            f = path.open("r", encoding=enc, newline="")
            # 先頭だけ読んで成功確認
            f.peek if False else None
            return f, enc
        except Exception as e:
            last_error = e

    raise RuntimeError(f"CSVを開けませんでした: {path} / {last_error}")


def get_col(row: dict[str, Any], *names: str) -> str:
    """
    列名揺れ対策。
    """
    for name in names:
        if name in row:
            return clean(row.get(name))
    return ""


def parse_rakuten_csv(path: Path) -> list[dict[str, Any]]:
    f, enc = read_csv_with_fallback(path)
    print(f"CSV encoding: {enc}")

    products: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    with f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise RuntimeError("CSVヘッダーが見つかりません。")

        print("検出ヘッダー:")
        for h in reader.fieldnames:
            print(f"  {h}")

        for row_no, row in enumerate(reader, start=2):
            manage_number = get_col(
                row,
                "商品管理番号（商品URL）",
                "商品管理番号",
                "商品URL",
            )

            if not manage_number:
                continue

            item_name = get_col(row, "商品名")
            item_number = get_col(row, "商品番号")
            warehouse = get_col(row, "倉庫指定")
            search_visible = get_col(row, "サーチ表示")
            genre_id = get_col(row, "ジャンルID")

            sku_code = get_col(row, "SKU管理番号")
            system_sku = get_col(row, "システム連携用SKU番号")
            price = get_col(row, "通常購入販売価格")
            stock = get_col(row, "在庫数")
            sku_warehouse = get_col(row, "SKU倉庫指定")

            # 商品行っぽいものを保存
            if item_name:
                products[manage_number] = {
                    "manage_number": manage_number,
                    "item_number": item_number,
                    "item_name": item_name,
                    "warehouse": warehouse,
                    "search_visible": search_visible,
                    "genre_id": genre_id,
                }

            # SKU行判定
            # 価格 or 在庫 or SKU管理番号がある行をSKU行として扱う
            is_sku_row = bool(sku_code or price or stock)

            if not is_sku_row:
                continue

            product = products.get(manage_number, {})

            # 多くの商品は商品管理番号=SKU管理番号。
            # SKU管理番号が空なら商品管理番号を使う。
            if not sku_code:
                sku_code = manage_number

            item = {
                "row_no": row_no,
                "manage_number": manage_number,
                "sku_code": sku_code,
                "system_sku": system_sku,
                "item_number": product.get("item_number") or item_number,
                "item_name": product.get("item_name") or item_name,
                "warehouse": product.get("warehouse") or warehouse,
                "search_visible": product.get("search_visible") or search_visible,
                "genre_id": product.get("genre_id") or genre_id,
                "current_price": to_int(price),
                "current_stock": to_int(stock, 0),
                "sku_warehouse": sku_warehouse,
            }

            results.append(item)

    return results


def get_store_id(conn, store_code: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM stores
            WHERE mall = 'rakuten'
              AND store_code = %s
            """,
            (store_code,),
        )
        row = cur.fetchone()

    if not row:
        raise RuntimeError(f"楽天店舗が見つかりません: {store_code}")

    return int(row[0])


def upsert_store_product(conn, store_id: int, item: dict[str, Any]) -> str:
    """
    mall_item_code + sku_code で既存行を探して、あればUPDATE、なければINSERT。
    ASINは対応表で後から入れるのでここでは触らない。
    """
    manage_number = item["manage_number"]
    sku_code = item["sku_code"]

    current_status = "warehouse" if item.get("warehouse") == "1" else "synced"

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE store_products
            SET
                mall_item_code = %s,
                sku_code = %s,
                item_name = %s,
                current_price = %s,
                current_stock = %s,
                current_status = %s,
                api_last_synced_at = CURRENT_TIMESTAMP,
                api_last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE store_id = %s
              AND mall_item_code = %s
              AND COALESCE(sku_code, '') = COALESCE(%s, '')
            """,
            (
                manage_number,
                sku_code,
                item.get("item_name") or "",
                item.get("current_price"),
                item.get("current_stock"),
                current_status,
                store_id,
                manage_number,
                sku_code,
            ),
        )

        if cur.rowcount > 0:
            return "updated"

        cur.execute(
            """
            INSERT INTO store_products (
                store_id,
                asin,
                mall_item_code,
                sku_code,
                item_name,
                current_price,
                current_stock,
                current_status,
                enabled,
                force_stop,
                no_price_change,
                api_last_synced_at
            )
            VALUES (
                %s,
                NULL,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                TRUE,
                FALSE,
                FALSE,
                CURRENT_TIMESTAMP
            )
            """,
            (
                store_id,
                manage_number,
                sku_code,
                item.get("item_name") or "",
                item.get("current_price"),
                item.get("current_stock"),
                current_status,
            ),
        )

        return "inserted"


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天DL商品CSVをstore_productsへ取り込みます。")
    parser.add_argument("--csv", required=True, help="楽天DL CSVパス")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--limit", type=int, default=0, help="テスト用。0なら全件")
    parser.add_argument("--dry-run", action="store_true", help="DB更新せず件数確認のみ")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise RuntimeError(f"CSVが見つかりません: {csv_path}")

    items = parse_rakuten_csv(csv_path)

    if args.limit and args.limit > 0:
        items = items[: args.limit]

    print("")
    print("解析結果")
    print(f"  SKU行数: {len(items)}")

    if not items:
        print("取り込み対象がありません。")
        return 0

    print("")
    print("先頭5件:")
    for item in items[:5]:
        print(
            f"  {item['manage_number']} / {item['sku_code']} / "
            f"price={item['current_price']} / stock={item['current_stock']} / "
            f"name={item['item_name'][:40]}"
        )

    if args.dry_run:
        print("")
        print("dry-run のためDB更新しません。")
        return 0

    conn = connect_db()

    inserted = 0
    updated = 0
    errors = 0

    try:
        store_id = get_store_id(conn, args.store)

        for idx, item in enumerate(items, start=1):
            try:
                result = upsert_store_product(conn, store_id, item)

                if result == "inserted":
                    inserted += 1
                else:
                    updated += 1

                if idx % 1000 == 0:
                    conn.commit()
                    print(f"{idx}/{len(items)} 件処理中... inserted={inserted}, updated={updated}, errors={errors}")

            except Exception as e:
                errors += 1
                print(f"エラー row={item.get('row_no')} manage={item.get('manage_number')} sku={item.get('sku_code')}: {e}")

        conn.commit()

    finally:
        conn.close()

    print("")
    print("取り込み完了")
    print(f"  inserted: {inserted}")
    print(f"  updated : {updated}")
    print(f"  errors  : {errors}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())