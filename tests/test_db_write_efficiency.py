"""Offline schema/write regression tests: no production DB or API imports."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_functions(filename, names, namespace):
    tree = ast.parse((SCRIPTS / filename).read_text(encoding="utf-8-sig"))
    # price_check_from_db later wraps these functions with the DB retry helper.
    selected = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.setdefault(node.name, node)
    exec(compile(ast.Module(body=list(selected.values()), type_ignores=[]), filename, "exec"), namespace)
    return namespace


class FakeConnection:
    def __init__(self, rows=(), one=(None, None)):
        self.rows, self.one, self.sql = rows, one, []
        self.closed = False
        self.commits = 0

    def __enter__(self): return self
    def __exit__(self, *_): pass
    def cursor(self): return self
    def transaction(self): return self
    def execute(self, sql, params=()): self.sql.append((sql, params))
    def fetchall(self): return self.rows
    def fetchone(self): return self.one
    def commit(self): self.commits += 1
    def close(self): self.closed = True


class WorkerSchemaTests(unittest.TestCase):
    STATS = {"status", "worker_id", "locked_at", "lock_expires_at",
             "consecutive_system_error_count", "last_system_error_reason"}
    RUNS = {"id", "worker_id", "claimed_count", "checked_count", "success_count",
            "changed_count", "stable_count", "system_error_count", "business_ng_count",
            "page_reset_count", "elapsed_seconds", "avg_seconds_per_item", "returncode",
            "started_at", "finished_at", "created_at"}

    def invoke(self, name, columns):
        conn = FakeConnection([(column,) for column in columns])
        ns = load_functions("price_check_from_db.py", {
            "amazon_check_schema_columns", "ensure_amazon_check_stats_schema",
            "ensure_amazon_check_worker_runs_schema",
        }, {"connect_db": lambda: conn})
        ns[name]()
        self.assertTrue(conn.closed)
        return conn, ns

    def test_existing_stats_does_not_request_ddl_or_commit(self):
        conn, _ = self.invoke("ensure_amazon_check_stats_schema", self.STATS)
        self.assertEqual(len(conn.sql), 1)
        self.assertIn("pg_attribute", conn.sql[0][0])
        self.assertEqual(conn.commits, 0)

    def test_missing_stats_column_keeps_original_migration(self):
        conn, _ = self.invoke("ensure_amazon_check_stats_schema", self.STATS - {"worker_id"})
        self.assertIn("ALTER TABLE amazon_check_stats", conn.sql[1][0])
        self.assertIn("last_system_error_reason", conn.sql[1][0])
        self.assertEqual(conn.commits, 1)

    def test_existing_metrics_schema_does_not_request_ddl(self):
        conn, _ = self.invoke("ensure_amazon_check_worker_runs_schema", self.RUNS)
        self.assertEqual(len(conn.sql), 1)
        self.assertEqual(conn.commits, 0)

    def test_missing_metrics_table_or_column_keeps_creation_and_migration(self):
        for columns in (set(), self.RUNS - {"returncode"}):
            conn, _ = self.invoke("ensure_amazon_check_worker_runs_schema", columns)
            self.assertEqual(len(conn.sql), 3)
            self.assertIn("CREATE TABLE IF NOT EXISTS", conn.sql[1][0])
            self.assertIn("ALTER TABLE amazon_check_worker_runs", conn.sql[2][0])

    def test_schema_is_checked_again_and_not_cached(self):
        conn, ns = self.invoke("ensure_amazon_check_stats_schema", self.STATS)
        conn.rows = []
        ns["ensure_amazon_check_stats_schema"]()
        self.assertIn("ALTER TABLE", conn.sql[-1][0])

    def test_catalog_failure_is_not_silenced(self):
        conn, ns = self.invoke("ensure_amazon_check_stats_schema", self.STATS)
        conn.execute = Mock(side_effect=RuntimeError("catalog unavailable"))
        with self.assertRaisesRegex(RuntimeError, "catalog unavailable"):
            ns["ensure_amazon_check_stats_schema"]()
        self.assertTrue(conn.closed)


class PriceQueueTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_functions("rakuten_price_patch.py", {
            "ensure_retry_state_table", "ensure_pending_state_table", "refresh_pending_price_queue",
        }, {"RETRY_STATE_TABLE": "rakuten_price_api_retry_state",
            "PENDING_STATE_TABLE": "rakuten_price_api_pending_state"})

    def test_existing_queue_tables_and_indexes_skip_ddl(self):
        for name in ("ensure_retry_state_table", "ensure_pending_state_table"):
            conn = FakeConnection(one=("table", "index"))
            self.ns[name](conn)
            self.assertEqual(len(conn.sql), 1)
            self.assertTrue(conn.sql[0][0].startswith("SELECT"))

    def test_missing_table_or_index_retains_ddl(self):
        for name in ("ensure_retry_state_table", "ensure_pending_state_table"):
            for row in ((None, None), ("table", None)):
                conn = FakeConnection(one=row)
                self.ns[name](conn)
                self.assertEqual(len(conn.sql), 3)
                self.assertIn("CREATE TABLE IF NOT EXISTS", conn.sql[1][0])
                self.assertIn("CREATE INDEX IF NOT EXISTS", conn.sql[2][0])

    def test_price_queue_filters_equal_values_before_conflict_and_rechecks_races(self):
        conn = FakeConnection()
        self.ns["refresh_pending_price_queue"](conn, "rakuten_2")
        insert, params = conn.sql[0]
        self.assertIn("AND NOT EXISTS", insert)
        self.assertIn("unchanged.store_code = s.store_code", insert)
        self.assertIn("unchanged.target_price = sp.target_price", insert)
        self.assertIn("IS DISTINCT FROM EXCLUDED.target_price", insert)
        self.assertIn("IS DISTINCT FROM EXCLUDED.store_code", insert)
        self.assertEqual(params, ("rakuten_2",))
        for condition in ("sp.enabled = TRUE", "COALESCE(sp.no_price_change, FALSE) = FALSE",
                          "sp.target_price IS NOT NULL", "COALESCE(sp.current_price, -1) <> sp.target_price",
                          "COALESCE(sp.mall_item_code, '') <> ''"):
            self.assertIn(condition, insert)
        delete, params = conn.sql[1]
        self.assertIn("DELETE FROM", delete)
        self.assertIn("sp.enabled IS NOT TRUE", delete)
        self.assertEqual(params, ("rakuten_2", "rakuten_2"))


if __name__ == "__main__":
    unittest.main()
