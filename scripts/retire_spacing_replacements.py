from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.db_config import connect_db
from scripts.listing.listing_master_db import ensure_listing_master_tables
from scripts.listing.prohibited_word_masking import is_spacing_only_replacement


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move spacing-only replacements into common allowed phrases, then disable them.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Omit for preview only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with connect_db() as conn, conn.cursor() as cur:
        ensure_listing_master_tables(cur)
        cur.execute(
            """
            SELECT id, source_text, replacement_text
            FROM word_replacements
            WHERE enabled = TRUE AND scope = 'global' AND target_field = 'all'
            ORDER BY id
            """
        )
        spacing_rules = [row for row in cur.fetchall() if is_spacing_only_replacement(str(row[1]), str(row[2]))]
        cur.execute(
            """
            SELECT keyword FROM prohibited_keywords
            WHERE enabled = TRUE AND scope = 'global' AND match_mode = 'contains'
              AND severity = 'block' AND listing_rule_set = 'rakuten'
            """
        )
        forbidden_words = [str(row[0]) for row in cur.fetchall() if str(row[0]).strip()]
        allowed_pairs = sorted(
            {
                (word, str(source))
                for _rule_id, source, _target in spacing_rules
                for word in forbidden_words
                if word and word in str(source)
            }
        )
        summary = {
            "spacing_rules": len(spacing_rules),
            "common_allowed_phrase_pairs": len(allowed_pairs),
            "rules_without_current_forbidden_match": len(spacing_rules) - len({rule_id for rule_id, source, _target in spacing_rules if any(word in str(source) for word in forbidden_words)}),
        }
        print(summary)
        if not args.apply:
            print("Preview only. Re-run with --apply to add common allowed phrases and disable spacing replacements.")
            return 0
        cur.executemany(
            """
            INSERT INTO listing_allowed_phrases (scope, store_id, forbidden_word, allowed_phrase, note)
            VALUES ('global', NULL, %s, %s, 'migrated from spacing-only replacement')
            ON CONFLICT DO NOTHING
            """,
            allowed_pairs,
        )
        cur.execute(
            "UPDATE word_replacements SET enabled = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = ANY(%s)",
            ([row[0] for row in spacing_rules],),
        )
    print("Added common allowed phrases and disabled spacing-only replacements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
