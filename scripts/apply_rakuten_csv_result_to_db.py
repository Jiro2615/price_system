import argparse
import csv
import re
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


def read_text_fallback(path: Path) -> tuple[str, str]:
    encodings = ["cp932", "utf-8-sig", "utf-8"]
    last_error = None
    for enc in encodings:
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError as e:
            last_error = e
    raise RuntimeError(f"ファイルを読めませんでした: {path} / {last_error}")


def read_csv_dict_fallback(path: Path) -> tuple[list[dict[str, str]], str]:
    encodings = ["cp932", "utf-8-sig", "utf-8"]
    last_error = None

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

    raise RuntimeError(f"CSVを読めませんでした: {path} / {last_error}")


def read_csv_rows_fallback(path: Path) -> tuple[list[list[str]], str]:
    encodings = ["cp932", "utf-8-sig", "utf-8"]
    last_error = None

    for enc in encodings:
        try:
            with path.open("r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                rows = [[clean(c) for c in row] for row in reader]
                return rows, enc
        except UnicodeDecodeError as e:
            last_error = e

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
    rows, enc = read_csv_dict_fallback(path)

    targets: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        manage_number = get_col(row, "商品管理番号（商品URL）", "商品管理番号", "商品URL")
        option_type = get_col(row, "選択肢タイプ")
        sku_code = get_col(row, "SKU管理番号", "SKU管理番号（SKU番号）")

        # 商品レベル行・商品オプション行はスキップ。SKUレベル行だけ反映対象。
        if not manage_number or not sku_code:
            continue
        if option_type:
            continue

        price = first_existing_int(row, PRICE_HEADERS)
        stock = first_existing_int(row, STOCK_HEADERS) if include_stock else None

        if price is None and stock is None:
            continue

        targets.append({
            "row_no": idx,
            "mall_item_code": manage_number,
            "sku_code": sku_code,
            "new_price": price,
            "new_stock": stock,
        })

    return targets, enc


def parse_error_log(path: Path) -> tuple[dict[tuple[str, str], str], set[str], str]:
    """
    楽天CSVエラーログを読む。
    典型:
      商品管理番号,エラーメッセージ,SKU管理番号

    SKUが取れない場合は商品管理番号単位でブロックする。
    """
    rows, enc = read_csv_rows_fallback(path)

    errors_by_pair: dict[tuple[str, str], str] = {}
    errors_by_manage: set[str] = set()

    sku_re = re.compile(r"SKU管理番号[:：]([^、。\s]+)")

    for row in rows:
        if not row or len(row) < 1:
            continue

        # ヘッダーっぽいものはスキップ
        if any("商品管理番号" == c or "エラー" == c for c in row):
            continue

        manage_number = clean(row[0])
        if not manage_number:
            continue

        message = clean(row[1]) if len(row) >= 2 else ""
        sku_code = clean(row[2]) if len(row) >= 3 else ""

        if not sku_code and message:
            m = sku_re.search(message)
            if m:
                sku_code = clean(m.group(1))

        if sku_code:
            errors_by_pair[(manage_number, sku_code)] = message
        else:
            errors_by_manage.add(manage_number)

    return errors_by_pair, errors_by_manage, enc


def ensure_columns(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            ALTER TABLE store_products
            ADD COLUMN IF NOT EXISTS rakuten_csv_update_blocked BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS rakuten_csv_update_error TEXT,
            ADD COLUMN IF NOT EXISTS rakuten_csv_update_error_at TIMESTAMP;
            """
        )


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
                    sp.target_stock,
                    sp.rakuten_csv_update_blocked
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
                blocked,
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
                "blocked_before": blocked,
            })

    return results


def apply_result(
    conn,
    *,
    store_code: str,
    targets: list[dict[str, Any]],
    errors_by_pair: dict[tuple[str, str], str],
    errors_by_manage: set[str],
    include_stock: bool,
    execute: bool,
    apply_successes: bool,
    mark_blocked: bool,
) -> tuple[int, int, int]:
    rows = fetch_current_rows(conn, store_code, targets)

    success_count = 0
    error_count = 0
    missing_count = 0

    with conn.cursor() as cur:
        for row in rows:
            manage = row["mall_item_code"]
            sku = row["sku_code"]
            pair = (manage, sku)

            is_error = pair in errors_by_pair or manage in errors_by_manage
            error_message = errors_by_pair.get(pair) or ("商品単位エラー" if manage in errors_by_manage else "")

            if not row.get("found"):
                missing_count += 1
                print(f"MISS Item={manage} SKU={sku} / {row.get('error')}")
                continue

            if is_error:
                error_count += 1
                print(f"ERROR id={row.get('store_product_id')} Item={manage} SKU={sku}")
                print(f"  {error_message}")

                if execute and mark_blocked:
                    cur.execute(
                        """
                        UPDATE store_products
                        SET
                            rakuten_csv_update_blocked = TRUE,
                            rakuten_csv_update_error = %s,
                            rakuten_csv_update_error_at = CURRENT_TIMESTAMP,
                            api_last_error = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            error_message,
                            error_message,
                            row["store_product_id"],
                        ),
                    )
                continue

            success_count += 1
            print(f"SUCCESS id={row.get('store_product_id')} Item={manage} SKU={sku}")
            print(f"  price: {row.get('current_price')} -> {row.get('new_price')}")
            if include_stock and row.get("new_stock") is not None:
                print(f"  stock: {row.get('current_stock')} -> {row.get('new_stock')}")

            if execute and apply_successes:
                if include_stock and row.get("new_stock") is not None:
                    cur.execute(
                        """
                        UPDATE store_products
                        SET
                            current_price = COALESCE(%s, current_price),
                            current_stock = COALESCE(%s, current_stock),
                            rakuten_csv_update_blocked = FALSE,
                            rakuten_csv_update_error = NULL,
                            rakuten_csv_update_error_at = NULL,
                            api_last_synced_at = CURRENT_TIMESTAMP,
                            api_last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            row.get("new_price"),
                            row.get("new_stock"),
                            row["store_product_id"],
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE store_products
                        SET
                            current_price = COALESCE(%s, current_price),
                            rakuten_csv_update_blocked = FALSE,
                            rakuten_csv_update_error = NULL,
                            rakuten_csv_update_error_at = NULL,
                            api_last_synced_at = CURRENT_TIMESTAMP,
                            api_last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            row.get("new_price"),
                            row["store_product_id"],
                        ),
                    )

    return success_count, error_count, missing_count


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天CSV処理結果ログをもとに、成功分DB反映・エラー商品blocked化を行います。")
    parser.add_argument("--csv", required=True, help="楽天へアップロードした normal-item CSV")
    parser.add_argument("--log", required=True, help="楽天が出力したエラーログCSV")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--include-stock", action="store_true", help="CSVの在庫数も current_stock へ反映する")
    parser.add_argument("--execute", action="store_true", help="実際にDB更新する。未指定ならdry-run")
    parser.add_argument("--no-apply-successes", action="store_true", help="成功分の current_price/current_stock 反映をしない")
    parser.add_argument("--no-mark-blocked", action="store_true", help="エラー商品のblocked化をしない")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    log_path = Path(args.log)

    if not csv_path.exists():
        raise RuntimeError(f"CSVが見つかりません: {csv_path}")
    if not log_path.exists():
        raise RuntimeError(f"ログが見つかりません: {log_path}")

    targets, csv_enc = parse_normal_item_csv(csv_path, include_stock=args.include_stock)
    errors_by_pair, errors_by_manage, log_enc = parse_error_log(log_path)

    print(f"CSV encoding : {csv_enc}")
    print(f"LOG encoding : {log_enc}")
    print(f"CSV SKU件数  : {len(targets)}")
    print(f"エラーSKU件数: {len(errors_by_pair)}")
    print(f"商品単位エラー: {len(errors_by_manage)}")
    print("")

    conn = connect_db()
    try:
        ensure_columns(conn)

        success_count, error_count, missing_count = apply_result(
            conn,
            store_code=args.store,
            targets=targets,
            errors_by_pair=errors_by_pair,
            errors_by_manage=errors_by_manage,
            include_stock=args.include_stock,
            execute=args.execute,
            apply_successes=not args.no_apply_successes,
            mark_blocked=not args.no_mark_blocked,
        )

        print("")
        if args.execute:
            conn.commit()
            print("DB更新完了")
        else:
            conn.rollback()
            print("dry-run のためDB更新していません。実行する場合は --execute を付けてください。")

        print("")
        print("===== 集計 =====")
        print(f"成功扱い: {success_count}")
        print(f"エラー扱い: {error_count}")
        print(f"DB未検出: {missing_count}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
