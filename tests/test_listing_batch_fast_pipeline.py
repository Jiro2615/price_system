"""Fake-only batch integration: all external/DB access is forbidden."""
import asyncio
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from scripts import rakuten_listing_batch_dry_run as dry_batch
from scripts import rakuten_listing_batch_execute as execute_batch
from scripts.listing.models import MasterData, ListingCommonSettings


def arguments(folder):
    return SimpleNamespace(
        store="shop", master_dir=Path("masters"), output_dir=Path(folder),
        allow_missing_master=True, prepare_workers=2, ignore_rules="", bypass_rules=(),
        require_minimum_same_jan_listings=False, page_timeout=100,
        execute=True, approved=True, confirm_real_api=True, allow_live_transport=True,
        max_execute=10000, update_existing=False,
    )


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_batches_reject_all_without_browser_keepa_or_rms(self):
        for module in (dry_batch, execute_batch):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                stack.enter_context(patch("psycopg.connect", side_effect=AssertionError("DB forbidden")))
                stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")))
                cache = stack.enter_context(patch.object(module, "BatchLocalData"))
                def reject(request, **kwargs):
                    self.assertIs(kwargs["batch_local_data"], cache.return_value)
                    return {"asin": request.asin, "listing_status": "business_ng", "execution_allowed": False}
                stack.enter_context(patch.object(module, "precheck_local_listing_exclusion", side_effect=reject))
                browser = stack.enter_context(patch.object(module, "create_amazon_page", new_callable=AsyncMock))
                keepa = stack.enter_context(patch.object(module, "precheck_keepa_before_amazon", side_effect=AssertionError("Keepa forbidden")))
                if module is execute_batch:
                    rms = stack.enter_context(patch.object(module, "build_real_execute_result", side_effect=AssertionError("RMS forbidden")))
                asins = [f"B{i:09}" for i in range(151)]
                result = await asyncio.wait_for(module.run_batch(arguments(folder), asins), timeout=5)
                self.assertEqual(result, 0)
                browser.assert_not_awaited(); keepa.assert_not_called()
                if module is execute_batch:
                    rms.assert_not_called()
                rows = [json.loads(line) for line in (Path(folder) / "results.jsonl").read_text().splitlines()]
                self.assertEqual(len(rows), len(asins))
                self.assertEqual({row["asin"] for row in rows}, set(asins))

    async def test_new_rule_or_db_failure_at_final_gate_prevents_live_execution(self):
        for error in (False, True):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                module = execute_batch
                stack.enter_context(patch("psycopg.connect", side_effect=AssertionError("DB forbidden")))
                stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")))
                cache = stack.enter_context(patch.object(module, "BatchLocalData"))
                stack.enter_context(patch.object(module, "precheck_local_listing_exclusion", return_value=None))
                keepa = stack.enter_context(patch.object(module, "precheck_keepa_before_amazon", return_value=(None, "keepa")))
                context = SimpleNamespace(new_page=AsyncMock(return_value="page2"))
                stack.enter_context(patch.object(module, "create_amazon_page", new_callable=AsyncMock,
                                                 return_value=(None, None, context, "page1")))
                stack.enter_context(patch.object(module, "fetch_amazon_result", new_callable=AsyncMock, return_value="amazon"))
                prepared = stack.enter_context(patch.object(module, "prepare_listing", return_value={
                    "asin": "B000TEST01", "listing_status": "eligible", "management_number": "item",
                    "amazon_result": "amazon", "keepa_result": "keepa",
                }))
                guard = stack.enter_context(patch.object(module, "revalidate_prepared_listing",
                    side_effect=RuntimeError("DB down") if error else None,
                    return_value={"asin": "B000TEST01", "listing_status": "business_ng", "listing_reason": "new blacklist"}))
                rms = stack.enter_context(patch.object(module, "build_real_execute_result", side_effect=AssertionError("RMS forbidden")))
                sync = stack.enter_context(patch.object(module, "sync_listing_result_to_db", side_effect=AssertionError("DB write forbidden")))
                await asyncio.wait_for(module.run_batch(arguments(folder), ["B000TEST01"]), timeout=5)
                self.assertIs(keepa.call_args.kwargs["prepare_kwargs"]["batch_local_data"], cache.return_value)
                self.assertIs(prepared.call_args.kwargs["batch_local_data"], cache.return_value)
                guard.assert_called_once(); rms.assert_not_called(); sync.assert_not_called()
                row = json.loads((Path(folder) / "results.jsonl").read_text())
                self.assertEqual(row["final_status"], "system_error" if error else "business_ng")


class RevalidationTests(unittest.TestCase):
    def test_real_preparation_reads_new_db_blacklist_without_old_files(self):
        latest = MasterData({"B000TEST01"}, {}, [], [], [], {}, {}, {})
        store = SimpleNamespace(store_code="shop")
        with ExitStack() as stack:
            stack.enter_context(patch("psycopg.connect", side_effect=AssertionError("Live DB forbidden")))
            stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("Live HTTP forbidden")))
            load = stack.enter_context(patch("scripts.listing.master_loader.load_active_master_data", return_value=latest))
            stack.enter_context(patch("scripts.listing.master_loader.load_master_data", side_effect=AssertionError("Old files forbidden")))
            stack.enter_context(patch("scripts.listing.prepare_service._resolve_store_settings", return_value=store))
            stack.enter_context(patch("scripts.listing.prepare_service.load_listing_common_settings", return_value=(ListingCommonSettings(3.5), [])))
            stack.enter_context(patch("scripts.listing.prepare_service.apply_asin_master_overrides", side_effect=lambda data, *_: data))
            stack.enter_context(patch("scripts.listing.listing_duplicate_check.find_existing_listing", return_value=None))
            stack.enter_context(patch("scripts.listing.prepare_service._base_result", side_effect=lambda **kwargs: kwargs))
            result = execute_batch.revalidate_prepared_listing(arguments("unused"), "B000TEST01", {
                "management_number": "item", "amazon_result": object(), "keepa_result": object(),
            })
        self.assertEqual(result["listing_status"], "business_ng")
        self.assertEqual(result["listing_reason"], "ブラックリスト")
        load.assert_called_once()

    def test_final_prepare_does_not_receive_cache_or_refetch_observations(self):
        amazon, keepa = object(), object()
        args = arguments("unused")
        args.update_existing = True
        args.bypass_rules = ("blacklist",)
        with patch.object(execute_batch, "prepare_listing", return_value={"listing_status": "eligible"}) as prepare:
            execute_batch.revalidate_prepared_listing(args, "B000TEST01", {
                "management_number": "same-item", "amazon_result": amazon, "keepa_result": keepa,
            })
        request = prepare.call_args.args[0]
        self.assertTrue(request.update_existing)
        self.assertEqual(request.bypass_rules, ("blacklist",))
        self.assertEqual(request.management_number, "same-item")
        self.assertNotIn("batch_local_data", prepare.call_args.kwargs)
        self.assertIs(prepare.call_args.kwargs["amazon_fetcher"]("B000TEST01", 100), amazon)
        self.assertIs(prepare.call_args.kwargs["keepa_fetcher"]("B000TEST01"), keepa)

    def test_missing_observations_fail_closed(self):
        with self.assertRaises(ValueError):
            execute_batch.revalidate_prepared_listing(arguments("unused"), "B000TEST01", {})


if __name__ == "__main__":
    unittest.main()
