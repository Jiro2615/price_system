"""Audit existing listings that now conflict with prohibited-word rules.

The audit is deliberately non-destructive.  It finds active Rakuten listings
whose stored title matches the current prohibited-word master, confirms the
same-JAN public Rakuten listing count, and stores only verified 0..N-1 results
as normal deletion candidates.  RMS items are not touched here; the operator
must still approve candidates and start the existing deletion workflow.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.db_config import connect_db
from scripts.listing.listing_master_db import load_database_master_snapshot
from scripts.listing.prohibited_word_masking import analyze_prohibited_word_issues
from scripts.listing.rakuten_marketplace_policy import rakuten_listing_count_for_jan


SOURCE_TYPE = "prohibited_same_jan_audit"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "compliance_updates"


def ensure_candidate_table(cur) -> None:
    """Keep the existing guarded deletion queue compatible with audit rows."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_delete_candidates (
            candidate_id BIGSERIAL PRIMARY KEY,
            source_type TEXT NOT NULL DEFAULT 'manual_delete_plan',
            run_id TEXT REFERENCES job_runs(run_id) ON DELETE SET NULL,
            store_id BIGINT REFERENCES stores(id) ON DELETE SET NULL,
            store_code TEXT NOT NULL DEFAULT '',
            asin TEXT NOT NULL,
            mall_item_code TEXT NOT NULL DEFAULT '',
            sku_code TEXT NOT NULL DEFAULT '',
            item_name TEXT NOT NULL DEFAULT '',
            reason_type TEXT NOT NULL DEFAULT '',
            matched_value TEXT NOT NULL DEFAULT '',
            reason_detail TEXT NOT NULL DEFAULT '',
            plan_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            candidate_status TEXT NOT NULL DEFAULT 'candidate',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_listing_delete_candidates_status
                CHECK (candidate_status IN ('candidate', 'approved', 'ignored', 'executed', 'failed')),
            CONSTRAINT chk_listing_delete_candidates_source
                CHECK (source_type IN ('manual_delete_plan', 'blacklist_added', 'prohibited_keyword_added', 'prohibited_same_jan_audit'))
        )
        """
    )
    # Existing installations have the older three-value check constraint.
    cur.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'listing_delete_candidates'::regclass
          AND conname = 'chk_listing_delete_candidates_source'
        """
    )
    source_constraint = str((cur.fetchone() or [""])[0] or "")
    if "prohibited_same_jan_audit" not in source_constraint:
        cur.execute("ALTER TABLE listing_delete_candidates DROP CONSTRAINT IF EXISTS chk_listing_delete_candidates_source")
        cur.execute(
            """
            ALTER TABLE listing_delete_candidates
            ADD CONSTRAINT chk_listing_delete_candidates_source
            CHECK (source_type IN ('manual_delete_plan', 'blacklist_added', 'prohibited_keyword_added', 'prohibited_same_jan_audit'))
            """
        )


def active_products(store_code: str) -> list[dict[str, Any]]:
    conn = connect_db(options="-c default_transaction_read_only=on")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.store_code, sp.asin, sp.mall_item_code, sp.sku_code,
                       sp.item_name, sp.rakuten_image_url, ap.jan_code
                FROM store_products sp
                JOIN stores s ON s.id = sp.store_id
                LEFT JOIN amazon_products ap ON ap.asin = sp.asin
                WHERE LOWER(s.store_code) = LOWER(%s)
                  AND sp.enabled = TRUE
                  AND COALESCE(sp.force_stop, FALSE) = FALSE
                  AND COALESCE(sp.current_status, '') NOT IN ('deleted', 'delete_pending', 'rms_deleted')
                  AND COALESCE(sp.mall_item_code, '') <> ''
                ORDER BY sp.id
                """,
                (store_code,),
            )
            keys = ("store_id", "store_code", "asin", "mall_item_code", "sku_code", "item_name", "image_url", "jan_code")
            return [dict(zip(keys, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def words_by_initial(words: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for word in words:
        value = str(word or "").strip()
        if value:
            grouped[value[0]].append(value)
    return grouped


def title_may_match_prohibited_word(title: str, grouped_words: dict[str, list[str]]) -> bool:
    """Cheap prefilter before the canonical allowed-phrase-aware matcher."""
    text = str(title or "")
    for character in set(text):
        if any(word in text for word in grouped_words.get(character, ())):
            return True
    return False


def matched_words_for_title(title: str, snapshot: Any, grouped_words: dict[str, list[str]]) -> list[str]:
    if not title_may_match_prohibited_word(title, grouped_words):
        return []
    analysis = analyze_prohibited_word_issues(
        {"title": title},
        list(dict.fromkeys(list(snapshot.prohibited_rakuten) + list(snapshot.prohibited_other))),
        snapshot.allowed_phrase_rules,
        separate_check_rules=snapshot.allowed_phrase_separate_checks,
    )
    return list(dict.fromkeys(str(item.get("word") or "").strip() for item in analysis["matched_forbidden_words"] if str(item.get("word") or "").strip()))


def save_candidate(cur, run_id: str, row: dict[str, Any], words: list[str], same_jan_count: int, minimum_listings: int) -> int:
    detail = f"楽天同一JANの在庫あり・送料込み商品: {same_jan_count}件（出品許可基準: {minimum_listings}件以上）"
    plan = {
        **row,
        "matched_prohibited_words": words,
        "same_jan_listing_count": same_jan_count,
        "minimum_same_jan_listings": minimum_listings,
        "reasons": [{"type": "prohibited_word_same_jan_under_threshold", "matched_value": ", ".join(words), "detail": detail}],
        "action_plan": {
            "rakuten_item": True,
            "rakuten_images": bool(row.get("image_url")),
            "db_soft_delete": True,
            "api_execute_enabled": False,
            "db_execute_enabled": False,
        },
    }
    cur.execute(
        """
        INSERT INTO listing_delete_candidates (
            source_type, run_id, store_id, store_code, asin, mall_item_code,
            sku_code, item_name, reason_type, matched_value, reason_detail, plan_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING candidate_id
        """,
        (
            SOURCE_TYPE, run_id, row["store_id"], row["store_code"], row["asin"], row["mall_item_code"],
            row.get("sku_code") or "", row.get("item_name") or "", "prohibited_word_same_jan_under_threshold",
            ", ".join(words), detail, Jsonb(plan),
        ),
    )
    return int(cur.fetchone()[0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--minimum-listings", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="0 scans all active products")
    parser.add_argument("--request-interval", type=float, default=1.0)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.minimum_listings < 1:
        raise SystemExit("--minimum-listings must be at least 1")
    if args.limit < 0 or args.request_interval < 0:
        raise SystemExit("--limit and --request-interval must not be negative")

    store_code = str(args.store).strip().lower()
    snapshot = load_database_master_snapshot(store_code)
    if snapshot is None:
        raise SystemExit("禁止語DBが有効ではないため監査を開始しません")
    words = list(dict.fromkeys(list(snapshot.prohibited_rakuten) + list(snapshot.prohibited_other)))
    grouped_words = words_by_initial(words)
    products = active_products(store_code)
    if args.limit:
        products = products[:args.limit]

    summary: dict[str, Any] = {
        "run_id": args.run_id,
        "store_code": store_code,
        "active_product_count": len(products),
        "prohibited_word_count": len(words),
        "title_match_count": 0,
        "api_unavailable_count": 0,
        "threshold_met_count": 0,
        "candidate_count": 0,
        "candidate_ids": [],
    }
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            ensure_candidate_table(cur)
        conn.commit()
        for index, row in enumerate(products, start=1):
            words_matched = matched_words_for_title(str(row.get("item_name") or ""), snapshot, grouped_words)
            if not words_matched:
                continue
            summary["title_match_count"] += 1
            jan_code = str(row.get("jan_code") or "").strip()
            same_jan_count = rakuten_listing_count_for_jan(jan_code) if jan_code else 0
            if same_jan_count is None:
                summary["api_unavailable_count"] += 1
                print("PROHIBITED_LISTING_AUDIT_ITEM " + json.dumps({"index": index, "asin": row["asin"], "status": "api_unavailable"}, ensure_ascii=False), flush=True)
                continue
            if same_jan_count >= args.minimum_listings:
                summary["threshold_met_count"] += 1
                status = "threshold_met"
            else:
                with conn.cursor() as cur:
                    candidate_id = save_candidate(cur, args.run_id, row, words_matched, same_jan_count, args.minimum_listings)
                conn.commit()
                summary["candidate_count"] += 1
                summary["candidate_ids"].append(candidate_id)
                status = "candidate"
            print("PROHIBITED_LISTING_AUDIT_ITEM " + json.dumps({"index": index, "total": len(products), "asin": row["asin"], "same_jan_count": same_jan_count, "status": status}, ensure_ascii=False), flush=True)
            if args.request_interval > 0:
                time.sleep(args.request_interval)
    finally:
        conn.close()

    summary["completed_at"] = datetime.now(timezone.utc).isoformat()
    output_path = args.output_json or DEFAULT_OUTPUT_DIR / f"{args.run_id}_prohibited_listing_audit.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PROHIBITED_LISTING_AUDIT_RESULT " + json.dumps({**summary, "output_json": str(output_path)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
