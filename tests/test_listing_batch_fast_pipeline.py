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
    async def test_class_edit_while_waiting_for_write_slot_stops_before_any_send(self):
        from tests.test_forced_word_policy import prepared
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            module=execute_batch
            stack.enter_context(patch("psycopg.connect",side_effect=AssertionError("Live DB forbidden")))
            stack.enter_context(patch("requests.sessions.Session.request",side_effect=AssertionError("Live HTTP forbidden")))
            stack.enter_context(patch.object(module,"BatchLocalData"))
            stack.enter_context(patch.object(module,"precheck_local_listing_exclusion",return_value=None))
            stack.enter_context(patch.object(module,"precheck_keepa_before_amazon",return_value=(None,"keepa")))
            stack.enter_context(patch.object(module,"create_amazon_page",new_callable=AsyncMock,
                return_value=(None,None,SimpleNamespace(new_page=AsyncMock(return_value="p2")),"p1")))
            stack.enter_context(patch.object(module,"fetch_amazon_result",new_callable=AsyncMock,return_value="amazon"))
            dry=prepared("商品 OU")
            stack.enter_context(patch.object(module,"prepare_listing",return_value=dry))
            stack.enter_context(patch.object(module,"revalidate_prepared_listing",return_value=dry))
            for name in ("build_preflight_result","build_mock_execute_result","build_real_readiness_result"):
                stack.enter_context(patch.object(module,name,return_value={}))
            stack.enter_context(patch.object(module,"read_active_words",return_value=["OU"]))
            stack.enter_context(patch("scripts.listing.forced_word_classification_db.read_overrides",return_value={"ou":"block"}))
            stack.enter_context(patch.object(module,"run_with_listing_write_slot",side_effect=lambda store,action,**kwargs:action()))
            send=stack.enter_context(patch.object(module,"build_real_execute_result",side_effect=AssertionError("RMS send forbidden")))
            sync=stack.enter_context(patch.object(module,"sync_listing_result_to_db",side_effect=AssertionError("Product DB write forbidden")))
            args=arguments(folder)
            args.store="rakuten_2"
            args.block_forbidden_company_brands=True
            args.review_uncertain_words=True
            await asyncio.wait_for(module.run_batch(args,["B000TEST01"]),timeout=5)
            result=json.loads((Path(folder)/"results.jsonl").read_text())
            self.assertEqual(result["final_status"],"company_brand_blocked")
            self.assertFalse(result["external_actions_performed"])
            send.assert_not_called();sync.assert_not_called()

    async def test_company_and_word_review_holds_never_preflight_upload_or_sync(self):
        for status in ("word_review_pending", "company_brand_blocked"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                module = execute_batch
                stack.enter_context(patch("psycopg.connect", side_effect=AssertionError("Live DB forbidden")))
                stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("Live HTTP forbidden")))
                stack.enter_context(patch.object(module, "BatchLocalData"))
                stack.enter_context(patch.object(module, "precheck_local_listing_exclusion", return_value=None))
                stack.enter_context(patch.object(module, "precheck_keepa_before_amazon", return_value=(None, "keepa")))
                stack.enter_context(patch.object(module, "create_amazon_page", new_callable=AsyncMock,
                    return_value=(None, None, SimpleNamespace(new_page=AsyncMock(return_value="p2")), "p1")))
                stack.enter_context(patch.object(module, "fetch_amazon_result", new_callable=AsyncMock, return_value="amazon"))
                dry = {"asin": "B000TEST01", "listing_status": status, "execution_allowed": False,
                       "forced_word_review": {"state": status, "title": "商品 OU", "matches": [{"word":"OU"}]}}
                if status == "word_review_pending":
                    dry["forced_word_review_cache"] = {"item_payload": {"title": "商品 OU"}}
                prepare = stack.enter_context(patch.object(module, "prepare_listing", return_value=dry))
                forbidden = [stack.enter_context(patch.object(module, name, side_effect=AssertionError(name+" forbidden")))
                    for name in ("revalidate_prepared_listing", "build_preflight_result", "build_real_execute_result", "sync_listing_result_to_db", "run_with_listing_write_slot")]
                args = arguments(folder)
                args.block_forbidden_company_brands = True
                args.review_uncertain_words = True
                await asyncio.wait_for(module.run_batch(args, ["B000TEST01"]), timeout=5)
                request = prepare.call_args.args[0]
                self.assertTrue(request.forced_company_brand_block)
                self.assertTrue(request.forced_word_review_mode)
                for call in forbidden: call.assert_not_called()
                result = json.loads((Path(folder)/"results.jsonl").read_text())
                self.assertEqual(result["final_status"], status)
                self.assertFalse(result["external_actions_performed"])

    async def test_refresh_and_bulk_write_and_db_sync_are_inside_slot(self):
        for refresh in (False, True):
            with self.subTest(refresh=refresh), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                module = execute_batch
                stack.enter_context(patch("psycopg.connect", side_effect=AssertionError("Live DB forbidden")))
                stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden")))
                stack.enter_context(patch.object(module, "BatchLocalData"))
                stack.enter_context(patch.object(module, "precheck_local_listing_exclusion", return_value=None))
                stack.enter_context(patch.object(module, "precheck_keepa_before_amazon", return_value=(None, "keepa")))
                stack.enter_context(patch.object(module, "create_amazon_page", new_callable=AsyncMock,
                    return_value=(None, None, SimpleNamespace(new_page=AsyncMock(return_value="p2")), "p1")))
                stack.enter_context(patch.object(module, "fetch_amazon_result", new_callable=AsyncMock, return_value="amazon"))
                dry = {"asin": "B000TEST01", "listing_status": "eligible", "management_number": "item",
                       "amazon_result": "amazon", "keepa_result": "keepa"}
                stack.enter_context(patch.object(module, "prepare_listing", return_value=dry))
                stack.enter_context(patch.object(module, "revalidate_prepared_listing", return_value=dry))
                for name in ("build_preflight_result", "build_mock_execute_result", "build_real_readiness_result"):
                    stack.enter_context(patch.object(module, name, return_value={}))
                inside = []
                calls = []
                def slot(store, action, *, priority, on_acquired):
                    self.assertEqual(store, "shop"); self.assertEqual(priority, refresh)
                    inside.append(True)
                    try:
                        on_acquired()
                        return action()
                    finally: inside.clear()
                stack.enter_context(patch.object(module, "run_with_listing_write_slot", side_effect=slot))
                def execute(request, **kwargs):
                    self.assertTrue(inside)
                    self.assertEqual(request.content_refresh, refresh)
                    calls.append("rms")
                    return {"final_status": "completed"}
                stack.enter_context(patch.object(module, "build_real_execute_result", side_effect=execute))
                def sync(*_):
                    self.assertTrue(inside); calls.append("db")
                    return {"external_db_writes_performed": True}
                stack.enter_context(patch.object(module, "sync_listing_result_to_db", side_effect=sync))
                args = arguments(folder); args.update_existing = refresh
                await asyncio.wait_for(module.run_batch(args, ["B000TEST01"]), timeout=5)
                self.assertEqual(calls, ["rms"] if refresh else ["rms", "db"])
                row = json.loads((Path(folder) / "results.jsonl").read_text())
                self.assertEqual(row["final_status"], "completed")

    async def test_both_batches_reject_all_without_browser_keepa_or_rms(self):
        for module in (dry_batch, execute_batch):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                stack.enter_context(patch("psycopg.connect", side_effect=AssertionError("DB forbidden")))
                stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")))
                cache = stack.enter_context(patch.object(module, "BatchLocalData"))
                def reject(request, **kwargs):
                    self.assertIs(kwargs["batch_local_data"], cache.return_value)
                    self.assertEqual(request.minimum_rakuten_shops, 3)
                    return {"asin": request.asin, "listing_status": "business_ng", "execution_allowed": False}
                stack.enter_context(patch.object(module, "precheck_local_listing_exclusion", side_effect=reject))
                browser = stack.enter_context(patch.object(module, "create_amazon_page", new_callable=AsyncMock))
                keepa = stack.enter_context(patch.object(module, "precheck_keepa_before_amazon", side_effect=AssertionError("Keepa forbidden")))
                if module is execute_batch:
                    rms = stack.enter_context(patch.object(module, "build_real_execute_result", side_effect=AssertionError("RMS forbidden")))
                asins = [f"B{i:09}" for i in range(151)]
                args = arguments(folder)
                args.minimum_rakuten_shops = 3
                result = await asyncio.wait_for(module.run_batch(args, asins), timeout=5)
                self.assertEqual(result, 0)
                browser.assert_not_awaited(); keepa.assert_not_called()
                if module is execute_batch:
                    rms.assert_not_called()
                rows = [json.loads(line) for line in (Path(folder) / "results.jsonl").read_text().splitlines()]
                self.assertEqual(len(rows), len(asins))
                self.assertEqual({row["asin"] for row in rows}, set(asins))
                summary = json.loads((Path(folder) / "summary.json").read_text())
                self.assertEqual(summary["minimum_rakuten_shops"], 3)

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
    def test_db_worker_capability_argument_is_accepted_without_starting_any_work(self):
        with patch("sys.argv", ["batch", "--asin-file", "unused.txt", "--store", "rakuten_2",
                                "--output-dir", "unused", "--require-shared-word-classifications"]):
            args = execute_batch.parse_args()
        self.assertTrue(args.require_shared_word_classifications)
        self.assertFalse(args.execute)

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
        args.minimum_rakuten_shops = 3
        with patch.object(execute_batch, "prepare_listing", return_value={"listing_status": "eligible"}) as prepare:
            execute_batch.revalidate_prepared_listing(args, "B000TEST01", {
                "management_number": "same-item", "amazon_result": amazon, "keepa_result": keepa,
            })
        request = prepare.call_args.args[0]
        self.assertTrue(request.update_existing)
        self.assertEqual(request.bypass_rules, ("blacklist",))
        self.assertEqual(request.minimum_rakuten_shops, 3)
        self.assertEqual(request.management_number, "same-item")
        self.assertNotIn("batch_local_data", prepare.call_args.kwargs)
        self.assertIs(prepare.call_args.kwargs["amazon_fetcher"]("B000TEST01", 100), amazon)
        self.assertIs(prepare.call_args.kwargs["keepa_fetcher"]("B000TEST01"), keepa)

    def test_missing_observations_fail_closed(self):
        with self.assertRaises(ValueError):
            execute_batch.revalidate_prepared_listing(arguments("unused"), "B000TEST01", {})


if __name__ == "__main__":
    unittest.main()
