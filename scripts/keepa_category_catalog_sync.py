from __future__ import annotations

"""Cache the Amazon.co.jp Keepa category tree for the Product Finder UI.

The UI is served by the central Web Orchestrator, while the Keepa credential
is intentionally kept on the assigned listing PC.  This command therefore
fetches category data on that PC and persists only non-sensitive category
metadata to the shared PostgreSQL database.
"""

import argparse
import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Iterable

import requests
from psycopg.types.json import Jsonb

from scripts.db_config import connect_db
from scripts.listing.keepa_product_client import load_keepa_api_key


KEEPA_CATEGORY_ENDPOINT = "https://api.keepa.com/category"
DOMAIN_ID = 5
MAX_BATCH_SIZE = 10
MAX_CATEGORY_COUNT = 10000
MAX_DEPTH = 20


def batched(values: list[int], size: int = MAX_BATCH_SIZE) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def ensure_catalog_schema(cur: Any) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS keepa_category_catalog (
            domain_id INTEGER NOT NULL,
            category_id BIGINT NOT NULL,
            parent_category_id BIGINT NOT NULL DEFAULT 0,
            root_category_id BIGINT NOT NULL,
            depth INTEGER NOT NULL DEFAULT 0,
            category_name TEXT NOT NULL DEFAULT '',
            website_display_group TEXT NOT NULL DEFAULT '',
            is_browse_node BOOLEAN NOT NULL DEFAULT TRUE,
            child_category_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (domain_id, category_id)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS keepa_category_catalog_root_idx
        ON keepa_category_catalog (domain_id, root_category_id, depth, category_name)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS keepa_category_catalog_sync_state (
            domain_id INTEGER NOT NULL,
            root_category_id BIGINT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            category_count INTEGER NOT NULL DEFAULT 0,
            complete BOOLEAN NOT NULL DEFAULT FALSE,
            error_message TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (domain_id, root_category_id)
        )
        """
    )


def request_categories(session: requests.Session, api_key: str, category_ids: list[int]) -> dict[str, Any]:
    for attempt in range(4):
        response = session.get(
            KEEPA_CATEGORY_ENDPOINT,
            params={
                "key": api_key,
                "domain": DOMAIN_ID,
                "category": ",".join(str(item) for item in category_ids),
                "parents": 0,
            },
            timeout=45,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_response": response.text[:1000]}
        if response.status_code == 429 and attempt < 3:
            wait_seconds = min(max(float(payload.get("refillIn") or 5000) / 1000, 2), 30)
            print(f"KEEPA_CATEGORY_CATALOG_WAIT seconds={wait_seconds:g}", flush=True)
            time.sleep(wait_seconds)
            continue
        if not response.ok:
            detail = payload.get("error") or payload.get("errorMessage") or payload.get("raw_response") or ""
            raise RuntimeError(f"Keepa category API rejected request: HTTP {response.status_code} {detail}".strip())
        return payload
    raise RuntimeError("Keepa category API rate limit retry exhausted")


def normalized_category_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_categories = payload.get("categories") or {}
    if not isinstance(raw_categories, dict):
        return []
    rows: list[dict[str, Any]] = []
    for raw in raw_categories.values():
        if not isinstance(raw, dict):
            continue
        try:
            category_id = int(raw.get("catId"))
            parent_id = int(raw.get("parent") or 0)
        except (TypeError, ValueError):
            continue
        if category_id <= 0:
            continue
        children: list[int] = []
        for child in raw.get("children") or []:
            try:
                child_id = int(child)
            except (TypeError, ValueError):
                continue
            if child_id > 0:
                children.append(child_id)
        rows.append(
            {
                "category_id": category_id,
                "parent_category_id": parent_id,
                "category_name": str(raw.get("name") or "").strip(),
                "website_display_group": str(raw.get("websiteDisplayGroup") or "").strip(),
                "is_browse_node": bool(raw.get("isBrowseNode", True)),
                "child_category_ids": list(dict.fromkeys(children)),
            }
        )
    return rows


def save_rows(rows: list[dict[str, Any]], root_category_id: int, depths: dict[int, int]) -> None:
    if not rows:
        return
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_catalog_schema(cur)
                for row in rows:
                    category_id = int(row["category_id"])
                    row_root_id = category_id if root_category_id == 0 else root_category_id
                    cur.execute(
                        """
                        INSERT INTO keepa_category_catalog (
                            domain_id, category_id, parent_category_id, root_category_id,
                            depth, category_name, website_display_group, is_browse_node,
                            child_category_ids, fetched_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (domain_id, category_id) DO UPDATE SET
                            parent_category_id = EXCLUDED.parent_category_id,
                            root_category_id = EXCLUDED.root_category_id,
                            depth = EXCLUDED.depth,
                            category_name = EXCLUDED.category_name,
                            website_display_group = EXCLUDED.website_display_group,
                            is_browse_node = EXCLUDED.is_browse_node,
                            child_category_ids = EXCLUDED.child_category_ids,
                            fetched_at = CURRENT_TIMESTAMP
                        """,
                        (
                            DOMAIN_ID,
                            category_id,
                            int(row["parent_category_id"]),
                            row_root_id,
                            int(depths.get(category_id, 0 if root_category_id == 0 else 1)),
                            row["category_name"],
                            row["website_display_group"],
                            row["is_browse_node"],
                            Jsonb(row["child_category_ids"]),
                        ),
                    )
    finally:
        conn.close()


def save_sync_state(root_category_id: int, *, status: str, category_count: int, complete: bool, error_message: str = "") -> None:
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_catalog_schema(cur)
                cur.execute(
                    """
                    INSERT INTO keepa_category_catalog_sync_state (
                        domain_id, root_category_id, status, category_count, complete, error_message, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (domain_id, root_category_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        category_count = EXCLUDED.category_count,
                        complete = EXCLUDED.complete,
                        error_message = EXCLUDED.error_message,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (DOMAIN_ID, root_category_id, status, category_count, complete, error_message[:1000]),
                )
    finally:
        conn.close()


def sync_root_categories(session: requests.Session, api_key: str) -> dict[str, Any]:
    payload = request_categories(session, api_key, [0])
    rows = normalized_category_rows(payload)
    save_rows(rows, 0, {int(row["category_id"]): 0 for row in rows})
    save_sync_state(0, status="completed", category_count=len(rows), complete=True)
    return {
        "root_category_id": 0,
        "category_count": len(rows),
        "complete": True,
        "tokens": {key: payload.get(key) for key in ("tokensLeft", "tokensConsumed", "refillRate", "refillIn") if key in payload},
    }


def sync_category_tree(session: requests.Session, api_key: str, root_category_id: int, max_categories: int, max_depth: int) -> dict[str, Any]:
    pending: deque[int] = deque([root_category_id])
    requested: set[int] = set()
    saved: set[int] = set()
    depths: dict[int, int] = {root_category_id: 0}
    last_tokens: dict[str, Any] = {}
    complete = True
    save_sync_state(root_category_id, status="running", category_count=0, complete=False)
    while pending:
        batch: list[int] = []
        while pending and len(batch) < MAX_BATCH_SIZE:
            category_id = pending.popleft()
            if category_id in requested:
                continue
            if len(requested) >= max_categories:
                complete = False
                pending.clear()
                break
            requested.add(category_id)
            batch.append(category_id)
        if not batch:
            break
        payload = request_categories(session, api_key, batch)
        last_tokens = {key: payload.get(key) for key in ("tokensLeft", "tokensConsumed", "refillRate", "refillIn") if key in payload}
        rows = normalized_category_rows(payload)
        for row in rows:
            category_id = int(row["category_id"])
            current_depth = depths.get(category_id, 0 if category_id == root_category_id else 1)
            depths[category_id] = current_depth
            if current_depth >= max_depth:
                if row["child_category_ids"]:
                    complete = False
                continue
            for child_id in row["child_category_ids"]:
                if child_id not in requested:
                    depths.setdefault(child_id, current_depth + 1)
                    pending.append(child_id)
        save_rows(rows, root_category_id, depths)
        saved.update(int(row["category_id"]) for row in rows)
        print(
            "KEEPA_CATEGORY_CATALOG_PROGRESS "
            + json.dumps(
                {
                    "root_category_id": root_category_id,
                    "cached_category_count": len(saved),
                    "pending_category_count": len(pending),
                    "complete": complete,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    save_sync_state(root_category_id, status="completed", category_count=len(saved), complete=complete)
    return {
        "root_category_id": root_category_id,
        "category_count": len(saved),
        "complete": complete,
        "max_categories": max_categories,
        "max_depth": max_depth,
        "tokens": last_tokens,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache Keepa Amazon category data for the Product Finder UI")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--root-category", type=int, default=0)
    parser.add_argument("--max-categories", type=int, default=MAX_CATEGORY_COUNT)
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH)
    args = parser.parse_args()
    if args.root_category < 0:
        raise ValueError("root-category must be 0 or a positive Amazon category ID")
    if args.max_categories < 1 or args.max_categories > MAX_CATEGORY_COUNT:
        raise ValueError(f"max-categories must be 1 to {MAX_CATEGORY_COUNT}")
    if args.max_depth < 1 or args.max_depth > MAX_DEPTH:
        raise ValueError(f"max-depth must be 1 to {MAX_DEPTH}")
    return args


def main() -> int:
    args = parse_args()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(
        "KEEPA_CATEGORY_CATALOG_START "
        + json.dumps(
            {"run_id": args.run_id, "store": args.store, "root_category_id": args.root_category},
            ensure_ascii=False,
        ),
        flush=True,
    )
    session = requests.Session()
    api_key = load_keepa_api_key()
    if args.root_category == 0:
        result = sync_root_categories(session, api_key)
    else:
        result = sync_category_tree(session, api_key, args.root_category, args.max_categories, args.max_depth)
    result.update({"run_id": args.run_id, "store": args.store, "started_at": started_at})
    print("KEEPA_CATEGORY_CATALOG_RESULT " + json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"KEEPA_CATEGORY_CATALOG_ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
