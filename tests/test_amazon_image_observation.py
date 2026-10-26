"""Only mocked cursors: never import the real checker or connect to a DB."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parents[1]/"scripts"))
import amazon_image_observation as images


class ObservationTests(unittest.TestCase):
    def setUp(self):
        images._schema = (0.0, False)
        self.cur = MagicMock()
        self.cur.fetchall.return_value = [(name,) for name in ("amazon_main_image_url", "amazon_main_image_checked_at", "amazon_main_image_error")]
        self.data = {"asin": "B000000001", "amazon_main_image_verified_asin": "B000000001",
                     "amazon_main_image_url": "https://m.media-amazon.com/images/I/main.jpg",
                     "amazon_main_image_checked_at": datetime.now(timezone.utc).isoformat(), "amazon_main_image_error": ""}

    def test_valid_observation_atomic_update_only_this_asin_and_not_older(self):
        images.record_main_image(self.cur, self.data)
        sql, params = self.cur.execute.call_args.args
        self.assertTrue(sql.startswith("UPDATE amazon_products"))
        self.assertIn("amazon_main_image_checked_at <= %s", sql)
        self.assertEqual(params[3], "B000000001")
        for name in ("amazon_price", "available_qty", "business_ng", "title="):
            self.assertNotIn(name, sql)
        self.assertNotIn("ALTER", " ".join(c.args[0] for c in self.cur.execute.call_args_list))

    def test_missing_schema_keeps_regular_price_save_working_and_cached(self):
        self.cur.fetchall.return_value = []
        images.record_main_image(self.cur, self.data)
        images.record_main_image(self.cur, self.data)
        self.assertEqual(self.cur.execute.call_count, 1)
        self.assertTrue(self.cur.execute.call_args.args[0].startswith("SELECT"))

    def test_schema_lookup_is_not_per_product(self):
        images.record_main_image(self.cur, self.data)
        images.record_main_image(self.cur, self.data)
        self.assertEqual(self.cur.execute.call_count, 3)

    def test_old_checkers_wrong_asin_and_naive_dates_never_write(self):
        for changes in ({"amazon_main_image_checked_at": None}, {"amazon_main_image_verified_asin": "B000000002"},
                        {"amazon_main_image_checked_at": "2026-10-26T12:00:00"}):
            images.record_main_image(self.cur, {**self.data, **changes})
        self.cur.execute.assert_not_called()

    def test_invalid_or_failed_image_clears_url_marks_unknown_not_old_match(self):
        images.record_main_image(self.cur, {**self.data, "amazon_main_image_url": "https://evil.invalid/a.jpg"})
        self.assertEqual(self.cur.execute.call_args.args[1][0], "")
        self.assertEqual(self.cur.execute.call_args.args[1][2], "main_image_unavailable")

    def test_production_calls_inside_existing_transaction_and_preserves_retry(self):
        path = Path(__file__).parents[1]/"scripts/price_check_one_asin_db.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        saves = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "save_to_db"]
        body = ast.unparse(saves[0])
        self.assertLess(body.index("INSERT INTO amazon_products"), body.index("record_main_image(cur, data)"))
        self.assertLess(body.index("record_main_image(cur, data)"), body.index("conn.commit()"))
        self.assertIn("run_with_db_retry", ast.unparse(saves[-1]))

    def test_real_save_function_uses_mocked_transaction_with_optional_metadata(self):
        path = Path(__file__).parents[1]/"scripts/price_check_one_asin_db.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "save_to_db")
        node.returns = None
        for arg in node.args.args:
            arg.annotation = None
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = self.cur
        namespace = {"re": re, "connect_db": lambda: conn}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), "exec"), namespace)
        namespace["save_to_db"](self.data)
        self.assertIn("INSERT INTO amazon_products", self.cur.execute.call_args_list[0].args[0])
        self.assertIn("UPDATE amazon_products", self.cur.execute.call_args_list[-1].args[0])
        conn.commit.assert_called_once()
        conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
