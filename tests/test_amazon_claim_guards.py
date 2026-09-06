"""Claim regression tests. DB cases use only temporary tables and roll back.

Opt in with AMAZON_CLAIM_TEST_TEMP_DB=1 to execute the PostgreSQL cases.
"""
import ast
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def function_node(filename, name):
    tree = ast.parse((ROOT / "scripts" / filename).read_text(encoding="utf-8-sig"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def claim_sql(name):
    node = function_node("price_check_from_db.py", name)
    return next(n.value.value for n in node.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "sql" for t in n.targets))


class WorkerCommandTests(unittest.TestCase):
    def test_error_recheck_cannot_disable_claiming(self):
        node = function_node("amazon_check_worker_loop.py", "build_child_cmd")
        namespace = {"Any": object, "py_cmd": lambda script: ["python", script]}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "worker-command", "exec"), namespace)
        settings = {"limit": {"value": 100}, "page_timeout_ms": {"value": 60000},
                    "use_stats": {"value": False}}
        command = namespace["build_child_cmd"]("test-worker", settings, recheck_system_errors=True)
        self.assertIn("--use-stats", command)
        self.assertNotIn("--no-use-stats", command)


@unittest.skipUnless(os.getenv("AMAZON_CLAIM_TEST_TEMP_DB") == "1", "temporary DB tests require opt-in")
class ClaimSqlTests(unittest.TestCase):
    def setUp(self):
        from db_config import connect_db
        self.conn = connect_db(connect_timeout=8, options="-c statement_timeout=10000")
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.q = self.conn.cursor()
        self.q.execute("""
            CREATE TEMP TABLE amazon_check_stats (
                asin text PRIMARY KEY, status text, next_check_at timestamp,
                last_checked_at timestamp, priority_score int DEFAULT 100,
                worker_id text, locked_at timestamp, lock_expires_at timestamp,
                updated_at timestamp, check_interval_hours int DEFAULT 1
            );
            CREATE TEMP TABLE amazon_products (asin text, system_error boolean, ng_reason text, checked_at timestamp);
            CREATE TEMP TABLE stores (id int, store_code text);
            CREATE TEMP TABLE store_products (asin text, store_id int, enabled boolean, force_stop boolean, current_status text);
            INSERT INTO stores VALUES (1, 'rakuten_2');
        """)
        # Fail closed if any query would resolve to a persistent table.
        for table in ("amazon_check_stats", "amazon_products", "stores", "store_products"):
            self.q.execute("SELECT relpersistence FROM pg_class WHERE oid = %s::regclass", (table,))
            self.assertEqual(self.q.fetchone()[0], "t")

    def seed(self, asin, status="done", delay="-1 hour", lock_delay="-1 minute", error=True, reason="BuyBox"):
        self.q.execute("""INSERT INTO amazon_check_stats
            (asin,status,next_check_at,lock_expires_at) VALUES
            (%s,%s,CURRENT_TIMESTAMP + %s::interval,CURRENT_TIMESTAMP + %s::interval)""",
            (asin,status,delay,lock_delay))
        self.q.execute("INSERT INTO amazon_products VALUES (%s,%s,%s,NULL)", (asin,error,reason))
        self.q.execute("INSERT INTO store_products VALUES (%s,1,TRUE,FALSE,'listed')", (asin,))

    def claim(self, name, worker="worker-a", error_only=True, reason=""):
        self.q.execute(claim_sql(name), {"limit": 100, "worker_id": worker,
            "lock_minutes": 30, "system_error_only": error_only, "reason_contains": reason,
            "reason_pattern": "%" + reason + "%", "store_code": "rakuten_2",
            "long_zero_interval_hours": 36})
        return {row[0] for row in self.q.fetchall()}

    def test_error_recheck_honors_schedule_and_existing_claims(self):
        for name in ("claim_target_asins_by_stats_v2", "_claim_active_listed_store_asins_without_retry"):
            with self.subTest(path=name):
                self.q.execute("SAVEPOINT fixture")
                self.seed("due")
                self.seed("future", delay="1 hour")
                self.seed("busy", status="processing", lock_delay="30 minutes")
                self.seed("expired", status="processing")
                self.seed("healthy", error=False)
                self.assertEqual(self.claim(name), {"due", "expired"})
                self.assertEqual(self.claim(name, worker="worker-b"), set())
                self.q.execute("ROLLBACK TO SAVEPOINT fixture")

    def test_reason_filter_still_applies(self):
        for name in ("claim_target_asins_by_stats_v2", "_claim_active_listed_store_asins_without_retry"):
            with self.subTest(path=name):
                self.q.execute("SAVEPOINT fixture")
                self.seed("match", reason="BuyBox unavailable")
                self.seed("other", reason="ASIN mismatch")
                self.assertEqual(self.claim(name, reason="BuyBox"), {"match"})
                self.q.execute("ROLLBACK TO SAVEPOINT fixture")

    def test_normal_due_queue_still_excludes_busy_and_future(self):
        self.seed("due", error=False)
        self.seed("future", delay="1 hour", error=False)
        self.seed("busy", status="processing", lock_delay="1 hour", error=False)
        self.assertEqual(self.claim("claim_target_asins_by_stats_v2", error_only=False), {"due"})


if __name__ == "__main__":
    unittest.main()
