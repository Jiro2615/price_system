import argparse
import csv
from pathlib import Path
from typing import Any

import psycopg


DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "price_system"
DB_USER = "price_app"
DB_PASSWORD = "price_app_2026"  # 自分の price_app パスワードに合わせる


def clean(value: Any) -> str:
    return str(value or "").strip()


def is_asin(value: str) -> bool:
    value = clean(value).upper()
    return len(value) == 10 and value.isalnum()


def get_col(row: dict[str, Any], *names: str) -> str:
    for name in names:
        if name in row:
            return clean(row.get(name))
    return ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    encodings = ["cp932", "utf-8-sig", "utf-8"]

    last_error = None

    for enc in encodings:
        try:
            with path.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames:
                    raise RuntimeError("CSVヘッダーが見つかりません。")

                print(f"CSV encoding: {enc}")
                print("検出ヘッダー:")
                for h in reader.fieldnames:
                    print(f"  {h}")

                rows = []
                for row_no, row in enumerate(reader, start=2):
                    manage_number = get_col(
                        row,
                        "楽天商品管理番号",
                        "商品管理番号",
                        "商品管理番号（商品URL）",
                        "商品URL",
                    )

                    asin = get_col(
                        row,
                        "ASIN",
                        "asin",
                    ).upper()

                    if not manage_number and not asin:
                        continue

                    rows.append({
                        "row_no": str(row_no),
                        "manage_number": manage_number,
                        "asin": asin,
                    })

                return rows

        except UnicodeDecodeError as e:
            last_error = e
            continue

    raise RuntimeError(f"CSVを開けませんでした: {path} / {last_error}")


def import_asin_map(path: Path, store_code: str, limit: int, dry_run: bool) -> None:
    rows = read_csv_rows(path)

    if limit > 0:
        rows = rows[:limit]

    print("")
    print("解析結果")
    print(f"  行数: {len(rows)}")

    valid_rows = []
    invalid_rows = []

    for row in rows:
        manage_number = row["manage_number"]
        asin = row["asin"]

        if not manage_number or not is_asin(asin):
            invalid_rows.append(row)
            continue

        valid_rows.append(row)

    print(f"  有効行: {len(valid_rows)}")
    print(f"  無効行: {len(invalid_rows)}")

    print("")
    print("先頭5件:")
    for row in valid_rows[:5]:
        print(f"  {row['manage_number']} -> {row['asin']}")

    if dry_run:
        print("")
        print("dry-run のためDB更新しません。")
        return

    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    inserted_amazon = 0
    updated_store = 0
    not_found_store = 0
    errors = 0

    try:
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
            store = cur.fetchone()
            if not store:
                raise RuntimeError(f"楽天店舗が見つかりません: {store_code}")

            store_id = int(store[0])

        for idx, row in enumerate(valid_rows, start=1):
            manage_number = row["manage_number"]
            asin = row["asin"]

            try:
                with conn.cursor() as cur:
                    # 外部キー制約があるので、先にamazon_productsへASINを登録する
                    cur.execute(
                        """
                        INSERT INTO amazon_products (
                            asin,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            %s,
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (asin) DO NOTHING
                        """,
                        (asin,),
                    )

                    if cur.rowcount > 0:
                        inserted_amazon += 1

                    # 楽天商品管理番号に一致するstore_productsへASINを紐付け
                    cur.execute(
                        """
                        UPDATE store_products
                        SET
                            asin = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE store_id = %s
                          AND mall_item_code = %s
                        """,
                        (
                            asin,
                            store_id,
                            manage_number,
                        ),
                    )

                    if cur.rowcount > 0:
                        updated_store += cur.rowcount
                    else:
                        not_found_store += 1

                if idx % 1000 == 0:
                    conn.commit()
                    print(
                        f"{idx}/{len(valid_rows)} 件処理中... "
                        f"amazon_inserted={inserted_amazon}, "
                        f"store_updated={updated_store}, "
                        f"store_not_found={not_found_store}, "
                        f"errors={errors}"
                    )

            except Exception as e:
                errors += 1
                print(f"エラー row={row.get('row_no')} manage={manage_number} asin={asin}: {e}")

        conn.commit()

    finally:
        conn.close()

    print("")
    print("ASIN紐付け取り込み完了")
    print(f"  amazon_products 新規ASIN: {inserted_amazon}")
    print(f"  store_products 更新行数 : {updated_store}")
    print(f"  store_products 未一致   : {not_found_store}")
    print(f"  errors                 : {errors}")


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天商品管理番号とASINの対応表をDBへ取り込みます。")
    parser.add_argument("--csv", required=True, help="楽天商品管理番号,ASIN のCSVパス")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--limit", type=int, default=0, help="テスト用。0なら全件")
    parser.add_argument("--dry-run", action="store_true", help="DB更新せず確認のみ")
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise RuntimeError(f"CSVが見つかりません: {path}")

    import_asin_map(
        path=path,
        store_code=args.store,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())