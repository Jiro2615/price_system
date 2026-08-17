from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import rakuten_inventory_reconcile as reconcile  # noqa: E402


def response(status: int, body: bytes, headers: dict[str, str] | None = None) -> requests.Response:
    result = requests.Response()
    result.status_code = status
    result._content = body
    result.headers.update(headers or {})
    result.url = "https://api.rms.rakuten.co.jp/es/2.1/inventories/example"
    return result


class InventoryReconcileRetryTests(unittest.TestCase):
    def test_retries_429_using_retry_after_then_returns_quantity(self) -> None:
        with (
            patch.object(
                reconcile.requests,
                "get",
                side_effect=[
                    response(429, b'{"error":"too many requests"}', {"Retry-After": "0"}),
                    response(200, b'{"quantity":3}'),
                ],
            ) as get_mock,
            patch.object(reconcile.time, "sleep") as sleep_mock,
        ):
            quantity = reconcile.fetch_rms_quantity(
                {"Authorization": "ESA token"},
                "manage",
                "sku",
                retry_count=2,
                retry_wait=5,
                timeout=60,
            )

        self.assertEqual(3, quantity)
        self.assertEqual(2, get_mock.call_count)
        sleep_mock.assert_called_once_with(0.0)

    def test_error_save_does_not_advance_last_checked_at(self) -> None:
        class Cursor:
            query = ""

            def execute(self, query, _params):
                self.query = query

        cursor = Cursor()
        reconcile.save_error(cursor, 1, "429")
        self.assertNotIn("rms_inventory_checked_at", cursor.query)


if __name__ == "__main__":
    unittest.main()
