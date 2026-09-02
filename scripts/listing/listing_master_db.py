from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from scripts.db_config import connect_db
from scripts.listing.models import MasterData
from scripts.listing.prohibited_word_masking import normalize_allowed_phrase_payload, split_replacement_rules


ACTIVE_SOURCE_KEY = "legacy_listing"


class ListingMasterDatabaseReadError(RuntimeError):
    """The active listing master could not be read from PostgreSQL.

    Listing decisions must fail closed in this case.  Falling back to a local
    legacy file can silently omit a prohibition added in the central UI.
    """


@dataclass
class ListingMasterDbSnapshot:
    blacklist: set[str]
    prohibited_rakuten: list[str]
    prohibited_other: list[str]
    replacements: list[tuple[str, str]]
    allowed_rules: dict[str, list[str]]
    separate_checks: dict[str, list[dict[str, Any]]]
    kako_ng: dict[str, str]
    category_map: dict[int, int]
    attribute_definitions: dict[int, list[str]]
    genre_paths: dict[int, str]


def ensure_listing_master_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS blacklist_entries (
            id BIGSERIAL PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT 'global' CHECK (scope IN ('global', 'store')),
            store_id BIGINT REFERENCES stores(id) ON DELETE CASCADE,
            entry_type TEXT NOT NULL DEFAULT 'asin',
            entry_value TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS prohibited_keywords (
            id BIGSERIAL PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT 'global' CHECK (scope IN ('global', 'store')),
            store_id BIGINT REFERENCES stores(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            match_mode TEXT NOT NULL DEFAULT 'contains',
            severity TEXT NOT NULL DEFAULT 'block',
            listing_rule_set TEXT NOT NULL DEFAULT 'rakuten',
            note TEXT NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("ALTER TABLE prohibited_keywords ADD COLUMN IF NOT EXISTS listing_rule_set TEXT NOT NULL DEFAULT 'rakuten'")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS word_replacements (
            id BIGSERIAL PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT 'global' CHECK (scope IN ('global', 'store')),
            store_id BIGINT REFERENCES stores(id) ON DELETE CASCADE,
            target_field TEXT NOT NULL DEFAULT 'all',
            source_text TEXT NOT NULL,
            replacement_text TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 100,
            note TEXT NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_allowed_phrases (
            id BIGSERIAL PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT 'global' CHECK (scope IN ('global', 'store')),
            store_id BIGINT REFERENCES stores(id) ON DELETE CASCADE,
            forbidden_word TEXT NOT NULL,
            allowed_phrase TEXT NOT NULL,
            separate_checks JSONB NOT NULL DEFAULT '[]'::jsonb,
            note TEXT NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_master_import_state (
            source_key TEXT PRIMARY KEY,
            active BOOLEAN NOT NULL DEFAULT FALSE,
            detail JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_blacklist_entries_rule ON blacklist_entries (scope, COALESCE(store_id, 0), entry_type, LOWER(entry_value))")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_prohibited_keywords_rule ON prohibited_keywords (scope, COALESCE(store_id, 0), listing_rule_set, match_mode, LOWER(keyword))")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_word_replacements_rule ON word_replacements (scope, COALESCE(store_id, 0), target_field, LOWER(source_text))")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_listing_allowed_phrases_rule ON listing_allowed_phrases (scope, COALESCE(store_id, 0), forbidden_word, allowed_phrase)")
    cur.execute("""CREATE TABLE IF NOT EXISTS listing_asin_allowed_phrases (id BIGSERIAL PRIMARY KEY, store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE, asin TEXT NOT NULL, forbidden_word TEXT NOT NULL, allowed_phrase TEXT NOT NULL, keepa_avg90_min NUMERIC(8,2) NOT NULL DEFAULT 3.5, note TEXT NOT NULL DEFAULT '', enabled BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE (store_id, asin, forbidden_word, allowed_phrase), CHECK (keepa_avg90_min >= 3.5))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS listing_past_ng (id BIGSERIAL PRIMARY KEY, scope TEXT NOT NULL DEFAULT 'global' CHECK (scope IN ('global','store')), store_id BIGINT REFERENCES stores(id) ON DELETE CASCADE, asin TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', matched_rules JSONB NOT NULL DEFAULT '[]'::jsonb, source TEXT NOT NULL DEFAULT 'legacy_import', enabled BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_listing_past_ng_scope_asin ON listing_past_ng (scope, COALESCE(store_id, 0), asin)")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_prohibited_word_exceptions (
            id BIGSERIAL PRIMARY KEY,
            store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            asin TEXT NOT NULL,
            management_number TEXT NOT NULL DEFAULT '',
            exception_type TEXT NOT NULL DEFAULT 'same_jan_marketplace',
            matched_words JSONB NOT NULL DEFAULT '[]'::jsonb,
            jan_code TEXT NOT NULL DEFAULT '',
            same_jan_listing_count INTEGER,
            minimum_listing_count INTEGER,
            detail TEXT NOT NULL DEFAULT '',
            occurrence_count INTEGER NOT NULL DEFAULT 1,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (store_id, asin, exception_type)
        )
        """
    )
    cur.execute("""CREATE TABLE IF NOT EXISTS listing_category_maps (keepa_category_id BIGINT PRIMARY KEY, rakuten_genre_id BIGINT NOT NULL, source TEXT NOT NULL DEFAULT 'legacy_import', enabled BOOLEAN NOT NULL DEFAULT TRUE, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS listing_genre_attributes (genre_id BIGINT NOT NULL, attribute_order INTEGER NOT NULL, attribute_name TEXT NOT NULL, genre_path TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'legacy_import', enabled BOOLEAN NOT NULL DEFAULT TRUE, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (genre_id, attribute_order))""")


def database_master_active() -> bool:
    try:
        with connect_db(options="-c default_transaction_read_only=on") as conn, conn.cursor() as cur:
            cur.execute("SELECT active FROM listing_master_import_state WHERE source_key = %s", (ACTIVE_SOURCE_KEY,))
            row = cur.fetchone()
            return bool(row and row[0])
    except Exception as exc:
        raise ListingMasterDatabaseReadError(
            "禁止語DBの状態を取得できませんでした。出品を停止しました: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def load_database_master_snapshot(store_code: str) -> ListingMasterDbSnapshot | None:
    if not database_master_active():
        return None
    try:
        with connect_db(options="-c default_transaction_read_only=on") as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM stores WHERE LOWER(store_code) = LOWER(%s)", (store_code,))
            row = cur.fetchone()
            store_id = row[0] if row else None
            scope_where = "(scope = 'global' OR store_id = %s)"
            cur.execute("SELECT to_regclass('public.listing_past_ng'), to_regclass('public.listing_category_maps'), to_regclass('public.listing_genre_attributes')")
            extended_tables_ready = all(cur.fetchone())
            cur.execute(f"SELECT entry_value FROM blacklist_entries WHERE enabled = TRUE AND entry_type = 'asin' AND {scope_where}", (store_id,))
            blacklist = {str(row[0]).strip().upper() for row in cur.fetchall() if str(row[0]).strip()}
            cur.execute(f"SELECT keyword, listing_rule_set FROM prohibited_keywords WHERE enabled = TRUE AND match_mode = 'contains' AND severity = 'block' AND {scope_where} ORDER BY id", (store_id,))
            prohibited_rakuten: list[str] = []
            prohibited_other: list[str] = []
            for keyword, rule_set in cur.fetchall():
                target = prohibited_other if str(rule_set or 'rakuten') == 'other' else prohibited_rakuten
                value = str(keyword).strip()
                if value and value not in target:
                    target.append(value)
            cur.execute(f"SELECT source_text, replacement_text FROM word_replacements WHERE enabled = TRUE AND target_field = 'all' AND {scope_where} ORDER BY priority, id", (store_id,))
            replacements = [(str(source), str(target)) for source, target in cur.fetchall() if str(source).strip()]
            cur.execute(f"SELECT forbidden_word, allowed_phrase, separate_checks FROM listing_allowed_phrases WHERE enabled = TRUE AND {scope_where} ORDER BY id", (store_id,))
            rules: dict[str, list[str]] = {}
            separate_checks: dict[str, list[dict[str, Any]]] = {}
            for forbidden_word, allowed_phrase, checks in cur.fetchall():
                word = str(forbidden_word).strip()
                phrase = str(allowed_phrase).strip()
                if not word or not phrase:
                    continue
                rules.setdefault(word, []).append(phrase)
                if isinstance(checks, list) and checks:
                    separate_checks.setdefault(phrase, []).extend(check for check in checks if isinstance(check, dict))
            attribute_definitions: dict[int, list[str]] = {}; genre_paths: dict[int, str] = {}
            kako_ng: dict[str, str] = {}; category_map: dict[int, int] = {}
            if extended_tables_ready:
                # Past-NG records are retained even when a store temporarily
                # opts out of using them as a listing exclusion.  The switch is
                # stored with the other store-level operation settings, so the
                # same master data can safely serve multiple Rakuten stores.
                cur.execute(
                    """
                    SELECT COALESCE(
                        NULLIF(ss.order_fulfillment_settings_json->>'listing_past_ng_exclude_enabled', '')::BOOLEAN,
                        TRUE
                    )
                    FROM stores s
                    LEFT JOIN store_settings ss ON ss.store_id = s.id
                    WHERE s.id = %s
                    """,
                    (store_id,),
                )
                setting_row = cur.fetchone()
                past_ng_exclude_enabled = bool(setting_row[0]) if setting_row else True
                if past_ng_exclude_enabled:
                    cur.execute(
                        "SELECT asin, reason FROM listing_past_ng "
                        "WHERE enabled = TRUE AND scope = 'store' AND store_id = %s",
                        (store_id,),
                    )
                    kako_ng = {str(asin).upper(): str(reason or '過去NG') for asin, reason in cur.fetchall()}
                cur.execute("SELECT keepa_category_id, rakuten_genre_id FROM listing_category_maps WHERE enabled = TRUE")
                category_map = {int(source): int(target) for source, target in cur.fetchall()}
                cur.execute("SELECT genre_id, attribute_order, attribute_name, genre_path FROM listing_genre_attributes WHERE enabled = TRUE ORDER BY genre_id, attribute_order")
                for genre_id, _order, name, genre_path in cur.fetchall():
                    attribute_definitions.setdefault(int(genre_id), []).append(str(name)); genre_paths.setdefault(int(genre_id), str(genre_path or ''))
    except ListingMasterDatabaseReadError:
        raise
    except Exception as exc:
        raise ListingMasterDatabaseReadError(
            "禁止語DBを読み込めませんでした。出品を停止しました: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    return ListingMasterDbSnapshot(blacklist, prohibited_rakuten, prohibited_other, replacements, normalize_allowed_phrase_payload(rules)["rules"], separate_checks, kako_ng, category_map, attribute_definitions, genre_paths)


def apply_database_master_snapshot(master_data: MasterData, store_code: str) -> MasterData:
    snapshot = load_database_master_snapshot(store_code)
    if snapshot is None:
        return master_data
    cleanup_replacements, legacy_spacing_replacements = split_replacement_rules(snapshot.replacements, snapshot.prohibited_rakuten)
    master_data.blacklist = snapshot.blacklist
    master_data.prohibited_words_rakuten = snapshot.prohibited_rakuten
    master_data.prohibited_words_other = snapshot.prohibited_other
    master_data.replacements = snapshot.replacements
    master_data.cleanup_replacements = cleanup_replacements
    master_data.legacy_spacing_replacements = legacy_spacing_replacements
    master_data.allowed_phrase_rules = snapshot.allowed_rules
    master_data.allowed_phrase_separate_checks = snapshot.separate_checks
    master_data.allowed_phrase_meta = {**master_data.allowed_phrase_meta, "source": "postgresql"}
    master_data.kako_ng = snapshot.kako_ng
    master_data.category_map = snapshot.category_map
    master_data.attribute_definitions = snapshot.attribute_definitions
    master_data.genre_paths = snapshot.genre_paths
    return master_data


def record_rule_based_past_ng(asin: str, store_code: str, reason: str, matched_rules: list[dict[str, Any]]) -> None:
    if not asin or not reason:
        return
    with connect_db() as conn, conn.cursor() as cur:
        ensure_listing_master_tables(cur)
        cur.execute("SELECT id FROM stores WHERE LOWER(store_code)=LOWER(%s)", (store_code,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"store not found: {store_code}")
        store_id = row[0]
        cur.execute("SELECT id FROM listing_past_ng WHERE scope='store' AND COALESCE(store_id,0)=COALESCE(%s,0) AND UPPER(asin)=UPPER(%s)", (store_id, asin))
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE listing_past_ng SET reason=%s, matched_rules=%s, enabled=TRUE, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (reason, Jsonb(matched_rules), existing[0]))
        else:
            cur.execute("INSERT INTO listing_past_ng (scope, store_id, asin, reason, matched_rules, source) VALUES ('store', %s, %s, %s, %s, 'listing_rule_auto')", (store_id, asin.upper(), reason, Jsonb(matched_rules)))
        conn.commit()


def record_prohibited_word_exceptions(
    *,
    asin: str,
    store_code: str,
    management_number: str,
    exceptions: list[dict[str, Any]],
) -> None:
    """Persist the last exact-JAN exception while retaining an occurrence count."""
    if not asin or not exceptions:
        return
    with connect_db() as conn, conn.cursor() as cur:
        ensure_listing_master_tables(cur)
        cur.execute("SELECT id FROM stores WHERE LOWER(store_code)=LOWER(%s)", (store_code,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"store not found: {store_code}")
        store_id = row[0]
        for exception in exceptions:
            exception_type = str(exception.get("type") or "same_jan_marketplace")
            cur.execute(
                """
                INSERT INTO listing_prohibited_word_exceptions (
                    store_id, asin, management_number, exception_type, matched_words,
                    jan_code, same_jan_listing_count, minimum_listing_count, detail
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (store_id, asin, exception_type) DO UPDATE SET
                    management_number = EXCLUDED.management_number,
                    matched_words = EXCLUDED.matched_words,
                    jan_code = EXCLUDED.jan_code,
                    same_jan_listing_count = EXCLUDED.same_jan_listing_count,
                    minimum_listing_count = EXCLUDED.minimum_listing_count,
                    detail = EXCLUDED.detail,
                    occurrence_count = listing_prohibited_word_exceptions.occurrence_count + 1,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (
                    store_id,
                    asin.upper(),
                    management_number.strip(),
                    exception_type,
                    Jsonb(list(exception.get("matched_words") or [])),
                    str(exception.get("jan_code") or ""),
                    exception.get("same_jan_listing_count"),
                    exception.get("minimum_listing_count"),
                    str(exception.get("message") or ""),
                ),
            )
        conn.commit()


def clear_past_ng_records() -> int:
    """Remove stored past-NG decisions without altering other listing masters."""
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM listing_past_ng")
        deleted = cur.rowcount
        conn.commit()
    return int(deleted)


def apply_asin_allowed_phrase_overrides(master_data: MasterData, store_code: str, asin: str) -> MasterData:
    if not asin:
        return master_data
    with connect_db(options="-c default_transaction_read_only=on") as conn, conn.cursor() as cur:
        cur.execute("SELECT s.id FROM stores s WHERE LOWER(s.store_code) = LOWER(%s)", (store_code,))
        store = cur.fetchone()
        if not store:
            return master_data
        cur.execute("SELECT forbidden_word, allowed_phrase FROM listing_asin_allowed_phrases WHERE store_id = %s AND UPPER(asin) = UPPER(%s) AND enabled = TRUE", (store[0], asin))
        rows = cur.fetchall()
    if not rows:
        return master_data
    merged = {word: list(phrases) for word, phrases in master_data.allowed_phrase_rules.items()}
    for forbidden_word, allowed_phrase in rows:
        word, phrase = str(forbidden_word).strip(), str(allowed_phrase).strip()
        if word and phrase and word in phrase:
            merged.setdefault(word, []).append(phrase)
    master_data.allowed_phrase_rules = normalize_allowed_phrase_payload(merged)["rules"]
    master_data.allowed_phrase_meta = {**master_data.allowed_phrase_meta, "asin_exception_count": len(rows), "asin_exception_asin": asin}
    return master_data


def set_database_master_active(cur, detail: dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO listing_master_import_state (source_key, active, detail)
        VALUES (%s, TRUE, %s)
        ON CONFLICT (source_key) DO UPDATE
        SET active = TRUE, detail = EXCLUDED.detail, updated_at = CURRENT_TIMESTAMP
        """,
        (ACTIVE_SOURCE_KEY, Jsonb(detail)),
    )
