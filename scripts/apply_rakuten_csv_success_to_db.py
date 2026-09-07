import argparse
import csv
import json
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


BATCH_SIZE = 500


def fetch_current_rows(conn, store_code: str, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    with conn.cursor() as cur:
        for offset in range(0, len(targets), BATCH_SIZE):
            batch = targets[offset:offset + BATCH_SIZE]
            cur.execute("""
                SELECT sp.id, s.store_code, sp.asin, sp.mall_item_code, sp.sku_code,
                       sp.item_name, sp.current_price, sp.target_price, sp.current_stock, sp.target_stock
                FROM store_products sp JOIN stores s ON s.id=sp.store_id
                JOIN (SELECT DISTINCT * FROM unnest(%s::text[], %s::text[]) AS t(item,sku)) t
                  ON sp.mall_item_code=t.item AND COALESCE(sp.sku_code,'')=t.sku
                WHERE s.mall='rakuten' AND s.store_code=%s
                """, ([t['mall_item_code'] for t in batch], [t['sku_code'] or '' for t in batch], store_code))
            found = {}
            for row in cur.fetchall():
                key = (row[3], row[4] or '')
                if key in found:
                    raise ValueError(f"商品管理番号・SKUがDB内で重複しています: {key}")
                found[key] = dict(zip(('store_product_id','store_code','asin','mall_item_code','sku_code',
                                     'item_name','current_price','target_price','current_stock','target_stock'), row))
            for target in batch:
                row = found.get((target['mall_item_code'], target['sku_code'] or ''))
                results.append({**target, **(row or {}), 'found': row is not None})
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


def insert_batch_logs(conn, rows, columns, include_stock):
    if not columns or not rows:
        return
    records = []
    for row in rows:
        stock = row.get('new_stock') if include_stock else None
        record = {
            'store_product_id': row['store_product_id'], 'asin': row.get('asin'),
            'mall_item_code': row['mall_item_code'], 'sku_code': row['sku_code'],
            'old_price': row.get('current_price'), 'new_price': row.get('new_price'),
            'old_stock': row.get('current_stock'), 'new_stock': stock,
            'status': 'success', 'result': 'success',
            'message': 'normal-item.csv 成功確認後にDBへ反映', 'error_message': None,
            'update_type': 'csv_price_stock' if stock is not None else 'csv_price',
            'api_name': 'rakuten_csv_normal_item',
            'request_json': {'mall_item_code': row['mall_item_code'], 'sku_code': row['sku_code'],
                             'new_price': row.get('new_price'), 'new_stock': stock},
            'response_json': {'source': 'normal-item.csv', 'status': 'success'},
        }
        records.append(record)
    names = sorted(columns.intersection(records[0]))
    timestamps = sorted(columns.intersection({'created_at','updated_at','logged_at'}))
    if not names and not timestamps:
        return
    # Column names come from the fixed allowlist above, not CSV input.
    sql = (f"INSERT INTO price_update_logs ({','.join(names + timestamps)}) "
           f"SELECT {','.join(['r.'+name for name in names] + ['CURRENT_TIMESTAMP']*len(timestamps))} "
           "FROM jsonb_populate_recordset(NULL::price_update_logs,%s::jsonb) r")
    # Log failures must not poison the price update transaction.
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(sql, (json.dumps(records, ensure_ascii=False),))
    except Exception as exc:
        print(f"注意: このバッチの価格更新ログを保存できませんでした: {exc}", flush=True)


def apply_updates(conn, rows, include_stock, execute, *, log_columns=None):
    valid = [r for r in rows if r.get('found') and
             (r.get('new_price') is not None or (include_stock and r.get('new_stock') is not None))]
    if not execute:
        return len(valid), len(rows)-len(valid)
    # Duplicate CSV rows retain last-row-wins behavior.
    unique = {r['store_product_id']: r for r in valid}
    batch = [unique[key] for key in sorted(unique)]
    if not batch:
        return 0, len(rows)
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE store_products sp SET current_price=COALESCE(t.price,sp.current_price),
                current_stock=COALESCE(t.stock,sp.current_stock),
                api_last_synced_at=CURRENT_TIMESTAMP, api_last_error=NULL, updated_at=CURRENT_TIMESTAMP
            FROM unnest(%s::bigint[],%s::bigint[],%s::integer[]) t(id,price,stock)
            WHERE sp.id=t.id RETURNING sp.id
            """, ([r['store_product_id'] for r in batch], [r.get('new_price') for r in batch],
                  [r.get('new_stock') if include_stock else None for r in batch]))
        updated_ids = {row[0] for row in cur.fetchall()}
    updated_rows = [r for r in batch if r['store_product_id'] in updated_ids]
    columns = log_columns if log_columns is not None else get_existing_columns(conn, 'price_update_logs')
    insert_batch_logs(conn, updated_rows, columns, include_stock)
    return len(updated_rows), len(rows)-len(updated_rows)


def apply_targets(conn, store, targets, include_stock, execute):
    updated = skipped = 0
    columns = get_existing_columns(conn, 'price_update_logs') if execute else set()
    # Short transactions: a failure rolls back only the current batch.
    for offset in range(0, len(targets), BATCH_SIZE):
        try:
            rows = fetch_current_rows(conn, store, targets[offset:offset+BATCH_SIZE])
            done, ignored = apply_updates(conn, rows, include_stock, execute, log_columns=columns)
            if execute:
                conn.commit()
            else:
                conn.rollback()
            updated += done
            skipped += ignored
            print(f"CSV_DB_PROGRESS processed={min(offset+BATCH_SIZE,len(targets))}/{len(targets)} "
                  f"updated={updated} skipped={skipped} committed={execute}", flush=True)
        except Exception:
            conn.rollback()
            print(f"CSV反映失敗: 確定済み={updated}件 / 今回のバッチは取り消しました。", flush=True)
            raise
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
        updated, skipped = apply_targets(
            conn, args.store, targets, args.include_stock, args.execute
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
