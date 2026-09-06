import ast
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from amazon_result_classification import classify_purchase_restriction


def load_functions(filename, names, namespace):
    tree = ast.parse((ROOT / "scripts" / filename).read_text(encoding="utf-8-sig"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), namespace)


class ClassificationTests(unittest.TestCase):
    def test_known_restrictions_are_business_ng(self):
        for reason in ("ギフト不可", "ギフト不可（Amazon.co.jp直販例外の未確認: 出荷元・販売元 Amazon.co.jp）",
                       "ASIN不一致 current=B000OTHER1", "ASIN不一致（別商品へ遷移）", "BuyBox取得失敗"):
            with self.subTest(reason=reason):
                result = classify_purchase_restriction({"ng_reason": reason, "system_error": True,
                    "business_ng": False, "system_error_reason": reason})
                self.assertTrue(result["business_ng"])
                self.assertFalse(result["system_error"])
                self.assertEqual(result["ng_reason"], reason)
                self.assertNotIn("system_error_reason", result)

    def test_technical_failures_and_success_are_unchanged(self):
        for reason in ("Timeout 60000ms exceeded", "net::ERR_CONNECTION_RESET", "画像認証", "価格取得失敗", ""):
            with self.subTest(reason=reason):
                result = {"ng_reason": reason, "system_error": bool(reason), "business_ng": False}
                self.assertEqual(classify_purchase_restriction(dict(result)), result)

    def test_browser_recovery_and_confirmation_take_precedence(self):
        for flag in ("page_needs_reset", "amazon_confirmation_waiting", "skip_product_persistence"):
            result = {"ng_reason": "BuyBox取得失敗", "system_error": True, flag: True}
            self.assertEqual(classify_purchase_restriction(dict(result)), result)

    def test_exported_checker_applies_classification_before_return(self):
        checker = AsyncMock(return_value={"ng_reason": "BuyBox取得失敗", "system_error": True})
        namespace = {"_shared_amazon_checker": SimpleNamespace(check_amazon_one=checker),
                     "classify_purchase_restriction": classify_purchase_restriction}
        # Only the final exported wrapper; never import or launch a real browser.
        tree = ast.parse((ROOT / "scripts/price_check_one_asin_db.py").read_text(encoding="utf-8-sig"))
        node = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "check_amazon_one"][-1]
        exec(compile(ast.Module(body=[node], type_ignores=[]), "checker-wrapper", "exec"), namespace)
        result = asyncio.run(namespace["check_amazon_one"]("B000TEST01", page="test-page", page_timeout_ms=60000))
        checker.assert_awaited_once_with("B000TEST01", page="test-page", page_timeout_ms=60000)
        self.assertTrue(result["business_ng"])
        self.assertFalse(result["system_error"])

    def test_reclassified_result_clears_retry_streak_and_uses_normal_schedule(self):
        namespace = {"Any": Any, "datetime": datetime, "timedelta": timedelta,
                     "LONG_ZERO_STOCK_CHECK_INTERVAL_HOURS": 36}
        load_functions("price_check_from_db.py", {"normalize_text", "system_error_reason",
            "consecutive_system_error_count", "determine_stats_update", "apply_repeated_system_error_stock_stop"}, namespace)
        current = classify_purchase_restriction({"ng_reason": "BuyBox取得失敗", "system_error": True,
            "business_ng": False, "checked_at": datetime(2026, 9, 7, 2)})
        existing = {"check_count": 20, "price_change_count": 0, "stock_change_count": 0,
            "ng_change_count": 0, "error_count": 20, "stable_count": 0,
            "consecutive_system_error_count": 20, "last_system_error_reason": "BuyBox取得失敗"}
        self.assertEqual(namespace["apply_repeated_system_error_stock_stop"](current, existing), 0)
        stats = namespace["determine_stats_update"]({}, current, existing)
        self.assertEqual(stats["consecutive_system_error_count"], 0)
        self.assertEqual(stats["last_system_error_reason"], "")
        self.assertEqual(stats["error_count"], 20)
        self.assertFalse(stats["system_error_detected"])
        self.assertGreater(stats["check_interval_hours"], 1)


if __name__ == "__main__":
    unittest.main()
