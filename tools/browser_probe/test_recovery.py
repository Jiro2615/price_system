"""Offline regression tests: no browser launch, network or real DB connection."""
import asyncio
from contextlib import ExitStack
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from probe_support import REPO, Meter, atomic_json
from interaction_probe import run, child_exit_code, stop_watcher
from summarize import summarize


class RecoveryTests(unittest.TestCase):
    def test_product_errors_do_not_abort_round(self):
        data = self.fake_run(False)
        self.assertEqual(len(data["cases"]), 3)
        self.assertTrue(all(c.get("error") and not c.get("fatal") for c in data["cases"]))
        self.assertEqual(child_exit_code(data), 0)
        self.assertIsNotNone(data["metrics"])

    def test_caught_challenge_still_stops(self):
        data = self.fake_run(True)
        self.assertEqual(len(data["cases"]), 1)
        self.assertTrue(data["cases"][0]["fatal"])
        self.assertEqual(child_exit_code(data), 1)
        self.assertIsNotNone(data["metrics"])

    def test_single_read_count_and_no_extra_operations(self):
        data = self.fake_run(False, single=True)
        self.assertEqual(len(data["cases"]), 3)
        self.assertEqual([c["index"] for c in data["cases"]], [50, 51, 52])
        self.assertTrue(all(not c.get("error") and "after_navigation" not in c for c in data["cases"]))

    def fake_run(self, authentication, single=False):
        sys.path.insert(0, str(REPO))
        import scripts.price_check_one_asin_db as checker
        page = MagicMock()
        page.url = "about:blank"
        page.is_closed.return_value = False
        page.add_init_script = AsyncMock()
        page.evaluate = AsyncMock(return_value=[])
        page.locator.return_value.inner_text = AsyncMock(return_value="Product")

        async def goto(url, **kwargs):
            page.url = url
        page.goto = goto
        browser = MagicMock()
        browser.version = "test"
        browser.is_connected.return_value = True
        browser.close = AsyncMock()
        ctx = MagicMock()
        ctx.route = AsyncMock()
        ctx.new_page = AsyncMock(return_value=page)
        browser.new_context = AsyncMock(return_value=ctx)
        engine = MagicMock()
        engine.chromium.launch = AsyncMock(return_value=browser)
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=engine)
        manager.__aexit__ = AsyncMock(return_value=False)

        async def check(asin, **kwargs):
            if authentication:
                try:
                    await page.goto("https://www.amazon.co.jp/ap/signin")
                except Exception:
                    pass  # Simulate the production parser swallowing exceptions.
            return {"asin": asin, "system_error": not single,
                    "ng_reason": "ギフト不可（Amazon.co.jp直販例外の未確認）"}

        real_sleep = asyncio.sleep
        async def quick_sleep(delay):
            await real_sleep(0)
        with TemporaryDirectory() as folder, ExitStack() as stack:
            stack.enter_context(patch("playwright.async_api.async_playwright", return_value=manager))
            stack.enter_context(patch.object(checker, "check_amazon_one", side_effect=check))
            stack.enter_context(patch.object(checker, "is_amazon_confirmation_page", return_value=False))
            for target in ("scripts.db_config.connect_db", "psycopg.connect",
                           "scripts.price_check_one_asin_db.connect_db",
                           "scripts.price_check_one_asin_db.save_to_db"):
                stack.enter_context(patch(target))
            stack.enter_context(patch("interaction_probe.asyncio.sleep", new=quick_sleep))
            out = Path(folder) / "round1_chrome.json"
            asyncio.run(run("chrome", out, seconds=-1, case_limit=3 if single else 0, index_offset=50 if single else 0))
            return json.loads(out.read_text(encoding="utf-8"))

    def test_partial_resources_are_recovered_not_complete(self):
        with TemporaryDirectory() as folder:
            folder = Path(folder)
            atomic_json(folder / "machine.json", {"arguments": {"rounds": 1}})
            atomic_json(folder / "round1_shell.json", {"mode": "shell", "cases": []})
            meter = Meter(folder / "round1_shell.resources.json")
            meter.start()
            try:
                checkpoint = json.loads(meter.checkpoint_path.read_text(encoding="utf-8"))
                self.assertGreater(checkpoint["metrics"]["samples"], 0)
                with patch("sys.stdout", new=io.StringIO()):
                    summary = summarize(folder)
                self.assertEqual(summary["observed_runs"], 1)  # Sidecar is not a run.
                self.assertTrue(summary["runs"][0]["metrics_partial"])
                self.assertIsNotNone(summary["runs"][0]["metrics"])
                self.assertFalse(summary["runs"][0]["complete"])
            finally:
                meter.finish()

    def test_explicit_stop_cancels_owner(self):
        async def exercise(folder):
            owner = asyncio.create_task(asyncio.sleep(60))
            await stop_watcher(owner, [folder / "STOP"])
            with self.assertRaises(asyncio.CancelledError):
                await owner
        with TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "STOP").touch()
            asyncio.run(exercise(folder))


if __name__ == "__main__":
    unittest.main()
