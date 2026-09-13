import asyncio
import ast
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from scripts import price_check_one_asin_db as checker


class BrowserTests(unittest.TestCase):
    def exercise(self, mode="chrome", fail=False):
        page = object()
        context = MagicMock(new_page=AsyncMock(return_value=page))
        browser = MagicMock(new_context=AsyncMock(return_value=context), close=AsyncMock())
        engine = MagicMock(stop=AsyncMock())
        engine.chromium.launch = AsyncMock(return_value=browser)
        if fail:
            context.new_page.side_effect = RuntimeError("test")
        manager = MagicMock(start=AsyncMock(return_value=engine))
        with patch.object(checker, "async_playwright", return_value=manager):
            if fail:
                with self.assertRaises(RuntimeError):
                    asyncio.run(checker.create_amazon_page(browser_mode=mode))
                browser.close.assert_awaited_once()
                engine.stop.assert_awaited_once()
            else:
                result = asyncio.run(checker.create_amazon_page(browser_mode=mode))
                self.assertIs(result[3], page)
        return engine.chromium.launch.call_args.kwargs

    def test_chrome_default(self):
        opts = self.exercise()
        self.assertEqual(opts["channel"], "chrome")
        self.assertFalse(opts["headless"])

    def test_shell(self):
        self.assertEqual(self.exercise("shell"), {"headless": True})

    def test_partial_launch_cleanup(self):
        self.exercise("shell", fail=True)

    def test_invalid_mode_no_launch(self):
        with patch.object(checker, "async_playwright") as launch:
            with self.assertRaises(ValueError):
                asyncio.run(checker.create_amazon_page(browser_mode="typo"))
            launch.assert_not_called()

    def test_all_reset_paths_preserve_mode(self):
        tree = ast.parse((Path(__file__).parents[1] / "scripts/price_check_from_db.py").read_text(encoding="utf-8-sig"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "create_amazon_page"]
        self.assertEqual(len(calls), 5)
        self.assertTrue(all(any(k.arg == "browser_mode" and ast.unparse(k.value) == "args.browser" for k in n.keywords) for n in calls))

    def test_restart_boundaries(self):
        tree = ast.parse((Path(__file__).parents[1] / "scripts/price_check_from_db.py").read_text(encoding="utf-8-sig"))
        conditions = [n.test for n in ast.walk(tree) if isinstance(n, ast.If) and "% 50" in ast.unparse(n.test)]
        self.assertEqual(len(conditions), 1)
        code = compile(ast.Expression(conditions[0]), "restart_condition", "eval")
        from types import SimpleNamespace
        for mode in ["chrome", "shell"]:
            boundaries = [i for i in range(1, 151) if eval(code, {"args": SimpleNamespace(browser=mode), "idx": i})]
            self.assertEqual(boundaries, [51, 101] if mode == "shell" else [])


if __name__ == "__main__":
    unittest.main()
