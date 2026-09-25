"""Read-only preview of legacy auto-NG records that need a fresh full check.

Never marks an ASIN eligible, disables past NG, or starts listing jobs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg.rows import dict_row
from scripts.db_config import connect_db
from scripts.listing.listing_text_policy import POLICY_VERSION, WORD_OR_BRAND_TERMS, CONTEXTUAL_CLAIM_TERMS


def is_legacy_policy_recheck_candidate(row: dict) -> bool:
    # This is a recheck candidate, NOT proof that the old result was wrong.
    # Partial saved context cannot establish eligibility for an entire product.
    if row.get("source") != "listing_rule_auto" or not row.get("enabled"):
        return False
    matches = row.get("matched_rules")
    if not isinstance(matches, list) or not matches:
        return False
    changed = WORD_OR_BRAND_TERMS | CONTEXTUAL_CLAIM_TERMS
    for match in matches:
        if not isinstance(match, dict) or match.get("word") not in changed:
            return False
        # Any versioned decision is not an unreviewed legacy substring result.
        if match.get("policy_version"):
            return False
    reason = str(row.get("reason") or "")
    return any(reason == f"prohibited word matched: {match['word']}" for match in matches)


def preview(store_code: str) -> dict:
    candidates = []
    checked = 0
    with connect_db(
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
        connect_timeout=10, row_factory=dict_row,
    ) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE LOWER(store_code)=LOWER(%s)", (store_code,))
        store = cur.fetchone()
        if store is None:
            raise ValueError(f"Unknown store: {store_code}")
        cur.execute("""
            SELECT id, asin, reason, matched_rules, source, enabled
            FROM listing_past_ng
            WHERE scope='store' AND store_id=%s AND enabled=TRUE
              AND source='listing_rule_auto'
            ORDER BY id
        """, (store["id"],))
        while rows := cur.fetchmany(1000):
            for row in rows:
                checked += 1
                if is_legacy_policy_recheck_candidate(row):
                    candidates.append({
                        "id": row["id"], "asin": row["asin"], "reason": row["reason"],
                        "words": sorted({match["word"] for match in row["matched_rules"]}),
                        "action": "requires_fresh_full_evaluation_not_auto_eligible",
                    })
    return {
        "store": store_code, "policy_version": POLICY_VERSION, "read_only": True,
        "checked_auto_ng_count": checked, "recheck_candidate_count": len(candidates),
        "past_ng_changed": False, "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True)
    parser.add_argument("--output", type=Path, help="New JSON report path; existing files are never overwritten")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    report = preview(args.store)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
    if args.summary_only or args.output:
        report = {key: value for key, value in report.items() if key != "candidates"}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
