import asyncio
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


SCRIPTS_DIR = Path(r"C:\price_system\scripts")
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if "playwright.async_api" not in sys.modules:
    playwright_module = types.ModuleType("playwright")
    async_api_module = types.ModuleType("playwright.async_api")
    async_api_module.async_playwright = Mock()
    playwright_module.async_api = async_api_module
    sys.modules["playwright"] = playwright_module
    sys.modules["playwright.async_api"] = async_api_module

import psycopg

import amazon_check_worker_loop
import db_retry
import price_check_from_db


def make_temp_db_error(message: str = "temporary db down") -> db_retry.TemporaryDbError:
    return db_retry.TemporaryDbError(
        message,
        attempts=3,
        waited_seconds=20,
        last_error=psycopg.OperationalError(message),
    )


class DbRetryTests(unittest.TestCase):
    def test_run_with_db_retry_succeeds_on_third_attempt(self) -> None:
        attempts = {"count": 0}
        sleeps: list[float] = []

        def operation() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise psycopg.OperationalError("db unavailable")
            return "ok"

        result = db_retry.run_with_db_retry(
            operation,
            description="test_operation",
            logger=lambda _msg: None,
            sleep_func=sleeps.append,
            max_attempts=5,
            max_wait_seconds=120,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(sleeps, [5, 15])


class PriceCheckMainTests(unittest.TestCase):
    def test_save_failure_does_not_trigger_second_stats_fetch(self) -> None:
        temp_db_error = make_temp_db_error()

        with patch.object(sys, "argv", ["price_check_from_db.py", "--limit", "1", "--use-stats"]), \
            patch.object(price_check_from_db, "ensure_amazon_check_stats_schema"), \
            patch.object(price_check_from_db, "ensure_amazon_check_stats_rows"), \
            patch.object(price_check_from_db, "ensure_amazon_check_worker_runs_schema"), \
            patch.object(price_check_from_db, "release_expired_processing_locks", return_value=0), \
            patch.object(price_check_from_db, "claim_target_asins_by_stats", return_value=[{"asin": "B000TEST"}]), \
            patch.object(price_check_from_db, "create_amazon_page", new=AsyncMock(return_value=(None, None, None, None))), \
            patch.object(price_check_from_db, "close_amazon_page", new=AsyncMock()), \
            patch.object(price_check_from_db, "check_amazon_one", new=AsyncMock(return_value={
                "asin": "B000TEST",
                "title": "item",
                "amazon_price": 1000,
                "amazon_point": 0,
                "available_qty": 1,
                "gift_available": False,
                "shipping_status": "OK",
                "business_ng": False,
                "system_error": False,
                "ng_reason": "",
                "checked_at": price_check_from_db.datetime.now(),
                "page_needs_reset": False,
            })), \
            patch.object(price_check_from_db, "get_previous_amazon_state", return_value={}), \
            patch.object(price_check_from_db, "get_existing_stats", return_value={}) as mock_get_existing_stats, \
            patch.object(price_check_from_db, "save_to_db", side_effect=temp_db_error):
            result = asyncio.run(price_check_from_db.main())

        self.assertEqual(result, db_retry.DB_RETRY_EXIT_CODE)
        self.assertEqual(mock_get_existing_stats.call_count, 1)


class TargetRecalcPersistenceTests(unittest.TestCase):
    class _Cursor:
        def __init__(self, rows):
            self.rows = rows

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args):
            return None

        def fetchall(self):
            return self.rows

    class _Connection:
        def __init__(self, rows):
            self.rows = rows

        def cursor(self):
            return TargetRecalcPersistenceTests._Cursor(self.rows)

    @staticmethod
    def _result(price=1234, stock=2):
        return {
            "rows": 1,
            "targets": [{
                "asin": "B000TEST01",
                "store_code": "rakuten_2",
                "target_price": price,
                "target_stock": stock,
            }],
        }

    def test_saved_target_matching_calculation_is_accepted(self) -> None:
        price_check_from_db.verify_target_recalc_persisted(
            self._Connection([(1234, 2)]),
            asin="B000TEST01",
            store_code="rakuten_2",
            result=self._result(),
        )

    def test_unsaved_target_is_reported(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "was not persisted"):
            price_check_from_db.verify_target_recalc_persisted(
                self._Connection([(None, None)]),
                asin="B000TEST01",
                store_code="rakuten_2",
                result=self._result(),
            )


class WorkerLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolved_worker = {
            "worker_config_id": 1,
            "worker_id": "test-worker",
            "node_code": "node-a",
            "hostname": "host-a",
            "worker_number": 1,
            "revision": 1,
            "enabled": True,
            "desired_state": "running",
            "resolved_settings": {
                "limit": {"value": 1, "source": "test"},
                "loop_sleep_seconds": {"value": 1, "source": "test"},
                "empty_sleep_seconds": {"value": 1, "source": "test"},
                "page_timeout_ms": {"value": 1000, "source": "test"},
                "use_stats": {"value": True, "source": "test"},
                "log_retention_days": {"value": 0, "source": "test"},
            },
        }

    def test_db_exit_code_restarts_worker(self) -> None:
        with patch.object(sys, "argv", ["amazon_check_worker_loop.py", "--worker-number", "1", "--max-loops", "2"]), \
            patch.object(amazon_check_worker_loop, "load_resolved_worker_settings", return_value=self.resolved_worker), \
            patch.object(amazon_check_worker_loop, "cleanup_old_logs", return_value=0), \
            patch.object(amazon_check_worker_loop, "open_log_stream", return_value=(Path("worker.log"), io.StringIO())), \
            patch.object(
                amazon_check_worker_loop,
                "run_child_once",
                side_effect=[
                    (db_retry.DB_RETRY_EXIT_CODE, 1.0, False, {}, "temporary DB error"),
                    (0, 1.0, True, {}, ""),
                ],
            ) as mock_run_child, \
            patch.object(amazon_check_worker_loop, "wait_for_db_recovery") as mock_wait, \
            patch.object(amazon_check_worker_loop.time, "sleep"):
            result = amazon_check_worker_loop.main()

        self.assertEqual(result, 0)
        self.assertEqual(mock_run_child.call_count, 2)
        mock_wait.assert_called_once()

    def test_non_db_error_does_not_restart_forever(self) -> None:
        with patch.object(sys, "argv", ["amazon_check_worker_loop.py", "--worker-number", "1"]), \
            patch.object(amazon_check_worker_loop, "load_resolved_worker_settings", return_value=self.resolved_worker), \
            patch.object(amazon_check_worker_loop, "cleanup_old_logs", return_value=0), \
            patch.object(amazon_check_worker_loop, "open_log_stream", return_value=(Path("worker.log"), io.StringIO())), \
            patch.object(amazon_check_worker_loop, "run_child_once", return_value=(1, 1.0, False, {}, "bug")), \
            patch.object(amazon_check_worker_loop, "wait_for_db_recovery") as mock_wait:
            result = amazon_check_worker_loop.main()

        self.assertEqual(result, 1)
        mock_wait.assert_not_called()

    def test_keyboard_interrupt_exits(self) -> None:
        with patch.object(sys, "argv", ["amazon_check_worker_loop.py", "--worker-number", "1"]), \
            patch.object(amazon_check_worker_loop, "load_resolved_worker_settings", return_value=self.resolved_worker), \
            patch.object(amazon_check_worker_loop, "cleanup_old_logs", return_value=0), \
            patch.object(amazon_check_worker_loop, "open_log_stream", return_value=(Path("worker.log"), io.StringIO())), \
            patch.object(amazon_check_worker_loop, "run_child_once", side_effect=KeyboardInterrupt):
            result = amazon_check_worker_loop.main()

        self.assertEqual(result, 130)


if __name__ == "__main__":
    unittest.main()
