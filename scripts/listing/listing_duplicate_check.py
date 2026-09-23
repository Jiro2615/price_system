from __future__ import annotations

from typing import Any

from scripts.db_config import connect_db


def find_existing_listings(asins: list[str], store_code: str) -> dict[str, dict[str, Any]]:
    """Bulk form of the same current-listing predicate; never use audit history."""
    normalized = list(dict.fromkeys(asin.strip().upper() for asin in asins if asin.strip()))
    if not normalized:
        return {}
    found = {}
    with connect_db(options="-c default_transaction_read_only=on") as conn, conn.cursor() as cur:
        for offset in range(0, len(normalized), 1000):
            cur.execute(
                """
                SELECT DISTINCT ON (UPPER(sp.asin)) UPPER(sp.asin),
                       sp.mall_item_code, sp.current_price, sp.current_stock,
                       COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code)
                FROM store_products sp JOIN stores s ON s.id = sp.store_id
                WHERE LOWER(s.store_code) = LOWER(%s) AND UPPER(sp.asin) = ANY(%s)
                  AND COALESCE(sp.enabled, TRUE) = TRUE AND COALESCE(sp.force_stop, FALSE) = FALSE
                  AND COALESCE(sp.current_status, '') NOT IN ('delete_pending', 'deleted')
                ORDER BY UPPER(sp.asin), sp.updated_at DESC NULLS LAST
                """,
                (store_code, normalized[offset:offset + 1000]),
            )
            for asin, code, price, stock, sku in cur.fetchall():
                if str(code or "").strip():
                    found[asin] = {
                        "management_number": str(code).strip(), "current_price": price,
                        "current_stock": stock, "sku_code": str(sku or code).strip(),
                        "source": "store_products",
                    }
    return found


def find_existing_listing(asin: str, store_code: str) -> dict[str, Any] | None:
    """Find an active same-ASIN listing from the authoritative store DB.

    Execution history is an audit/resume record, not proof that an item is
    still listed in RMS.  In particular, an RMS deletion followed by removal
    from ``store_products`` must allow the ASIN to be listed again.
    """
    with connect_db(options="-c default_transaction_read_only=on") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT sp.mall_item_code, sp.current_price, sp.current_stock,
                   COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code)
            FROM store_products sp JOIN stores s ON s.id = sp.store_id
            WHERE LOWER(s.store_code) = LOWER(%s) AND UPPER(sp.asin) = UPPER(%s)
              AND COALESCE(sp.enabled, TRUE) = TRUE AND COALESCE(sp.force_stop, FALSE) = FALSE
              AND COALESCE(sp.current_status, '') NOT IN ('delete_pending', 'deleted')
            ORDER BY sp.updated_at DESC NULLS LAST LIMIT 1
            """,
            (store_code, asin),
        )
        row = cur.fetchone()
    if row and str(row[0] or "").strip():
        return {
            "management_number": str(row[0]).strip(),
            "current_price": row[1],
            "current_stock": row[2],
            "sku_code": str(row[3] or row[0]).strip(),
            "source": "store_products",
        }
    return None
