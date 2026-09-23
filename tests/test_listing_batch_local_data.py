"""Offline cache, DB-first loading and exclusion tests. No live connections."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from scripts.listing import master_loader, listing_master_db, listing_duplicate_check
from scripts.listing.batch_local_data import BatchLocalData, LazyAmazonPages
from scripts.listing.models import MasterData, ListingCommonSettings
from scripts.listing.prepare_service import PrepareListingRequest, precheck_local_listing_exclusion, load_preparation_masters


def masters():
    return MasterData(set(), {}, [], [], [], {}, {}, {})


def snapshot():
    return listing_master_db.ListingMasterDbSnapshot(
        {"B000TEST01"}, ["forbidden"], [], [], {}, {},
        {"B000TEST02": "past"}, {1: 2}, {2: ["brand"]}, {2: "genre"},
    )


class NoNetwork(unittest.TestCase):
    def setUp(self):
        # Catch any accidental real access including imported connect aliases.
        for target in ("psycopg.connect", "requests.sessions.Session.request"):
            guard = patch(target, side_effect=AssertionError("Unexpected live access"))
            guard.start()
            self.addCleanup(guard.stop)


class DatabaseFirstTests(NoNetwork):
    def test_active_db_does_not_touch_missing_or_corrupt_legacy_files(self):
        with patch.object(listing_master_db, "load_database_master_snapshot", return_value=snapshot()), \
             patch.object(master_loader, "load_master_data", side_effect=AssertionError("legacy read")), \
             patch.object(Path, "read_text", side_effect=AssertionError("file read")):
            result = master_loader.load_active_master_data(Path("missing"), "shop")
        self.assertEqual(result.blacklist, {"B000TEST01"})
        self.assertEqual(result.kako_ng, {"B000TEST02": "past"})
        self.assertEqual(result.missing_files, [])
        self.assertEqual(result.allowed_phrase_meta["source"], "postgresql")

    def test_unmigrated_db_uses_legacy_without_second_db_read(self):
        value = masters()
        with patch.object(listing_master_db, "load_database_master_snapshot", return_value=None) as db, \
             patch.object(master_loader, "load_master_data", return_value=value) as files, \
             patch.object(master_loader, "apply_store_allowed_phrase_overrides", return_value=value) as overlay:
            self.assertIs(master_loader.load_active_master_data(Path("missing"), "shop", True), value)
        db.assert_called_once_with("shop")
        files.assert_called_once_with(Path("missing"), allow_missing=True)
        self.assertFalse(overlay.call_args.kwargs["use_database"])

    def test_db_failure_never_falls_back_to_old_rules(self):
        with patch.object(listing_master_db, "load_database_master_snapshot", side_effect=RuntimeError("DB down")), \
             patch.object(master_loader, "load_master_data") as files:
            with self.assertRaisesRegex(RuntimeError, "DB down"):
                master_loader.load_active_master_data(Path("missing"), "shop")
        files.assert_not_called()


class CacheTests(NoNetwork):
    def setUp(self):
        super().setUp()
        self.now = 0.0
        self.load = Mock(return_value=masters())
        self.duplicates = Mock(return_value={"B000TEST01": {"management_number": "existing"}})
        self.data = BatchLocalData("shop", Path("masters"), ["B000TEST01", "B000TEST02"],
                                   clock=lambda: self.now, master_loader=self.load, duplicate_loader=self.duplicates)

    def test_thousands_of_membership_checks_load_once(self):
        for _ in range(1000):
            self.data.masters()
            self.assertIsNone(self.data.existing("B000TEST02", "shop"))
        self.load.assert_called_once()
        self.duplicates.assert_called_once()

    def test_parallel_threads_share_single_load(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.data.masters(), range(100)))
        self.load.assert_called_once()

    def test_expiry_picks_up_added_and_removed_rules_and_listings(self):
        self.data.masters(); self.data.existing("B000TEST01", "shop")
        changed = masters(); changed.blacklist.add("B000TEST02")
        self.load.return_value = changed
        self.duplicates.return_value = {}
        self.now = 30
        self.assertIn("B000TEST02", self.data.masters().blacklist)
        self.assertIsNone(self.data.existing("B000TEST01", "shop"))
        self.assertEqual(self.load.call_count, 2)
        self.assertEqual(self.duplicates.call_count, 2)

    def test_expired_failed_refresh_does_not_serve_stale_data(self):
        self.data.masters(); self.now = 31
        self.load.side_effect = RuntimeError("DB down")
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, "DB down"):
                self.data.masters()

    def test_store_and_run_isolation(self):
        self.data.masters()
        other = BatchLocalData("other", Path("masters"), ["B000TEST01"], master_loader=self.load)
        other.masters()
        self.assertEqual(self.load.call_count, 2)
        with self.assertRaises(ValueError):
            self.data.existing("B000TEST01", "other")
        with self.assertRaises(ValueError):
            self.data.existing("B000TEST99", "shop")

    def test_asin_rule_edits_do_not_leak_to_next_item(self):
        self.load.return_value.allowed_phrase_rules = {"word": ["allowed word"]}
        first = self.data.masters()
        first.allowed_phrase_rules["word"].append("ASIN-only")
        self.assertEqual(self.data.masters().allowed_phrase_rules, {"word": ["allowed word"]})

    def test_scope_rejects_offline_other_store_and_path(self):
        request = PrepareListingRequest("B000TEST01", "shop", Path("masters"))
        self.data.validate_scope(request)
        for candidate in (replace(request, offline=True), replace(request, store_code="other"),
                          replace(request, master_dir=Path("other")), replace(request, allow_missing_master=True)):
            with self.assertRaises(ValueError):
                self.data.validate_scope(candidate)


class BulkDuplicateTests(NoNetwork):
    def test_bulk_query_preserves_active_listing_predicates_and_chunks(self):
        conn = MagicMock()
        cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [("B000TEST01", "item", 100, 2, "sku")]
        with patch.object(listing_duplicate_check, "connect_db", return_value=conn):
            found = listing_duplicate_check.find_existing_listings([f"B{i:09}" for i in range(2001)], "shop")
        self.assertEqual(cur.execute.call_count, 3)
        for call in cur.execute.call_args_list:
            sql, values = call.args
            self.assertIn("'delete_pending', 'deleted'", sql)
            self.assertIn("sp.force_stop", sql)
            self.assertIn("sp.enabled", sql)
            self.assertNotIn("execution_history", sql)
            self.assertEqual(values[0], "shop")
            self.assertLessEqual(len(values[1]), 1000)
        self.assertEqual(found["B000TEST01"]["sku_code"], "sku")

    def test_empty_input_makes_no_connection(self):
        with patch.object(listing_duplicate_check, "connect_db") as db:
            self.assertEqual(listing_duplicate_check.find_existing_listings([], "shop"), {})
        db.assert_not_called()


class ExclusionTests(NoNetwork):
    def test_fast_screening_needs_no_per_asin_db_or_phrase_exception(self):
        rules = masters(); rules.blacklist.add("B000TEST02"); rules.kako_ng["B000TEST03"] = "past"
        store = SimpleNamespace(store_code="shop", min_avg90_sellers=3.5)
        settings_loader = Mock(return_value=store)
        common_loader = Mock(return_value=(ListingCommonSettings(min_avg90_new_offer_count=3.5), []))
        data = BatchLocalData("shop", Path("masters"), [f"B000TEST0{i}" for i in range(1, 5)],
                              master_loader=Mock(return_value=rules),
                              duplicate_loader=Mock(return_value={"B000TEST01": {"management_number": "item"}}))
        with patch("scripts.listing.prepare_service._base_result", side_effect=lambda **kwargs: kwargs), \
             patch("scripts.listing.prepare_service.apply_asin_master_overrides", side_effect=AssertionError("ASIN query")):
            results = []
            for i in range(1, 5):
                request = PrepareListingRequest(f"B000TEST0{i}", "shop", Path("masters"))
                results.append(precheck_local_listing_exclusion(request, batch_local_data=data,
                    store_settings_loader=settings_loader, common_settings_loader=common_loader))
            bypass = PrepareListingRequest("B000TEST02", "shop", Path("masters"), bypass_rules=("blacklist",))
            self.assertIsNone(precheck_local_listing_exclusion(bypass, batch_local_data=data,
                store_settings_loader=settings_loader, common_settings_loader=common_loader))
            update = PrepareListingRequest("B000TEST01", "shop", Path("masters"), update_existing=True)
            self.assertIsNone(precheck_local_listing_exclusion(update, batch_local_data=data,
                store_settings_loader=settings_loader, common_settings_loader=common_loader))
        self.assertEqual([r["listing_status"] if r else None for r in results],
                         ["already_listed", "business_ng", "business_ng", None])
        settings_loader.assert_called_once()
        common_loader.assert_called_once()


class LazyBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_browser_until_survivor_then_initialize_once(self):
        context = SimpleNamespace(new_page=AsyncMock(return_value="page2"))
        factory = AsyncMock(return_value=(None, None, context, "page1"))
        pages = LazyAmazonPages(factory, 2)
        factory.assert_not_called()
        result = await asyncio.gather(pages.get(1), pages.get(2))
        self.assertEqual(result, ["page1", "page2"])
        factory.assert_awaited_once()

    async def test_failure_does_not_repeatedly_start_browser(self):
        factory = AsyncMock(side_effect=RuntimeError("broken"))
        pages = LazyAmazonPages(factory, 2)
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                await pages.get(1)
        factory.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
