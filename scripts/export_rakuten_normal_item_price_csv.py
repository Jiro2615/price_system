import argparse
import csv
import math
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from db_config import connect_db


BASE_DIR = Path(r"C:\price_system")
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_csv"


NORMAL_ITEM_HEADERS_BASE = [
    "商品管理番号（商品URL）",
    "選択肢タイプ",
    "SKU管理番号",
    "通常購入販売価格",
]

NORMAL_ITEM_HEADERS_WITH_STOCK = [
    "商品管理番号（商品URL）",
    "選択肢タイプ",
    "SKU管理番号",
    "通常購入販売価格",
    "在庫数",
]

CHECK_HEADERS = [
    "store_product_id",
    "ASIN",
    "商品管理番号",
    "SKU管理番号",
    "商品名",
    "現在価格",
    "更新予定価格",
    "価格差",
    "価格変更率",
    "現在在庫",
    "更新予定在庫",
    "Amazon価格",
    "Amazonポイント",
    "Amazon在庫数",
    "CSVブロック",
    "CSVブロック理由",
    "更新理由",
]


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        s = str(value).replace(",", "").strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default


def pct_change(current_price: int | None, target_price: int | None) -> float | None:
    if current_price is None or current_price <= 0 or target_price is None:
        return None
    return (target_price - current_price) / current_price


def format_pct(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value * 100:.2f}%"


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


def build_reason(row: dict[str, Any], include_stock: bool) -> str:
    reasons = []

    current_price = to_int(row.get("current_price"))
    target_price = to_int(row.get("target_price"))
    current_stock = to_int(row.get("current_stock"))
    target_stock = to_int(row.get("target_stock"))

    if target_price is not None and current_price != target_price:
        reasons.append("価格変更")

    if include_stock and target_stock is not None and current_stock != target_stock:
        reasons.append("在庫変更")

    if row.get("business_ng"):
        reasons.append(f"業務NG:{row.get('ng_reason') or ''}")

    if row.get("system_error"):
        reasons.append(f"システムエラー:{row.get('ng_reason') or ''}")

    return " / ".join(reasons)


def validate_target(row: dict[str, Any], include_stock: bool, allow_large_change: bool, max_change_rate: float) -> tuple[bool, str]:
    manage_number = str(row.get("mall_item_code") or "").strip()
    sku_code = str(row.get("sku_code") or "").strip()
    target_price = to_int(row.get("target_price"))
    current_price = to_int(row.get("current_price"))
    target_stock = to_int(row.get("target_stock"))

    if not manage_number:
        return False, "商品管理番号が空"

    if not sku_code:
        return False, "SKU管理番号が空"

    if target_price is None:
        return False, "target_price が空"

    if target_price < 1 or target_price > 999999999:
        return False, f"target_price が範囲外: {target_price}"

    if include_stock and target_stock is not None and target_stock < 0:
        return False, f"target_stock がマイナス: {target_stock}"

    change_rate = pct_change(current_price, target_price)
    if not allow_large_change and change_rate is not None and abs(change_rate) > max_change_rate:
        return False, f"価格変更率が大きすぎます: {format_pct(change_rate)}"

    return True, ""


def fetch_price_targets(
    store_code: str,
    limit: int,
    include_stock: bool,
    include_stock_only: bool,
    allow_large_change: bool,
    max_change_rate: float,
    include_blocked: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    conn = connect_db()
    valid_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []

    try:
        ensure_columns(conn)

        where = [
            "s.mall = 'rakuten'",
            "s.store_code = %s",
            "sp.enabled = TRUE",
            "COALESCE(sp.no_price_change, FALSE) = FALSE",
            "sp.mall_item_code IS NOT NULL",
            "sp.sku_code IS NOT NULL",
        ]
        params: list[Any] = [store_code]

        if not include_blocked:
            where.append("COALESCE(sp.rakuten_csv_update_blocked, FALSE) = FALSE")

        if include_stock and include_stock_only:
            where.append(
                """
                (
                    (sp.target_price IS NOT NULL AND COALESCE(sp.current_price, -1) <> sp.target_price)
                    OR
                    (sp.target_stock IS NOT NULL AND COALESCE(sp.current_stock, -999999) <> sp.target_stock)
                )
                """
            )
        else:
            where.append("sp.target_price IS NOT NULL")
            where.append("COALESCE(sp.current_price, -1) <> sp.target_price")

        sql = f"""
            SELECT
                sp.id AS store_product_id,
                sp.asin,
                sp.mall_item_code,
                sp.sku_code,
                sp.item_name,
                sp.current_price,
                sp.target_price,
                sp.current_stock,
                sp.target_stock,
                sp.rakuten_csv_update_blocked,
                sp.rakuten_csv_update_error,
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
            ORDER BY sp.id
            LIMIT %s;
        """
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(sql, params)
            colnames = [desc.name for desc in cur.description]
            rows = [dict(zip(colnames, row)) for row in cur.fetchall()]

        for row in rows:
            ok, reason = validate_target(
                row=row,
                include_stock=include_stock,
                allow_large_change=allow_large_change,
                max_change_rate=max_change_rate,
            )
            if ok:
                valid_rows.append(row)
            else:
                row = dict(row)
                row["_skip_reason"] = reason
                skipped_rows.append(row)

    finally:
        conn.close()

    return valid_rows, skipped_rows


def make_normal_item_rows(rows: list[dict[str, Any]], include_stock: bool, include_product_rows: bool) -> list[list[Any]]:
    output_rows: list[list[Any]] = []
    grouped: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    for row in rows:
        manage_number = str(row.get("mall_item_code") or "").strip()
        grouped.setdefault(manage_number, []).append(row)

    for manage_number, sku_rows in grouped.items():
        if include_product_rows:
            if include_stock:
                output_rows.append([manage_number, "", "", "", ""])
            else:
                output_rows.append([manage_number, "", "", ""])

        for row in sku_rows:
            sku_code = str(row.get("sku_code") or "").strip()
            target_price = to_int(row.get("target_price"))
            target_stock = to_int(row.get("target_stock"))

            if include_stock:
                output_rows.append([
                    manage_number,
                    "",
                    sku_code,
                    target_price,
                    "" if target_stock is None else target_stock,
                ])
            else:
                output_rows.append([
                    manage_number,
                    "",
                    sku_code,
                    target_price,
                ])

    return output_rows


def write_normal_item_csv(path: Path, rows: list[dict[str, Any]], include_stock: bool, include_product_rows: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = NORMAL_ITEM_HEADERS_WITH_STOCK if include_stock else NORMAL_ITEM_HEADERS_BASE
    csv_rows = make_normal_item_rows(
        rows=rows,
        include_stock=include_stock,
        include_product_rows=include_product_rows,
    )

    # RMSのCSVはCP932が必要です。商品名などにCP932外の文字が混ざっても、
    # CSV全体の出力を止めず置換して続行します。
    with path.open("w", encoding="cp932", errors="replace", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(csv_rows)


def write_check_csv(path: Path, rows: list[dict[str, Any]], include_stock: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="cp932", errors="replace", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CHECK_HEADERS)

        for row in rows:
            current_price = to_int(row.get("current_price"))
            target_price = to_int(row.get("target_price"))
            current_stock = to_int(row.get("current_stock"))
            target_stock = to_int(row.get("target_stock"))
            change = None
            if current_price is not None and target_price is not None:
                change = target_price - current_price

            writer.writerow([
                row.get("store_product_id"),
                row.get("asin") or "",
                row.get("mall_item_code") or "",
                row.get("sku_code") or "",
                row.get("item_name") or "",
                "" if current_price is None else current_price,
                "" if target_price is None else target_price,
                "" if change is None else change,
                format_pct(pct_change(current_price, target_price)),
                "" if current_stock is None else current_stock,
                "" if target_stock is None else target_stock,
                "" if row.get("amazon_price") is None else row.get("amazon_price"),
                "" if row.get("amazon_point") is None else row.get("amazon_point"),
                "" if row.get("available_qty") is None else row.get("available_qty"),
                row.get("rakuten_csv_update_blocked"),
                row.get("rakuten_csv_update_error") or "",
                build_reason(row, include_stock=include_stock),
            ])


def write_skipped_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "store_product_id",
        "ASIN",
        "商品管理番号",
        "SKU管理番号",
        "商品名",
        "現在価格",
        "更新予定価格",
        "現在在庫",
        "更新予定在庫",
        "CSVブロック",
        "CSVブロック理由",
        "スキップ理由",
    ]

    with path.open("w", encoding="cp932", errors="replace", newline="") as f:
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
                row.get("target_price") if row.get("target_price") is not None else "",
                row.get("current_stock") if row.get("current_stock") is not None else "",
                row.get("target_stock") if row.get("target_stock") is not None else "",
                row.get("rakuten_csv_update_blocked"),
                row.get("rakuten_csv_update_error") or "",
                row.get("_skip_reason") or "",
            ])


def print_preview(rows: list[dict[str, Any]], include_stock: bool, max_rows: int = 10) -> None:
    if not rows:
        print("出力対象はありません。")
        return

    print("")
    print("===== CSV出力対象プレビュー =====")
    print("")

    for row in rows[:max_rows]:
        print(
            f"[{row.get('store_product_id')}] "
            f"ASIN={row.get('asin')} "
            f"Item={row.get('mall_item_code')} "
            f"SKU={row.get('sku_code')}"
        )
        print(f"  name : {str(row.get('item_name') or '')[:80]}")
        print(f"  price: {row.get('current_price')} -> {row.get('target_price')}")
        if include_stock:
            print(f"  stock: {row.get('current_stock')} -> {row.get('target_stock')}")
        print(f"  amazon: price={row.get('amazon_price')}, point={row.get('amazon_point')}, qty={row.get('available_qty')}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天 normal-item.csv 形式の価格更新CSVをDBから出力します。blocked商品はデフォルト除外します。")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--limit", type=int, default=10, help="CSV出力する最大SKU件数")
    parser.add_argument("--output", default="", help="normal-item CSV出力先。未指定なら C:\\price_system\\output\\rakuten_csv 配下")
    parser.add_argument("--check-output", default="", help="確認用CSV出力先。未指定なら自動生成")
    parser.add_argument("--include-stock", action="store_true", help="在庫数もCSVに含める")
    parser.add_argument("--include-stock-only", action="store_true", help="--include-stock 時、在庫差分だけの商品も出力対象に含める")
    parser.add_argument("--sku-only", action="store_true", help="商品レベル行を出さず、SKUレベル行だけ出力する。楽天仕様上NGになりやすいので基本非推奨")
    parser.add_argument("--include-blocked", action="store_true", help="CSV更新blocked商品も出力対象に含める")
    parser.add_argument("--allow-large-change", action="store_true", help="価格変更率が大きくても出力する")
    parser.add_argument("--max-change-rate", type=float, default=0.50, help="許容する価格変更率。0.50=50%%")
    parser.add_argument("--dry-run", action="store_true", help="CSVを書き出さず、対象プレビューだけ表示する")
    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit は1以上にしてください。")
        return 2

    if args.include_stock_only and not args.include_stock:
        print("--include-stock-only は --include-stock と一緒に指定してください。")
        return 2

    rows, skipped_rows = fetch_price_targets(
        store_code=args.store,
        limit=args.limit,
        include_stock=args.include_stock,
        include_stock_only=args.include_stock_only,
        allow_large_change=args.allow_large_change,
        max_change_rate=args.max_change_rate,
        include_blocked=args.include_blocked,
    )

    print_preview(rows, include_stock=args.include_stock)
    print(f"CSV出力対象SKU件数: {len(rows)}")
    print(f"スキップ件数      : {len(skipped_rows)}")
    if not args.include_blocked:
        print("CSV blocked商品  : 除外中")

    if skipped_rows:
        print("")
        print("スキップ先頭5件:")
        for row in skipped_rows[:5]:
            print(
                f"  id={row.get('store_product_id')} "
                f"Item={row.get('mall_item_code')} "
                f"SKU={row.get('sku_code')} "
                f"reason={row.get('_skip_reason')}"
            )

    if args.dry_run:
        print("")
        print("dry-run のためCSVは出力しません。")
        return 0

    if not rows:
        print("出力対象がないためCSVは作成しません。")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.output:
        normal_item_path = Path(args.output)
    else:
        normal_item_path = OUTPUT_DIR / f"normal-item_price_{timestamp}.csv"

    if args.check_output:
        check_path = Path(args.check_output)
    else:
        check_path = OUTPUT_DIR / f"normal-item_price_check_{timestamp}.csv"

    skipped_path = OUTPUT_DIR / f"normal-item_price_skipped_{timestamp}.csv"

    write_normal_item_csv(
        path=normal_item_path,
        rows=rows,
        include_stock=args.include_stock,
        include_product_rows=not args.sku_only,
    )
    write_check_csv(check_path, rows, include_stock=args.include_stock)

    if skipped_rows:
        write_skipped_csv(skipped_path, skipped_rows)

    print("")
    print("CSV出力完了")
    print(f"  楽天アップロード用: {normal_item_path}")
    print(f"  確認用CSV        : {check_path}")
    if skipped_rows:
        print(f"  スキップCSV      : {skipped_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
