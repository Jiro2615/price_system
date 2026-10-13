"""Isolated production-function tests; API and DB operations are always mocked."""
import argparse
import ast
import contextlib
from decimal import Decimal, ROUND_CEILING
import io
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/keepa_product_finder.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))


def load():
    names = {"comma_values", "integer_values", "optional_int", "optional_rating", "optional_nonnegative_float",
             "make_selection", "parse_args", "batched", "asin_only_candidates", "token_snapshot",
             "needs_exact_average_metadata", "metadata_candidates", "filtered_candidate_search", "save_candidates"}
    scope = {"argparse": argparse, "json": json, "math": math, "re": re, "Decimal": Decimal,
             "ROUND_CEILING": ROUND_CEILING, "ASIN_PATTERN": re.compile(r"[A-Z0-9]{10}"),
             "MAX_CANDIDATE_LIMIT": 10000, "MAX_FILTERED_CANDIDATE_LIMIT": 500000,
             "MAX_FULL_SCAN_CANDIDATE_LIMIT": 1000000, "FULL_SCAN_PAGE_SIZE": 10000,
             "KEEPA_QUERY_ENDPOINT": "query", "wait_for_full_scan_budget": lambda *_args: None}
    text = "from __future__ import annotations\n" + "\n".join(ast.unparse(n) for n in TREE.body
               if isinstance(n, ast.FunctionDef) and n.name in names)
    exec(text, scope)
    return scope


def arguments(scope, *options):
    with patch.object(sys, "argv", ["finder", "--run-id", "test", "--store", "test", "--filtered-search", *options]):
        return scope["parse_args"]()


class FilterContractTests(unittest.TestCase):
    def test_every_configured_predicate_is_in_the_api_selection(self):
        s = load()
        a = arguments(s, "--root-categories", "52374051", "--include-categories", "111,222",
                      "--exclude-categories", "333", "--title", "cream", "--brands", "A,B", "--manufacturers", "M",
                      "--min-price", "500", "--max-price", "4500", "--min-rating", "3.5", "--min-review-count", "5",
                      "--min-current-new-sellers", "3", "--max-current-new-sellers", "10",
                      "--min-avg90-new-sellers", "3", "--max-avg90-new-sellers", "8",
                      "--min-sales-rank", "1", "--max-sales-rank", "50000", "--min-monthly-sold", "10",
                      "--amazon-in-stock", "--candidate-limit", "500000")
        selection = s["make_selection"](a)
        expected = {"rootCategory": [52374051], "categories_include": [111, 222], "categories_exclude": [333],
                    "title": "cream", "brand": ["A", "B"], "manufacturer": ["M"],
                    "current_NEW_gte": 500, "current_NEW_lte": 4500, "current_RATING_gte": 35,
                    "current_COUNT_REVIEWS_gte": 5, "current_COUNT_NEW_gte": 3, "current_COUNT_NEW_lte": 10,
                    "avg90_COUNT_NEW_gte": 3, "avg90_COUNT_NEW_lte": 8,
                    "current_SALES_gte": 1, "current_SALES_lte": 50000,
                    "monthlySold_gte": 10, "availabilityAmazon": [0]}
        for key, value in expected.items():
            self.assertEqual(selection[key], value, key)
        self.assertEqual(selection["perPage"], 10000)
        self.assertFalse(s["needs_exact_average_metadata"](a))

    def test_empty_optional_fields_do_not_reintroduce_cli_defaults(self):
        s = load()
        optional = ["min-price", "max-price", "min-rating", "min-review-count", "min-current-new-sellers",
                    "max-current-new-sellers", "min-avg90-new-sellers", "max-avg90-new-sellers",
                    "min-sales-rank", "max-sales-rank", "min-monthly-sold"]
        a = arguments(s, *[item for name in optional for item in ("--" + name, "")])
        selection = s["make_selection"](a)
        self.assertFalse(any(key.startswith(("current_", "avg90_", "monthlySold")) for key in selection), selection)

    def test_rating_rounding_never_accepts_below_the_requested_threshold(self):
        s = load()
        a = arguments(s, "--min-rating", "3.45")
        self.assertEqual(s["make_selection"](a)["current_RATING_gte"], 35)

    def test_invalid_values_and_paging_fail_before_an_api_call(self):
        s = load()
        for options in (("--candidate-limit", "500001"), ("--page", "1", "--candidate-limit", "20000"),
                        ("--page", "-1"), ("--min-rating", "nan"), ("--min-rating", "6"),
                        ("--min-avg90-new-sellers", "inf"), ("--min-price", "5", "--max-price", "4")):
            with self.subTest(options=options), self.assertRaises(ValueError):
                arguments(s, *options)

    def exercise(self, a, s, responder):
        queries, batches = [], []
        def request(_session, method, url, **kwargs):
            self.assertEqual((method, url), ("POST", "query"))
            query = dict(kwargs["json"])
            queries.append(query)
            return responder(query)
        s["request_json"] = request
        def save(_run, _store, rows, *, replace=True):
            batches.append((replace, len(rows)))
            self.assertLessEqual(len(rows), 1000)
        s["save_candidates"] = save
        with contextlib.redirect_stdout(io.StringIO()):
            result = s["filtered_candidate_search"](None, "unused", a, s["make_selection"](a))
        return result, queries, batches

    def test_large_limit_partitions_without_losing_any_other_condition(self):
        s = load()
        a = arguments(s, "--candidate-limit", "20000", "--root-categories", "52374051")
        def response(q):
            lo, hi = q["current_SALES_gte"], q["current_SALES_lte"]
            if hi - lo > 25000:
                return {"totalResults": 12000, "asinList": ["B000000001"]}
            first = 1 if lo == 1 else 6001
            return {"totalResults": 6000, "asinList": [f"B{i:09d}" for i in range(first, first + 6000)]}
        result, queries, batches = self.exercise(a, s, response)
        self.assertEqual(result["candidate_count"], 12000)
        self.assertEqual(len(queries), 3)
        for q in queries:
            self.assertEqual(q["current_RATING_gte"], 35)
            self.assertEqual(q["current_COUNT_REVIEWS_gte"], 5)
            self.assertEqual(q["current_NEW_gte"], 500)
            self.assertEqual(q["current_COUNT_NEW_gte"], 3)
            self.assertEqual(q["rootCategory"], [52374051])
        self.assertEqual(queries[1]["current_SALES_lte"], 25000)
        self.assertEqual(queries[2]["current_SALES_gte"], 25001)
        self.assertEqual(batches[0], (True, 0))
        self.assertTrue(all(not replace for replace, _ in batches[1:]))

    def test_half_million_synthetic_results_are_saved_in_small_batches_only(self):
        s = load()
        a = arguments(s, "--candidate-limit", "500000", "--min-sales-rank", "1", "--max-sales-rank", "50")
        def response(q):
            first = (q["current_SALES_gte"] - 1) * 10000 + 1
            total = (q["current_SALES_lte"] - q["current_SALES_gte"] + 1) * 10000
            return {"totalResults": total, "asinList": [f"B{i:09d}" for i in range(first, first + min(total, q["perPage"]))]}
        result, _, batches = self.exercise(a, s, response)
        self.assertEqual(result["candidate_count"], 500000)
        self.assertEqual(sum(size for _, size in batches), 500000)
        self.assertTrue(result["limit_reached"])

    def test_bounded_page_is_preserved_not_reset_to_zero(self):
        s = load()
        a = arguments(s, "--candidate-limit", "50", "--page", "2")
        result, queries, _ = self.exercise(a, s, lambda q: {"totalResults": 110, "asinList": ["B000000001"]})
        self.assertEqual(queries[0]["page"], 2)
        self.assertEqual(queries[0]["perPage"], 50)
        self.assertEqual(result["candidate_count"], 1)

    def test_unpartitionable_range_and_broken_response_fail_closed(self):
        for extra, payload in ((["--min-sales-rank", "", "--max-sales-rank", ""], {"totalResults": 20000, "asinList": ["B000000001"]}),
                               ([], {"totalResults": 1, "asinList": []}),
                               ([], {"totalResults": 1, "asinList": "bad"})):
            with self.subTest(extra=extra):
                s = load(); a = arguments(s, "--candidate-limit", "20000", *extra)
                with self.assertRaises((RuntimeError, ValueError)):
                    self.exercise(a, s, lambda q: payload)

    def test_first_request_failure_does_not_erase_existing_partial_output(self):
        s = load(); a = arguments(s)
        saved = Mock()
        s["save_candidates"] = saved
        s["request_json"] = Mock(side_effect=RuntimeError("network failure"))
        with self.assertRaises(RuntimeError):
            s["filtered_candidate_search"](None, "unused", a, s["make_selection"](a))
        saved.assert_not_called()

    def test_decimal_average_is_checked_exactly_after_the_query(self):
        s = load(); a = arguments(s, "--min-avg90-new-sellers", "3.5")
        self.assertTrue(s["needs_exact_average_metadata"](a))
        s["request_json"] = lambda *_args, **_kwargs: {"products": [
            {"asin": "B000000001", "average": 3.49}, {"asin": "B000000002", "average": 3.5},
            {"asin": "B000000003", "average": float("nan")}]}
        s["parse_keepa_product"] = lambda asin, raw: SimpleNamespace(
            title="Test", ean="", category_id=None, category_tree=[], current_new_offer_count=3,
            avg90_new_offer_count=raw["average"], avg90_seller_count=None, buy_box_price=None,
            buy_box_shipping=None, is_adult=False)
        s["category_path"] = lambda _p: ""
        s["asdict"] = vars
        rows, _ = s["metadata_candidates"](None, "unused", ["B000000001", "B000000002", "B000000003"], a, s["make_selection"](a))
        self.assertEqual([row["asin"] for row in rows], ["B000000002"])

    def test_bulk_save_is_transactional_and_clears_only_the_requested_run(self):
        s = load()
        cursor = MagicMock(); cursor.__enter__.return_value = cursor
        conn = MagicMock(); conn.__enter__.return_value = conn; conn.cursor.return_value = cursor
        s.update(connect_db=lambda: conn, ensure_candidate_table=lambda _cur: None, Jsonb=lambda value: value)
        recorded = []
        cursor.executemany.side_effect = lambda sql, values: recorded.extend(values)
        rows = s["asin_only_candidates"](["B000000001", "B000000002"], {"current_RATING_gte": 35})
        s["save_candidates"]("test", "store", rows)
        self.assertEqual(cursor.execute.call_args.args[1], ("test",))
        self.assertEqual([row[2] for row in recorded], ["B000000001", "B000000002"])
        self.assertTrue(all(row[12]["current_RATING_gte"] == 35 for row in recorded))
        conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
