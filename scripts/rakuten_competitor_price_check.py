import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from db_config import connect_db


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR.parent / ".env"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"


def load_credentials() -> tuple[str, str]:
    load_dotenv(ENV_PATH)
    application_id = os.getenv("RAKUTEN_WEB_SERVICE_APPLICATION_ID", "").strip()
    access_key = os.getenv("RAKUTEN_WEB_SERVICE_ACCESS_KEY", "").strip()
    if not application_id or not access_key:
        raise RuntimeError(
            f"Rakuten Web Service credentials are missing: {ENV_PATH} "
            "(set RAKUTEN_WEB_SERVICE_APPLICATION_ID and RAKUTEN_WEB_SERVICE_ACCESS_KEY)"
        )
    return application_id, access_key


def normalize_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items") or payload.get("Items") or []
    normalized: list[dict[str, Any]] = []
    for entry in items:
        item = entry.get("Item", entry) if isinstance(entry, dict) else {}
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def fetch_competitors(jan_code: str, timeout: float = 20.0) -> list[dict[str, Any]]:
    application_id, access_key = load_credentials()
    try:
        response = requests.get(
            ENDPOINT,
            params={
                "applicationId": application_id,
                "keyword": jan_code,
                "sort": "+itemPrice",
                "postageFlag": 1,
                "availability": 1,
                "hits": 30,
                "format": "json",
                "formatVersion": 2,
                "elements": "itemName,itemCode,shopCode,shopName,itemPrice,postageFlag,availability,itemUrl",
            },
            headers={"accessKey": access_key},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Rakuten competitor request failed: {type(exc).__name__}") from exc
    if not response.ok:
        try:
            detail = response.json().get("errors", {}).get("errorMessage", "")
        except ValueError:
            detail = ""
        raise RuntimeError(f"Rakuten competitor request rejected: HTTP {response.status_code} {detail}".strip())
    candidates: list[dict[str, Any]] = []
    for item in normalize_items(response.json()):
        try:
            price = int(item.get("itemPrice"))
        except (TypeError, ValueError):
            continue
        if price <= 0 or int(item.get("postageFlag", 1)) != 0 or int(item.get("availability", 0)) != 1:
            continue
        candidates.append(
            {
                "item_code": str(item.get("itemCode") or ""),
                "shop_code": str(item.get("shopCode") or ""),
                "shop_name": str(item.get("shopName") or ""),
                "item_name": str(item.get("itemName") or ""),
                "item_price": price,
                "postage_included": True,
                "availability": True,
                "item_url": str(item.get("itemUrl") or ""),
            }
        )
    return candidates


def fetch_targets(
    store_code: str,
    limit: int,
    asin: str = "",
    max_age_hours: float | None = None,
) -> list[tuple[str, str]]:
    where = ["sp.enabled = TRUE", "ap.jan_code IS NOT NULL", "ap.jan_code <> ''"]
    params: list[Any] = []
    if store_code:
        where.append("s.store_code = %s")
        params.append(store_code)
    if asin:
        where.append("sp.asin = %s")
        params.append(asin.strip().upper())
    freshness_join = ""
    freshness_order = "sp.asin"
    target_select = "DISTINCT sp.asin, ap.jan_code"
    if max_age_hours is not None:
        if max_age_hours <= 0:
            raise ValueError("max_age_hours must be greater than zero")
        # A missing snapshot, including a saved no-result marker, is selected
        # before a fresh one.  This makes the recurring QNAP job work through
        # the full catalog instead of repeatedly starting at the same ASINs.
        freshness_join = """
        LEFT JOIN LATERAL (
            SELECT MAX(rcp.fetched_at) AS fetched_at
            FROM rakuten_competitor_price_snapshots rcp
            WHERE rcp.asin = sp.asin
        ) latest_snapshot ON TRUE
        """
        where.append("(latest_snapshot.fetched_at IS NULL OR latest_snapshot.fetched_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 hour'))")
        params.append(max_age_hours)
        freshness_order = "latest_snapshot.fetched_at NULLS FIRST, sp.asin"
        # ``store_products`` has one row per store/ASIN.  Avoid DISTINCT here
        # because PostgreSQL requires the freshness ORDER BY expression to be
        # part of a DISTINCT select list.
        target_select = "sp.asin, ap.jan_code"
    sql = f"""
        SELECT {target_select}
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        JOIN amazon_products ap ON ap.asin = sp.asin
        {freshness_join}
        WHERE {' AND '.join(where)}
        ORDER BY {freshness_order}
        LIMIT %s
    """
    params.append(limit)
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [(str(row[0]), str(row[1])) for row in cur.fetchall()]
    finally:
        conn.close()


def replace_snapshots(asin: str, jan_code: str, candidates: list[dict[str, Any]]) -> int:
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rakuten_competitor_price_snapshots WHERE asin = %s", (asin,))
                # Keep one unavailable marker when no matching Rakuten offer
                # exists.  The calculation query only accepts availability=true,
                # while the recurring fetcher uses fetched_at to avoid querying
                # the same no-result JAN every cycle.
                lowest_candidate = min(candidates, key=lambda candidate: int(candidate["item_price"])) if candidates else None
                snapshot_rows = [lowest_candidate] if lowest_candidate is not None else [{
                    "item_code": "__no_competitor__",
                    "shop_code": "",
                    "shop_name": "",
                    "item_name": "",
                    "item_price": 1,
                    "postage_included": False,
                    "availability": False,
                    "item_url": "",
                }]
                for candidate in snapshot_rows:
                    cur.execute(
                        """
                        INSERT INTO rakuten_competitor_price_snapshots (
                            asin, jan_code, item_code, shop_code, shop_name, item_name,
                            item_price, postage_included, availability, item_url, fetched_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            asin,
                            jan_code,
                            candidate["item_code"],
                            candidate["shop_code"],
                            candidate["shop_name"],
                            candidate["item_name"],
                            candidate["item_price"],
                            bool(candidate["postage_included"]),
                            bool(candidate["availability"]),
                            candidate["item_url"],
                            datetime.now(timezone.utc),
                        ),
                    )
        return len(snapshot_rows)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Rakuten Ichiba competitor prices using JAN and optionally save the latest candidates.")
    parser.add_argument("--store", default="", help="Limit database targets to one store_code.")
    parser.add_argument("--asin", default="", help="Limit database targets to one ASIN.")
    parser.add_argument("--jan", default="", help="Read one JAN directly without database lookup or saving.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--save", action="store_true", help="Replace saved snapshots for database targets. --jan never saves.")
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Minimum seconds between request starts. Rakuten Web Service requires at least 1.0.",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="Only fetch targets whose saved competitor snapshot is older than this many hours.",
    )
    args = parser.parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    if args.interval < 1.0:
        raise SystemExit("--interval must be at least 1.0 (one request per second per Rakuten application ID)")

    raw_targets = [("", args.jan.strip())] if args.jan.strip() else fetch_targets(
        args.store,
        args.limit,
        args.asin,
        args.max_age_hours,
    )
    if not raw_targets:
        print("No JAN-linked targets found.")
        return 0

    # The price search result is determined by JAN, not ASIN.  Avoid consuming
    # the one-request-per-second quota more than once when the same JAN has
    # multiple listed variations or duplicate catalog records in this batch.
    targets_by_jan: dict[str, list[str]] = {}
    for asin, jan_code in raw_targets:
        targets_by_jan.setdefault(jan_code, []).append(asin)

    next_request_at = time.monotonic()
    grouped_targets = list(targets_by_jan.items())
    for index, (jan_code, asins) in enumerate(grouped_targets, start=1):
        wait_seconds = next_request_at - time.monotonic()
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        request_started_at = time.monotonic()
        candidates = fetch_competitors(jan_code)
        lowest = min((row["item_price"] for row in candidates), default=None)
        saved = (
            sum(replace_snapshots(asin, jan_code, candidates) for asin in asins if asin)
            if args.save
            else 0
        )
        asin_labels = ",".join(asins) if asins else "-"
        print(
            f"{index}/{len(grouped_targets)} asins={asin_labels} jan={jan_code} "
            f"candidates={len(candidates)} lowest={lowest} saved={saved}"
        )
        next_request_at = request_started_at + args.interval
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
