from __future__ import annotations

"""Keepa Product Finder candidate discovery for the Rakuten listing flow.

The Product Finder endpoint returns ASINs only. This command normally stores
that bounded ASIN list in the shared PostgreSQL database. Optional product
metadata can be requested for a smaller, detail-oriented search, but it costs
one additional Keepa token per candidate.

It is deliberately a *candidate* finder.  The existing listing bulk check is
still the authority for the Amazon page, Rakuten duplicate, blacklist and RMS
payload decisions.
"""

import argparse
import json
import math
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from psycopg.types.json import Jsonb

# The execution agent invokes this file directly.  Make the project package
# importable without depending on the caller's PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.db_config import connect_db
from scripts.listing.keepa_product_client import KeepaClient, load_keepa_api_key, parse_keepa_product


KEEPA_QUERY_ENDPOINT = "https://api.keepa.com/query"
ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
# Keepa permits up to 10,000 ASINs for the first Product Finder page.  The
# UI warns about the matching product-metadata token cost before such a large
# request is started.
MAX_CANDIDATE_LIMIT = 10000


def comma_values(value: object) -> list[str]:
    return [item.strip() for item in str(value or "").replace("\n", ",").split(",") if item.strip()]


def integer_values(value: object, label: str) -> list[int]:
    result: list[int] = []
    for item in comma_values(value):
        try:
            number = int(item)
        except ValueError as exc:
            raise ValueError(f"{label} はAmazonカテゴリIDをカンマ区切りで入力してください: {item}") from exc
        if number <= 0:
            raise ValueError(f"{label} は正の数だけ指定できます: {item}")
        result.append(number)
    return list(dict.fromkeys(result))


def optional_int(value: object, label: str, *, minimum: int = 0) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{label} は整数で入力してください") from exc
    if parsed < minimum:
        raise ValueError(f"{label} は{minimum}以上で入力してください")
    return parsed


def optional_rating(value: object) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        rating = float(raw)
    except ValueError as exc:
        raise ValueError("最低評価は0.0〜5.0で入力してください") from exc
    if rating < 0 or rating > 5:
        raise ValueError("最低評価は0.0〜5.0で入力してください")
    return rating


def optional_nonnegative_float(value: object, label: str) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise ValueError(f"{label} は0以上の数値で入力してください") from exc
    if parsed < 0:
        raise ValueError(f"{label} は0以上の数値で入力してください")
    return parsed


def ensure_candidate_table(cur: Any) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS keepa_product_finder_candidates (
            id BIGSERIAL PRIMARY KEY,
            run_id TEXT NOT NULL,
            store_code TEXT NOT NULL,
            asin TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            ean_code TEXT NOT NULL DEFAULT '',
            category_id BIGINT,
            category_path TEXT NOT NULL DEFAULT '',
            current_new_offer_count INTEGER,
            avg90_new_offer_count NUMERIC(12, 3),
            avg90_seller_count NUMERIC(12, 3),
            buy_box_price INTEGER,
            buy_box_shipping INTEGER,
            finder_selection_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            keepa_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            candidate_status TEXT NOT NULL DEFAULT 'candidate',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, asin)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS keepa_product_finder_candidates_run_idx
        ON keepa_product_finder_candidates (run_id, candidate_status, id)
        """
    )


def make_selection(args: argparse.Namespace) -> dict[str, Any]:
    selection: dict[str, Any] = {
        "page": args.page,
        "perPage": args.candidate_limit,
        # Product Finder treats 0 as a standard product.  This excludes
        # downloadable products, ebooks and variation parents up front.
        "productType": 0,
        # Candidate discovery must not return adult products.  Used offers may
        # coexist with a new offer, so they are *not* used as an exclusion.
        "isAdultProduct": False,
        "imageCount_gte": 1,
        "current_COUNT_NEW_gte": args.min_current_new_sellers,
    }
    root_categories = integer_values(args.root_categories, "ルートカテゴリ")
    include_categories = integer_values(args.include_categories, "対象カテゴリ")
    exclude_categories = integer_values(args.exclude_categories, "除外カテゴリ")
    if root_categories:
        selection["rootCategory"] = root_categories
    if include_categories:
        selection["categories_include"] = include_categories
    if exclude_categories:
        selection["categories_exclude"] = exclude_categories
    if args.title.strip():
        selection["title"] = args.title.strip()
    if comma_values(args.brands):
        selection["brand"] = comma_values(args.brands)
    if comma_values(args.manufacturers):
        selection["manufacturer"] = comma_values(args.manufacturers)

    numeric_filters = {
        "current_NEW_gte": args.min_price,
        "current_NEW_lte": args.max_price,
        "current_COUNT_NEW_lte": args.max_current_new_sellers,
        # The Product Finder schema documents count statistics as integers.
        # Keep the API predicate conservative when a fractional threshold is
        # entered, then apply the exact decimal comparison after product data
        # is returned below.
        "avg90_COUNT_NEW_gte": math.floor(args.min_avg90_new_sellers) if args.min_avg90_new_sellers is not None else None,
        "avg90_COUNT_NEW_lte": math.ceil(args.max_avg90_new_sellers) if args.max_avg90_new_sellers is not None else None,
        "current_COUNT_REVIEWS_gte": args.min_review_count,
        "current_SALES_gte": args.min_sales_rank,
        "current_SALES_lte": args.max_sales_rank,
        "monthlySold_gte": args.min_monthly_sold,
    }
    for name, value in numeric_filters.items():
        if value is not None:
            selection[name] = value
    if args.min_rating is not None:
        selection["current_RATING_gte"] = int(round(args.min_rating * 10))
    if args.amazon_in_stock:
        selection["availabilityAmazon"] = [0]
    # Sales rank is a practical default ordering for sourcing candidates.
    selection["sort"] = [["current_SALES", "asc"]]
    return selection


def request_json(session: requests.Session, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    for attempt in range(4):
        response = session.request(method, url, timeout=45, **kwargs)
        try:
            data = response.json()
        except ValueError:
            data = {"raw_response": response.text[:1000]}
        if response.status_code == 429 and attempt < 3:
            wait_seconds = min(max(float(data.get("refillIn") or 5000) / 1000, 2), 30)
            print(f"KEEPA_PRODUCT_FINDER_WAIT seconds={wait_seconds:g}", flush=True)
            time.sleep(wait_seconds)
            continue
        if not response.ok:
            detail = data.get("error") or data.get("errorMessage") or data.get("raw_response") or ""
            raise RuntimeError(f"Keepa API rejected request: HTTP {response.status_code} {detail}".strip())
        return data
    raise RuntimeError("Keepa API rate limit retry exhausted")


def batched(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def category_path(product: Any) -> str:
    return " > ".join(str(node.get("name") or "").strip() for node in product.category_tree if str(node.get("name") or "").strip())


def metadata_candidates(
    session: requests.Session,
    api_key: str,
    asins: list[str],
    args: argparse.Namespace,
    selection: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    token_state: dict[str, Any] = {}
    for batch in batched(asins, 100):
        payload = request_json(
            session,
            "GET",
            "https://api.keepa.com/product",
            params={
                "key": api_key,
                "domain": 5,
                "asin": ",".join(batch),
                "stats": 90,
                "history": 0,
            },
        )
        token_state = {key: payload.get(key) for key in ("tokensLeft", "tokensConsumed", "refillRate", "refillIn") if key in payload}
        raw_products = payload.get("products") or []
        for raw in raw_products:
            if not isinstance(raw, dict):
                continue
            asin = str(raw.get("asin") or "").strip().upper()
            if not ASIN_PATTERN.fullmatch(asin):
                continue
            product = parse_keepa_product(asin, raw)
            # Keepa query has already enforced these predicates.  Rechecking
            # uses the exact metadata that is displayed and protects against
            # a query/product update race.
            if product.is_adult is True or product.current_new_offer_count in (None, 0):
                continue
            if args.min_avg90_new_sellers is not None and (
                product.avg90_new_offer_count is None or product.avg90_new_offer_count < args.min_avg90_new_sellers
            ):
                continue
            if args.max_avg90_new_sellers is not None and (
                product.avg90_new_offer_count is None or product.avg90_new_offer_count > args.max_avg90_new_sellers
            ):
                continue
            rows.append(
                {
                    "asin": asin,
                    "title": product.title,
                    "ean_code": product.ean,
                    "category_id": product.category_id,
                    "category_path": category_path(product),
                    "current_new_offer_count": product.current_new_offer_count,
                    "avg90_new_offer_count": product.avg90_new_offer_count,
                    "avg90_seller_count": product.avg90_seller_count,
                    "buy_box_price": product.buy_box_price,
                    "buy_box_shipping": product.buy_box_shipping,
                    "keepa_summary": asdict(product),
                    "finder_selection": selection,
                }
            )
    return rows, token_state


def asin_only_candidates(asins: list[str], selection: dict[str, Any]) -> list[dict[str, Any]]:
    """Persist fast Product Finder output without per-ASIN product requests."""
    return [
        {
            "asin": asin,
            "title": "",
            "ean_code": "",
            "category_id": None,
            "category_path": "",
            "current_new_offer_count": None,
            "avg90_new_offer_count": None,
            "avg90_seller_count": None,
            "buy_box_price": None,
            "buy_box_shipping": None,
            "keepa_summary": {},
            "finder_selection": selection,
        }
        for asin in asins
    ]


def save_candidates(run_id: str, store_code: str, rows: list[dict[str, Any]]) -> None:
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_candidate_table(cur)
                cur.execute("DELETE FROM keepa_product_finder_candidates WHERE run_id = %s", (run_id,))
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO keepa_product_finder_candidates (
                            run_id, store_code, asin, title, ean_code, category_id, category_path,
                            current_new_offer_count, avg90_new_offer_count, avg90_seller_count,
                            buy_box_price, buy_box_shipping, finder_selection_json, keepa_summary_json
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            run_id,
                            store_code,
                            row["asin"],
                            row["title"],
                            row["ean_code"],
                            row["category_id"],
                            row["category_path"],
                            row["current_new_offer_count"],
                            row["avg90_new_offer_count"],
                            row["avg90_seller_count"],
                            row["buy_box_price"],
                            row["buy_box_shipping"],
                            Jsonb(row["finder_selection"]),
                            Jsonb(row["keepa_summary"]),
                        ),
                    )
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find listing candidates through the Keepa Product Finder API")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--root-categories", default="")
    parser.add_argument("--include-categories", default="")
    parser.add_argument("--exclude-categories", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--brands", default="")
    parser.add_argument("--manufacturers", default="")
    parser.add_argument("--min-price", default="")
    parser.add_argument("--max-price", default="")
    parser.add_argument("--min-rating", default="")
    parser.add_argument("--min-review-count", default="")
    parser.add_argument("--min-current-new-sellers", default="1")
    parser.add_argument("--max-current-new-sellers", default="")
    parser.add_argument("--min-avg90-new-sellers", default="")
    parser.add_argument("--max-avg90-new-sellers", default="")
    parser.add_argument("--min-sales-rank", default="")
    parser.add_argument("--max-sales-rank", default="")
    parser.add_argument("--min-monthly-sold", default="")
    parser.add_argument("--candidate-limit", type=int, default=100)
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--amazon-in-stock", action="store_true")
    parser.add_argument("--fetch-product-metadata", action="store_true")
    args = parser.parse_args()
    args.store = str(args.store).strip().lower()
    args.run_id = str(args.run_id).strip()
    if not args.run_id or not args.store:
        raise ValueError("run_id and store are required")
    if args.candidate_limit < 50 or args.candidate_limit > MAX_CANDIDATE_LIMIT:
        raise ValueError(f"candidate-limit must be 50 to {MAX_CANDIDATE_LIMIT}")
    if args.page < 0 or args.page * args.candidate_limit >= 10000:
        raise ValueError("page and candidate-limit must stay within Keepa's 10,000-result paging limit")
    for name, label, minimum in (
        ("min_price", "仕入れ価格下限", 0),
        ("max_price", "仕入れ価格上限", 0),
        ("min_review_count", "最小レビュー数", 0),
        ("min_current_new_sellers", "新品出品者数下限", 1),
        ("max_current_new_sellers", "新品出品者数上限", 1),
        ("min_sales_rank", "販売ランク下限", 1),
        ("max_sales_rank", "販売ランク上限", 1),
        ("min_monthly_sold", "月間販売数下限", 0),
    ):
        setattr(args, name, optional_int(getattr(args, name), label, minimum=minimum))
    args.min_avg90_new_sellers = optional_nonnegative_float(
        args.min_avg90_new_sellers,
        "90日平均新品出品者数下限",
    )
    args.max_avg90_new_sellers = optional_nonnegative_float(
        args.max_avg90_new_sellers,
        "90日平均新品出品者数上限",
    )
    args.min_rating = optional_rating(args.min_rating)
    if args.min_price is not None and args.max_price is not None and args.min_price > args.max_price:
        raise ValueError("仕入れ価格下限は上限以下にしてください")
    if args.min_sales_rank is not None and args.max_sales_rank is not None and args.min_sales_rank > args.max_sales_rank:
        raise ValueError("販売ランク下限は上限以下にしてください")
    for lower, upper, label in (
        (args.min_current_new_sellers, args.max_current_new_sellers, "新品出品者数"),
        (args.min_avg90_new_sellers, args.max_avg90_new_sellers, "90日平均新品出品者数"),
    ):
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"{label}下限は上限以下にしてください")
    return args


def main() -> int:
    args = parse_args()
    selection = make_selection(args)
    # At least current_COUNT_NEW_gte is always present, so the finder query
    # is never an unbounded all-products request.
    api_key = load_keepa_api_key()
    session = requests.Session()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(
        "KEEPA_PRODUCT_FINDER_START "
        + json.dumps({"run_id": args.run_id, "store": args.store, "selection": selection}, ensure_ascii=False),
        flush=True,
    )
    query_response = request_json(
        session,
        "POST",
        KEEPA_QUERY_ENDPOINT,
        params={"key": api_key, "domain": 5},
        json=selection,
    )
    asins = [str(asin).strip().upper() for asin in (query_response.get("asinList") or [])]
    asins = list(dict.fromkeys(asin for asin in asins if ASIN_PATTERN.fullmatch(asin)))
    if args.fetch_product_metadata:
        candidates, product_tokens = metadata_candidates(session, api_key, asins, args, selection)
    else:
        candidates = asin_only_candidates(asins, selection)
        product_tokens = {}
    save_candidates(args.run_id, args.store, candidates)
    summary = {
        "run_id": args.run_id,
        "store": args.store,
        "started_at": started,
        "selection": selection,
        "matched_total": query_response.get("totalResults"),
        "finder_returned_count": len(asins),
        "candidate_count": len(candidates),
        "product_metadata_fetched": bool(args.fetch_product_metadata),
        "finder_tokens": {key: query_response.get(key) for key in ("tokensLeft", "tokensConsumed", "refillRate", "refillIn") if key in query_response},
        "product_tokens": product_tokens,
        "estimated_product_requests": math.ceil(len(asins) / 100) if asins else 0,
    }
    print("KEEPA_PRODUCT_FINDER_RESULT " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"KEEPA_PRODUCT_FINDER_ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
