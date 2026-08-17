from __future__ import annotations

import argparse
import sys
from pathlib import Path

from psycopg.types.json import Jsonb

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.db_config import connect_db
from scripts.listing.listing_master_db import ensure_listing_master_tables, set_database_master_active
from scripts.listing.master_loader import (
    apply_store_allowed_phrase_overrides,
    load_master_data,
    load_category_map,
    load_attribute_definition_records,
    load_word_list,
)


DEFAULT_MASTER_DIR = Path(__file__).resolve().parents[1] / "reference" / "legacy_listing"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy listing masters into PostgreSQL and activate the DB source.")
    parser.add_argument("--master-dir", default=str(DEFAULT_MASTER_DIR))
    parser.add_argument("--apply", action="store_true", help="Write to PostgreSQL. Omit for a read-only count preview.")
    return parser.parse_args()


def records(master_dir: Path) -> dict[str, object]:
    common = load_master_data(master_dir, allow_missing=True)
    store_2 = load_master_data(master_dir, allow_missing=True)
    apply_store_allowed_phrase_overrides(store_2, master_dir, "rakuten_2")
    other_path = master_dir / "kinsiword_other.txt"
    return {
        "blacklist": sorted(common.blacklist),
        "prohibited_rakuten": list(common.prohibited_words_rakuten),
        "prohibited_other": load_word_list(other_path) if other_path.exists() else [],
        "replacements": list(common.replacements),
        "allowed_global": common.allowed_phrase_rules,
        "allowed_store_2": store_2.allowed_phrase_rules,
        "separate_global": common.allowed_phrase_separate_checks,
        "separate_store_2": store_2.allowed_phrase_separate_checks,
        "category_map": load_category_map(master_dir / "catlist_rakuten.txt"),
        "attribute_definitions": load_attribute_definition_records(master_dir / "属性定義書.txt"),
        "manufacturer_warnings": load_word_list(master_dir / "警告ありメーカ.txt"),
    }


def allowed_rows(rules: dict[str, list[str]], checks: dict[str, list[dict]], *, store_id: int | None) -> list[tuple]:
    rows: list[tuple] = []
    scope = "store" if store_id is not None else "global"
    for word, phrases in rules.items():
        for phrase in phrases:
            rows.append((scope, store_id, word, phrase, Jsonb(checks.get(phrase, [])), "legacy import"))
    return rows


def main() -> int:
    args = parse_args()
    data = records(Path(args.master_dir))
    global_allowed = allowed_rows(data["allowed_global"], data["separate_global"], store_id=None)
    store_2_only = {
        word: [phrase for phrase in phrases if phrase not in data["allowed_global"].get(word, [])]
        for word, phrases in data["allowed_store_2"].items()
    }
    summary = {
        "blacklist": len(data["blacklist"]),
        "prohibited_rakuten": len(data["prohibited_rakuten"]),
        "prohibited_other": len(data["prohibited_other"]),
        "replacements": len(data["replacements"]),
        "allowed_global": len(global_allowed),
        "allowed_rakuten_2": sum(len(values) for values in store_2_only.values()),
        "category_map": len(data["category_map"]),
        "attribute_genres": len(data["attribute_definitions"][0]), "manufacturer_warnings": len(data["manufacturer_warnings"]),
    }
    print(summary)
    if not args.apply:
        print("Preview only. Re-run with --apply to import and activate PostgreSQL masters.")
        return 0

    with connect_db() as conn, conn.cursor() as cur:
        ensure_listing_master_tables(cur)
        cur.execute("SELECT id FROM stores WHERE LOWER(store_code) = 'rakuten_2'")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("store rakuten_2 was not found in stores")
        store_2_id = row[0]
        cur.executemany(
            "INSERT INTO blacklist_entries (scope, store_id, entry_type, entry_value, reason, note) VALUES ('global', NULL, 'asin', %s, 'legacy import', 'legacy import') ON CONFLICT DO NOTHING",
            [(value,) for value in data["blacklist"]],
        )
        for rule_set, words in (("rakuten", data["prohibited_rakuten"]), ("other", data["prohibited_other"])):
            cur.executemany(
                "INSERT INTO prohibited_keywords (scope, store_id, keyword, match_mode, severity, listing_rule_set, note) VALUES ('global', NULL, %s, 'contains', 'block', %s, 'legacy import') ON CONFLICT DO NOTHING",
                [(word, rule_set) for word in words],
            )
        cur.executemany(
            "INSERT INTO word_replacements (scope, store_id, target_field, source_text, replacement_text, priority, note) VALUES ('global', NULL, 'all', %s, %s, 100, 'legacy import') ON CONFLICT DO NOTHING",
            data["replacements"],
        )
        cur.executemany(
            "INSERT INTO listing_allowed_phrases (scope, store_id, forbidden_word, allowed_phrase, separate_checks, note) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            global_allowed,
        )
        cur.executemany(
            "INSERT INTO listing_allowed_phrases (scope, store_id, forbidden_word, allowed_phrase, separate_checks, note) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            allowed_rows(store_2_only, data["separate_store_2"], store_id=store_2_id),
        )
        # Past NG is operational history, not a reusable master.  It starts
        # empty and is accumulated per store by the current listing workflow.
        cur.executemany("INSERT INTO listing_category_maps (keepa_category_id, rakuten_genre_id) VALUES (%s,%s) ON CONFLICT (keepa_category_id) DO UPDATE SET rakuten_genre_id=EXCLUDED.rakuten_genre_id, enabled=TRUE, updated_at=CURRENT_TIMESTAMP", list(data["category_map"].items()))
        attributes, paths = data["attribute_definitions"]
        attribute_rows = [(genre, index, name, paths.get(genre, "")) for genre, names in attributes.items() for index, name in enumerate(names, start=1)]
        cur.executemany("INSERT INTO listing_genre_attributes (genre_id, attribute_order, attribute_name, genre_path) VALUES (%s,%s,%s,%s) ON CONFLICT (genre_id, attribute_order) DO UPDATE SET attribute_name=EXCLUDED.attribute_name, genre_path=EXCLUDED.genre_path, enabled=TRUE, updated_at=CURRENT_TIMESTAMP", attribute_rows)
        cur.executemany("INSERT INTO prohibited_keywords (scope, store_id, keyword, match_mode, severity, listing_rule_set, note) VALUES ('global', NULL, %s, 'contains', 'block', 'rakuten', 'legacy manufacturer warning') ON CONFLICT DO NOTHING", [(word,) for word in data["manufacturer_warnings"]])
        set_database_master_active(cur, summary)
    print("Imported and activated PostgreSQL listing masters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
