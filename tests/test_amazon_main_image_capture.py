"""Exercise just the production DOM reader, without a browser/event loop/DB."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import urlsplit
import unittest
from unittest.mock import AsyncMock

SOURCE = Path(__file__).parents[1]/"scripts/price_check_one_asin_db.py"


def capture(page, asin="B000000001"):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name in {"extract_asin", "capture_main_image"}]
    ns = {"datetime": datetime, "timezone": timezone, "urlsplit": urlsplit, "re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), ns)
    coroutine = ns["capture_main_image"](page, asin)
    try:
        coroutine.send(None)
    except StopIteration as exc:
        return exc.value
    raise AssertionError("Reader must not start timers, navigation, or network")


class CaptureTests(unittest.TestCase):
    def page(self, values):
        return SimpleNamespace(url="https://www.amazon.co.jp/dp/B000000001?th=1", evaluate=AsyncMock(return_value=values))

    def test_selected_main_image_metadata_and_utc(self):
        page = self.page([None, "https://m.media-amazon.com/images/I/main.jpg"])
        result = capture(page)
        self.assertEqual(result["amazon_main_image_url"], "https://m.media-amazon.com/images/I/main.jpg")
        self.assertEqual(result["amazon_main_image_verified_asin"], "B000000001")
        self.assertEqual(result["amazon_main_image_error"], "")
        self.assertEqual(datetime.fromisoformat(result["amazon_main_image_checked_at"]).utcoffset().total_seconds(), 0)
        script = page.evaluate.call_args.args[0]
        self.assertIn("#landingImage", script)
        self.assertIn("#imgBlkFront", script)
        self.assertIn("data-old-hires", script)
        self.assertIn("data-a-dynamic-image", script)
        self.assertNotIn("querySelectorAll('img')", script)

    def test_wrong_or_unverified_asin_is_not_an_observation(self):
        page = self.page([])
        for url in ("https://www.amazon.co.jp/dp/B000000002", "https://www.amazon.co.jp/errors"):
            page.url = url
            self.assertEqual(capture(page), {})
        page.evaluate.assert_not_called()

    def test_invalid_image_urls_and_missing_images_are_not_current_matches(self):
        for urls in ([], ["data:image/png;base64,aa"], ["http://m.media-amazon.com/images/I/main.jpg"],
                     ["https://m.media-amazon.com.evil/images/I/main.jpg"], ["https://evil.invalid/a.jpg"]):
            result = capture(self.page(urls))
            self.assertEqual(result["amazon_main_image_url"], "")
            self.assertEqual(result["amazon_main_image_error"], "main_image_unavailable")

    def test_read_error_does_not_raise_into_price_check(self):
        page = self.page([])
        page.evaluate.side_effect = RuntimeError("frame detached")
        self.assertEqual(capture(page)["amazon_main_image_error"], "main_image_read_failed")

    def test_production_calls_capture_after_identity_check_before_business_ng(self):
        text = SOURCE.read_text(encoding="utf-8")
        start = text.index("async def check_amazon_one(")
        body = text[start:]
        self.assertLess(body.index("await verify_product_identity(page, asin, result)"), body.index("await capture_main_image(page, asin)"))
        self.assertLess(body.index("await capture_main_image(page, asin)"), body.index('out_of_stock_text ='))


if __name__ == "__main__":
    unittest.main()
