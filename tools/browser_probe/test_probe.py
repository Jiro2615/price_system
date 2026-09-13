import unittest
from summarize import comparable, compare_cases
from probe_support import REPO, no_db, challenge
from asin_plan import make_plan, CONTROLS, load_asins, wait_turn, from_db
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
import asyncio
import sys


class ProbeTests(unittest.TestCase):
    def test_multivariety_controls(self):
        others = [f"B{i:09d}" for i in range(21)]
        plan = make_plan(others + others)
        self.assertEqual(plan[:3], CONTROLS)
        self.assertEqual(plan[13:16], CONTROLS)
        self.assertEqual(set(plan), set(others + CONTROLS))

    def test_input(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "asins.txt"
            p.write_text("b07qp2l8lc &#x20;\nB07QP2L8LC\n", encoding="utf-8")
            self.assertEqual(load_asins(p), ["B07QP2L8LC"])
            p.write_text("bad", encoding="utf-8")
            with self.assertRaises(ValueError): load_asins(p)

    def test_paired_turn(self):
        with TemporaryDirectory() as folder:
            p = Path(folder)
            self.assertTrue(asyncio.run(wait_turn(p, "chrome", "chrome", 0)))
            self.assertTrue(asyncio.run(wait_turn(p, "shell", "shell", 0)))
            (p / "chrome_0.done").touch()
            self.assertTrue(asyncio.run(wait_turn(p, "shell", "chrome", 0)))
            (p / "chrome.finished").touch()
            self.assertFalse(asyncio.run(wait_turn(p, "shell", "chrome", 1)))
            (p / "STOP").touch()
            self.assertFalse(asyncio.run(wait_turn(p, "chrome", "chrome", 0)))

    def test_db_select_only(self):
        sys.path.insert(0, str(REPO))
        for stats in (False, True):
            with patch("scripts.db_config.connect_db") as connect:
                cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
                cursor.fetchall.return_value = [("B07QP2L8LC",)]
                self.assertEqual(from_db(use_stats=stats), ["B07QP2L8LC"])
                self.assertIn("default_transaction_read_only=on", connect.call_args.kwargs["options"])
                sql = cursor.execute.call_args.args[0].upper()
                self.assertTrue(sql.strip().startswith("SELECT"))
                for forbidden in ("UPDATE ", "INSERT ", "DELETE ", "FOR UPDATE"):
                    self.assertNotIn(forbidden, sql)
    def test_relative_repo(self):
        self.assertTrue((REPO / "scripts" / "price_check_one_asin_db.py").is_file())

    def test_db_forbidden(self):
        with self.assertRaises(RuntimeError):
            no_db()

    def test_challenge(self):
        self.assertTrue(challenge("https://www.amazon.co.jp/ap/signin", ""))
        self.assertTrue(challenge("", "ロボットではない"))
        self.assertFalse(challenge("https://www.amazon.co.jp/dp/B07QP2L8LC", "商品"))

    def test_empty_never_passes(self):
        self.assertFalse(compare_cases({}, {})["baseline_matches"])

    def test_error_never_passes(self):
        a = {"baseline": {"system_error": True}}
        self.assertFalse(compare_cases(a, a)["baseline_matches"])

    def test_countdown_only(self):
        a = "929円 9月15日（5 時間 40 分以内にご注文の場合）"
        b = "929円 9月15日（5 時間 39 分以内にご注文の場合）"
        self.assertEqual(comparable(a), comparable(b))
        self.assertNotEqual(comparable(a), comparable(b.replace("929", "930")))
        self.assertNotEqual(comparable(a), comparable(b.replace("15日", "16日")))

    def test_same_price_different_quantity_detected(self):
        a = {"baseline": {"amazon_price": 2792, "available_qty": 2}}
        b = {"baseline": {"amazon_price": 2792, "available_qty": 15}}
        result = compare_cases(a, b)
        self.assertFalse(result["baseline_matches"])
        self.assertEqual(result["baseline_differences"], ["available_qty"])


if __name__ == "__main__":
    unittest.main()
