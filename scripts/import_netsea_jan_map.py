import argparse
import sqlite3
from pathlib import Path

from db_config import connect_db


DEFAULT_SQLITE_PATH = Path(r"C:\rakuten\Rakuten\netsea_amazon_work\netsea_amazon_processed.sqlite3")


def load_jan_asin_rows(sqlite_path: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            """
            SELECT jan, amazon_asin
            FROM completed_products
            WHERE status = 'matched'
              AND jan GLOB '[0-9]*'
              AND length(jan) BETWEEN 8 AND 14
              AND amazon_asin <> ''
            """
        ).fetchall()
    return [(str(jan), str(asin).strip().upper()) for jan, asin in rows]


def import_jan_map(rows: list[tuple[str, str]], execute: bool) -> dict[str, int]:
    jan_by_asin: dict[str, str] = {}
    for jan, asin in rows:
        jan_by_asin.setdefault(asin, jan)
    if not jan_by_asin:
        return {"source_rows": len(rows), "matched_asins": 0, "updated": 0}

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT asin FROM amazon_products WHERE asin = ANY(%s)", (list(jan_by_asin),))
            existing_asins = {str(row[0]) for row in cur.fetchall()}
        matched_rows = [(jan_by_asin[asin], asin) for asin in sorted(existing_asins)]
        updated = 0
        if execute:
            with conn.cursor() as cur:
                for jan, asin in matched_rows:
                    cur.execute(
                        "UPDATE amazon_products SET jan_code = %s, updated_at = CURRENT_TIMESTAMP WHERE asin = %s AND jan_code IS DISTINCT FROM %s",
                        (jan, asin, jan),
                    )
                    updated += cur.rowcount
            conn.commit()
        return {"source_rows": len(rows), "matched_asins": len(matched_rows), "updated": updated}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import existing NETSEA JAN to ASIN mappings into price_system.")
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--execute", action="store_true", help="Write matched JAN values to amazon_products.")
    args = parser.parse_args()
    if not args.sqlite_path.is_file():
        raise SystemExit(f"SQLite file not found: {args.sqlite_path}")
    result = import_jan_map(load_jan_asin_rows(args.sqlite_path), execute=args.execute)
    print(f"source_rows={result['source_rows']} matched_asins={result['matched_asins']} updated={result['updated']}")
    if not args.execute:
        print("dry-run: add --execute after applying the migration to save JAN values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
