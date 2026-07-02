import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from db_config import connect_db


PRICE_HEADERS = [
    "通常購入販売価格",
    "販売価格",
    "価格",
]

STOCK_HEADERS = [
    "在庫数",
]


def clean(value: Any) -> str:
    return str(value or "").strip()


def to_int(value: Any, default: int | None = None) -> int | None:
    s = clean(value).replace(",", "").replace("￥", "").replace("\\", "").replace("円", "")
    if not s:
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def read_csv_with_fallback(path: Path) -> tuple[list[dict[str, str]], str]:
    """
    楽天 normal-item.csv は基本 CP932/Shift-JIS。
    念のため UTF-8 系も読む。
    """
    encodings = ["cp932", "utf-8-sig", "utf-8"]
    last_error: Exception | None = None

    for enc in encodings:
        try:
            with path.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise RuntimeError("CSVヘッダーが見つかりません。")

                rows = []
                for row in reader:
                    rows.append({clean(k): clean(v) for k, v in row.items() if k is not None})

                return rows, enc

        except UnicodeDecodeError as e:
            last_error = e
            continue

    raise RuntimeError(f"CSVを読めませんでした: {path} / {last_error}")


def get_col(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row:
            return clean(row.get(name))
    return ""


def first_existing_int(row: dict[str, str], names: list[str]) -> int | None:
    for name in names:
        if name in row:
            value = to_int(row.get(name))
            if value is not None:
                return value
    return None


def parse_normal_item_csv(path: Path, include_stock: bool) -> tuple[list[dict[str, Any]], str]:
    rows, enc = read_csv_with_fallback(path)

    targets: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        manage_number = get_col(row, "商品管理番号（商品URL）", "商品管理番号", "商品URL")
        option_type = get_col(row, "選択肢タイプ")
        sku_code = get_col(row, "SKU管理番号", "SKU管理番号（SKU番号）")

        # 商品レベル行・商品オプション行はスキップ。
        # SKUレベル行だけ反映する。
        if not manage_number or not sku_code:
            continue

        if option_type:
            continue

        price = first_existing_int(row, PRICE_HEADERS)
        stock = first_existing_int(row, STOCK_HEADERS) if include_stock else None

        if price is None and stock is None:
            continue

        item = {
            "row_no": idx,
            "mall_item_code": manage_number,
            "sku_code": sku_code,
            "new_price": price,
            "new_stock": stock,
        }
        targets.append(item)

    return targets, enc


def fetch_current_rows(conn, store_code: str, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    with conn.cursor() as cur:
        for t in targets:
            cur.execute(
                """
                SELECT
                    sp.id,
                    s.store_code,
                    sp.asin,
                    sp.mall_item_code,
                    sp.sku_code,
                    sp.item_name,
                    sp.current_price,
                    sp.target_price,
                    sp.current_stock,
                    sp.target_stock
                FROM store_products sp
                JOIN stores s ON s.id = sp.store_id
                WHERE s.mall = 'rakuten'
                  AND s.store_code = %s
                  AND sp.mall_item_code = %s
                  AND COALESCE(sp.sku_code, '') = COALESCE(%s, '')
                """,
                (
                    store_code,
                    t["mall_item_code"],
                    t["sku_code"],
                ),
            )
            row = cur.fetchone()
            if not row:
                results.append({
                    **t,
                    "found": False,
                    "error": "store_products に該当行なし",
                })
                continue

            (
                store_product_id,
                found_store_code,
                asin,
                mall_item_code,
                sku_code,
                item_name,
                current_price,
                target_price,
                current_stock,
                target_stock,
            ) = row

            results.append({
                **t,
                "found": True,
                "store_product_id": store_product_id,
                "store_code": found_store_code,
                "asin": asin,
                "item_name": item_name,
                "current_price": current_price,
                "target_price": target_price,
                "current_stock": current_stock,
                "target_stock": target_stock,
            })

    return results


def get_existing_columns(conn, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        return {r[0] for r in cur.fetchall()}


def insert_price_update_log_if_possible(
    conn,
    *,
    row: dict[str, Any],
    status: str,
    message: str,
    update_type: str,
) -> None:
    """
    price_update_logs の列構成が未確定でも落ちないように、
    存在する列だけにINSERTする。
    ログ挿入失敗で本体更新を止めない。
    """
    try:
        columns = get_existing_columns(conn, "price_update_logs")
        if not columns:
            return

        candidates: dict[str, Any] = {
            "store_product_id": row.get("store_product_id"),
            "asin": row.get("asin"),
            "mall_item_code": row.get("mall_item_code"),
            "sku_code": row.get("sku_code"),
            "old_price": row.get("current_price"),
            "new_price": row.get("new_price"),
            "old_stock": row.get("current_stock"),
            "new_stock": row.get("new_stock"),
            "status": status,
            "result": status,
            "message": message,
            "error_message": None if status == "success" else message,
            "update_type": update_type,
            "api_name": "rakuten_csv_normal_item",
            "request_json": json.dumps({
                "mall_item_code": row.get("mall_item_code"),
                "sku_code": row.get("sku_code"),
                "new_price": row.get("new_price"),
                "new_stock": row.get("new_stock"),
            }, ensure_ascii=False),
            "response_json": json.dumps({
                "source": "normal-item.csv",
                "status": status,
                "message": message,
            }, ensure_ascii=False),
        }

        insert_cols = []
        values = []

        for col, value in candidates.items():
            if col in columns:
                insert_cols.append(col)
                values.append(value)

        # created_at / updated_at 系があればCURRENT_TIMESTAMPで入れる
        timestamp_cols = []
        for col in ["created_at", "updated_at", "logged_at"]:
            if col in columns:
                timestamp_cols.append(col)

        if not insert_cols and not timestamp_cols:
            return

        col_sql = insert_cols + timestamp_cols
        placeholders = ["%s"] * len(insert_cols) + ["CURRENT_TIMESTAMP"] * len(timestamp_cols)

        sql = f"""
            INSERT INTO price_update_logs ({", ".join(col_sql)})
            VALUES ({", ".join(placeholders)})
        """

        with conn.cursor() as cur:
            cur.execute(sql, values)

    except Exception as e:
        print(f"注意: price_update_logs への書き込みをスキップしました: {e}")


def apply_updates(
    conn,
    rows: list[dict[str, Any]],
    include_stock: bool,
    execute: bool,
) -> tuple[int, int]:
    updated = 0
    skipped = 0

    with conn.cursor() as cur:
        for row in rows:
            if not row.get("found"):
                skipped += 1
                print(
                    f"SKIP row={row.get('row_no')} "
                    f"Item={row.get('mall_item_code')} SKU={row.get('sku_code')} / {row.get('error')}"
                )
                continue

            new_price = row.get("new_price")
            new_stock = row.get("new_stock") if include_stock else None

            if new_price is None and new_stock is None:
                skipped += 1
                print(
                    f"SKIP id={row.get('store_product_id')} "
                    f"Item={row.get('mall_item_code')} SKU={row.get('sku_code')} / 反映値なし"
                )
                continue

            if execute:
                if include_stock and new_stock is not None:
                    cur.execute(
                        """
                        UPDATE store_products
                        SET
                            current_price = COALESCE(%s, current_price),
                            current_stock = COALESCE(%s, current_stock),
                            api_last_synced_at = CURRENT_TIMESTAMP,
                            api_last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            new_price,
                            new_stock,
                            row["store_product_id"],
                        ),
                    )
                    update_type = "csv_price_stock"
                else:
                    cur.execute(
                        """
                        UPDATE store_products
                        SET
                            current_price = COALESCE(%s, current_price),
                            api_last_synced_at = CURRENT_TIMESTAMP,
                            api_last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            new_price,
                            row["store_product_id"],
                        ),
                    )
                    update_type = "csv_price"

                insert_price_update_log_if_possible(
                    conn,
                    row=row,
                    status="success",
                    message="normal-item.csv 成功確認後にDBへ反映",
                    update_type=update_type,
                )

            updated += 1

            print(
                f"{'UPDATE' if execute else 'DRY'} "
                f"id={row.get('store_product_id')} "
                f"ASIN={row.get('asin')} "
                f"Item={row.get('mall_item_code')} SKU={row.get('sku_code')}"
            )
            print(f"  price: {row.get('current_price')} -> {new_price}")
            if include_stock and new_stock is not None:
                print(f"  stock: {row.get('current_stock')} -> {new_stock}")
            print(f"  name : {str(row.get('item_name') or '')[:80]}")

    return updated, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天 normal-item.csv の成功反映としてDBの current_price/current_stock を更新します。")
    parser.add_argument("--csv", required=True, help="楽天へアップロードして成功確認済みの normal-item CSV")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--include-stock", action="store_true", help="CSVの在庫数も current_stock へ反映する")
    parser.add_argument("--execute", action="store_true", help="実際にDB更新する。未指定ならdry-run")
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise RuntimeError(f"CSVが見つかりません: {path}")

    targets, enc = parse_normal_item_csv(path, include_stock=args.include_stock)

    print(f"CSV encoding: {enc}")
    print(f"SKU反映候補件数: {len(targets)}")
    print("")

    if not targets:
        print("反映対象がありません。")
        return 0

    conn = connect_db()

    try:
        rows = fetch_current_rows(conn, args.store, targets)

        print("===== DB反映プレビュー =====")
        print("")

        updated, skipped = apply_updates(
            conn=conn,
            rows=rows,
            include_stock=args.include_stock,
            execute=args.execute,
        )

        print("")
        if args.execute:
            conn.commit()
            print("DB反映完了")
        else:
            conn.rollback()
            print("dry-run のためDB更新していません。実行する場合は --execute を付けてください。")

        print(f"反映対象: {updated}")
        print(f"スキップ: {skipped}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
