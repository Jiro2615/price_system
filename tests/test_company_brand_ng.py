"""Durable exclusion tests using mocks/private SQLite only. No live DB/API."""
from contextlib import ExitStack
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import MagicMock, Mock, patch

from scripts.listing import forced_word_policy as policy, listing_master_db as master_db
from scripts.listing import prepare_service as prepare, listing_evaluator
from scripts.listing.models import ListingCommonSettings
from tests.test_forced_word_policy import prepared
from tests import test_rakuten_listing_payload as fixture_module

ASIN = "B000TEST01"


class NoLive(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ("psycopg.connect", "requests.sessions.Session.request", "urllib.request.OpenerDirector.open"):
            self.stack.enter_context(patch(target, side_effect=AssertionError("Live access forbidden")))


class RecordingTests(NoLive):
    def block(self, *, word="Foo", group="block", **kwargs):
        return policy.screen_forced_words(prepared("商品 " + word), [word], block_company=True,
                                         review_uncertain=True, groups=("test", {word.lower(): group}), **kwargs)

    def test_records_only_company_matches_and_keeps_diagnostics_once(self):
        dry = self.block()
        save = self.stack.enter_context(patch.object(master_db, "record_rule_based_past_ng"))
        self.assertIs(policy.persist_company_brand_exclusion(dry), dry)
        self.assertTrue(dry["company_brand_ng_recorded"])
        save.assert_called_once()
        self.assertEqual(save.call_args.args[:2], (ASIN, "rakuten_2"))
        self.assertEqual(save.call_args.kwargs, {"source": "company_brand_auto"})
        self.assertIn("Foo", save.call_args.args[2])
        match = save.call_args.args[3][0]
        self.assertEqual((match["group"], match["rule_kind"], match["product_title"]), ("block", "whole_word", "商品 Foo"))
        self.assertIn("field", match)
        policy.persist_company_brand_exclusion(dry)
        save.assert_called_once()

    def test_review_offline_other_ng_substrings_and_invalid_matches_do_not_record(self):
        save = self.stack.enter_context(patch.object(master_db, "record_rule_based_past_ng"))
        policy.persist_company_brand_exclusion(self.block(group="review"))
        policy.persist_company_brand_exclusion(self.block(), offline=True)
        dry = prepared("商品 Foo"); dry.update(listing_status="business_ng", execution_allowed=False)
        dry = policy.screen_forced_words(dry, ["Foo"], block_company=True, groups=("test", {"foo": "block"}))
        policy.persist_company_brand_exclusion(dry)
        policy.persist_company_brand_exclusion(policy.screen_forced_words(prepared("Count"), ["OU"],
            block_company=True, groups=("test", {"ou": "block"})))
        dry = self.block(); dry["forced_word_review"]["matches"][0]["rule_kind"] = "contains"
        # All matches must be invalid to test the positive-evidence guard.
        for match in dry["forced_word_review"]["matches"]: match["rule_kind"] = "contains"
        policy.persist_company_brand_exclusion(dry)
        save.assert_not_called()

    def test_recording_failure_keeps_block_and_visible_warning(self):
        self.stack.enter_context(patch.object(master_db, "record_rule_based_past_ng", side_effect=RuntimeError("private details")))
        result = policy.persist_company_brand_exclusion(self.block())
        self.assertFalse(result["company_brand_ng_recorded"])
        self.assertEqual(result["listing_status"], "company_brand_blocked")
        self.assertFalse(result["execution_allowed"])
        self.assertIn("保存に失敗", result["warnings"][-1])
        self.assertNotIn("private details", result["warnings"][-1])


class EarlyExclusionTests(NoLive):
    def setUp(self):
        super().setUp()
        self.fixture = fixture_module.RakutenListingPhase1Tests(); self.fixture.setUp()
        self.fixture.keepa.avg90_new_offer_count = 4.5
        self.request = prepare.PrepareListingRequest(ASIN, "rakuten_1", Path("unused"), dry_run=True,
                                                     bypass_rules=("past_ng", "blacklist", "prohibited_words"))
        self.stack.enter_context(patch.object(prepare, "load_preparation_masters", return_value=self.fixture.master))
        self.overrides = self.stack.enter_context(patch.object(prepare, "apply_asin_master_overrides", side_effect=lambda m,*_:m))
        self.options = {"store_settings_loader": lambda _: self.fixture.store,
                        "common_settings_loader": lambda _: (ListingCommonSettings(3.5), []),
                        "existing_listing_lookup": lambda *_: None,
                        "amazon_fetcher": Mock(return_value=self.fixture.amazon),
                        "keepa_fetcher": Mock(return_value=self.fixture.keepa)}

    def test_cached_block_precedes_all_external_calls_despite_every_bypass_and_switch_off(self):
        self.fixture.master.company_brand_ng[ASIN] = "company Foo"
        result = prepare.prepare_listing(self.request, **self.options)
        self.assertEqual(result["listing_status"], "company_brand_blocked")
        self.assertTrue(result["company_brand_ng_cached"])
        local = {k:v for k,v in self.options.items() if k.endswith("loader") or k == "existing_listing_lookup"}
        result = prepare.precheck_local_listing_exclusion(self.request, **local)
        self.assertEqual(result["listing_status"], "company_brand_blocked")
        keepa = Mock(side_effect=AssertionError("Keepa must not run"))
        result, observation = prepare.precheck_keepa_before_amazon(self.request, keepa_fetcher=keepa, prepare_kwargs=local)
        self.assertEqual(result["listing_status"], "company_brand_blocked")
        self.assertIsNone(observation)
        keepa.assert_not_called(); self.overrides.assert_not_called()
        self.options["amazon_fetcher"].assert_not_called(); self.options["keepa_fetcher"].assert_not_called()
        # Direct evaluation has the same non-bypassable gate.
        result = listing_evaluator.evaluate_listing(asin=ASIN, amazon_result=None, keepa_result=None,
            master_data=self.fixture.master, store_settings=self.fixture.store, management_number="x", bypass_rules={"past_ng"})
        self.assertEqual(result.listing_status, "company_brand_blocked")

    def test_description_only_positive_match_is_saved_at_final_preparation(self):
        self.fixture.master.prohibited_words_rakuten = ["Foo"]
        self.fixture.keepa.features = ["説明 Foo"]
        self.stack.enter_context(patch.object(prepare, "load_groups", return_value=("test", {"foo":"block"})))
        save = self.stack.enter_context(patch.object(master_db, "record_rule_based_past_ng"))
        result = prepare.prepare_listing(replace(self.request, forced_company_brand_block=True), **self.options)
        self.assertEqual(result["listing_status"], "company_brand_blocked", result["listing_reason"])
        self.assertTrue(result["company_brand_ng_recorded"])
        self.assertTrue(all(m["field"].startswith("商品説明") for m in save.call_args.args[3]))


class SnapshotTests(NoLive):
    def test_company_records_are_loaded_with_ordinary_past_ng_setting_off(self):
        conn = MagicMock(); cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [(1,), ("past", "map", "attributes"), (False,)]
        cur.fetchall.side_effect = [[], [], [], [], [(ASIN, "company Foo", "company_brand_auto")], [], []]
        self.stack.enter_context(patch.object(master_db, "database_master_active", return_value=True))
        self.stack.enter_context(patch.object(master_db, "connect_db", return_value=conn))
        snapshot = master_db.load_database_master_snapshot("rakuten_1")
        self.assertEqual(snapshot.company_brand_ng, {ASIN: "company Foo"})
        self.assertEqual(snapshot.kako_ng, {})
        query = next(c for c in cur.execute.call_args_list if "SELECT asin, reason, source" in c.args[0])
        self.assertEqual(query.args[1], (1, "company_brand_auto", False))
        self.assertIn("COALESCE(store_id, 0)", query.args[0])
        self.assertTrue(all(c.args[0].lstrip().startswith("SELECT") for c in cur.execute.call_args_list))

    def test_missing_mapping_tables_do_not_hide_existing_company_ledger(self):
        conn = MagicMock(); cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [(1,), ("past", None, None)]
        cur.fetchall.side_effect = [[], [], [], [], [(ASIN, "company Foo")]]
        self.stack.enter_context(patch.object(master_db, "database_master_active", return_value=True))
        self.stack.enter_context(patch.object(master_db, "connect_db", return_value=conn))
        result = master_db.load_database_master_snapshot("rakuten_1")
        self.assertEqual(result.company_brand_ng, {ASIN:"company Foo"})
        self.assertEqual(result.kako_ng, {})

    def test_direct_ledger_lookup_is_indexed_readonly_scoped_and_fails_closed(self):
        conn = MagicMock(); cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = ("past", "stores")
        cur.fetchall.return_value = [(ASIN, "company Foo")]
        connect = self.stack.enter_context(patch.object(master_db, "connect_db", return_value=conn))
        result = master_db.load_company_brand_ng("rakuten_1", asin=ASIN.lower())
        self.assertEqual(result, {ASIN:"company Foo"})
        connect.assert_called_once_with(options="-c default_transaction_read_only=on")
        query, params = cur.execute.call_args.args
        self.assertEqual(params, ("company_brand_auto","rakuten_1",ASIN))
        self.assertIn("AND png.asin = %s", query)
        for clause in ("png.scope = 'store'", "png.enabled = TRUE", "png.source = %s", "png.store_id IS NOT NULL", "COALESCE(png.store_id, 0)"):
            self.assertIn(clause, query)
        cur.execute.side_effect = RuntimeError("DB unavailable")
        with self.assertRaises(master_db.ListingMasterDatabaseReadError):
            master_db.load_company_brand_ng("rakuten_1", asin=ASIN)

    def test_missing_tables_are_compatible_before_first_ever_record(self):
        conn = MagicMock(); cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = (None, "stores")
        self.stack.enter_context(patch.object(master_db, "connect_db", return_value=conn))
        self.assertEqual(master_db.load_company_brand_ng("rakuten_1"), {})
        self.assertEqual(cur.execute.call_count, 1)


class SqliteCursor:
    def __init__(self, db, *, force_conflict=False):
        self.cursor = db.cursor(); self.force_conflict = force_conflict; self.empty = False
    def __enter__(self): return self
    def __exit__(self, *_): self.cursor.close()
    def execute(self, sql, params=()):
        self.empty = self.force_conflict and sql.startswith("SELECT id FROM listing_past_ng")
        values = [json.dumps(p.obj, ensure_ascii=False) if hasattr(p, "obj") else p for p in params]
        self.cursor.execute(sql.replace("%s", "?"), values)
    def fetchone(self): return None if self.empty else self.cursor.fetchone()


class SqliteConnection:
    def __init__(self, db, force_conflict=False): self.db, self.force_conflict = db, force_conflict
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def cursor(self): return SqliteCursor(self.db, force_conflict=self.force_conflict)
    def commit(self): self.db.commit()


class LedgerWriteSqlTests(NoLive):
    def setUp(self):
        super().setUp()
        self.db = sqlite3.connect(":memory:"); self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE stores (id INTEGER PRIMARY KEY,store_code TEXT);
            INSERT INTO stores VALUES (1,'rakuten_1'),(2,'rakuten_2');
            CREATE TABLE listing_past_ng (id INTEGER PRIMARY KEY,scope TEXT,store_id INTEGER,asin TEXT,
                reason TEXT,matched_rules TEXT,source TEXT,enabled BOOLEAN DEFAULT TRUE,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE UNIQUE INDEX ux ON listing_past_ng(scope,COALESCE(store_id,0),asin);
        """)
        self.connect = self.stack.enter_context(patch.object(master_db, "connect_db", return_value=SqliteConnection(self.db)))
        self.schema = self.stack.enter_context(patch.object(master_db, "ensure_listing_master_tables"))

    def write(self, reason, source="company_brand_auto", store="rakuten_1", asin=ASIN):
        master_db.record_rule_based_past_ng(asin, store, reason, [{"word":"Foo"}], source=source)

    def rows(self): return self.db.execute("SELECT store_id,asin,reason,source,enabled FROM listing_past_ng ORDER BY store_id").fetchall()

    def test_idempotence_store_scope_and_ordinary_ng_cannot_erase_company(self):
        self.write("normal", source="listing_rule_auto")
        self.write("company Foo")
        self.write("ordinary attempt", source="listing_rule_auto")
        self.write("company Foo")
        self.write("company other", store="rakuten_2")
        self.assertEqual(self.rows(), [(1,ASIN,"company Foo","company_brand_auto",1), (2,ASIN,"company other","company_brand_auto",1)])
        self.assertEqual(self.schema.call_count, 2, "Company writes must not add tables/indexes")

    def test_concurrent_insert_conflict_keeps_same_protection(self):
        self.write("company Foo")
        self.connect.return_value = SqliteConnection(self.db, force_conflict=True)
        self.write("normal overwrite", source="listing_rule_auto")
        self.write("updated company Foo")
        self.assertEqual(self.rows(), [(1,ASIN,"updated company Foo","company_brand_auto",1)])

    def test_disabled_company_can_be_released_and_recheck_can_promote_again(self):
        self.write("company Foo")
        self.db.execute("UPDATE listing_past_ng SET enabled=FALSE")
        self.write("normal", source="listing_rule_auto")
        self.assertEqual(self.rows()[0][3:], ("listing_rule_auto",1))
        self.write("company Foo")
        self.assertEqual(self.rows()[0][3:], ("company_brand_auto",1))

    def test_legacy_lowercase_entry_promotes_without_duplicate_and_is_normalized(self):
        self.write("old", source="listing_rule_auto", asin=ASIN.lower())
        self.db.execute("UPDATE listing_past_ng SET asin=LOWER(asin)")
        self.write("company Foo")
        self.assertEqual(self.rows(), [(1,ASIN,"company Foo","company_brand_auto",1)])


if __name__ == "__main__": unittest.main()
