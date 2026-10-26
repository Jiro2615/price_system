"""Fake-only successful content refresh persistence; no live DB or APIs."""
import unittest
from unittest.mock import MagicMock, patch
from scripts.listing import listing_db_sync as sync


class ContentSyncTests(unittest.TestCase):
    def payload(self):
        return {"asin": "B000000001", "store_code": "rakuten_2", "management_number": "item",
                "variant_id": "sku",
                "title": "楽天向け新タイトル", "final_status": "completed", "item_success": True, "inventory_success": True,
                "executed_item_payload": {"title": "楽天向け新タイトル"}, "inventory_payload": {},
                "amazon_result": {"requested_asin": "B000000001", "page_asin": "B000000001", "title": "Amazon原題"},
                "raw_execute_result": {"inventory_result": {"success": True, "skipped": True,
                                      "reason": "content_refresh does not change inventory"}}}

    def test_preview_and_non_success_never_connect(self):
        for execute, changes in ((False, {}), (True, {"final_status": "failed"}),
                                 (True, {"item_success": False}), (True, {"inventory_success": False}),
                                 (True, {"title": ""}), (True, {"raw_execute_result": {}})):
            with patch.object(sync, "_extract_sync_payload", return_value={**self.payload(), **changes}), \
                    patch.object(sync, "connect_db") as connect:
                result = sync.sync_listing_content_result_to_db(sync.ListingDbSyncRequest(result_json=None, execute=execute))
            self.assertFalse(result["external_db_writes_performed"])
            connect.assert_not_called()

    def test_only_title_and_snapshot_written_no_prices_inventory_or_reenable(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [("B000000001",)]
        with patch.object(sync, "_extract_sync_payload", return_value=self.payload()), \
                patch.object(sync, "_get_store_id", return_value=2), \
                patch.object(sync, "connect_db", return_value=conn), \
                patch.object(sync, "_upsert_amazon_product", side_effect=AssertionError("No Amazon state writes")), \
                patch.object(sync, "_update_or_insert_store_product", side_effect=AssertionError("No normal listing writes")):
            result = sync.sync_listing_content_result_to_db(sync.ListingDbSyncRequest(result_json=None, execute=True))
        self.assertTrue(result["external_db_writes_performed"])
        writes = [call for call in cur.execute.call_args_list if call.args[0].lstrip().startswith("UPDATE")]
        self.assertEqual(len(writes), 1)
        sql, params = writes[0].args
        self.assertEqual(params, ("楽天向け新タイトル", 2, "item", "B000000001"))
        for forbidden in ("current_price", "target_price", "current_stock", "target_stock", "enabled", "force_stop"):
            self.assertNotIn(forbidden, sql)
        snapshot = cur.execute.call_args_list[-1].args[1][-1].obj
        self.assertEqual(snapshot["source_amazon_title"], "Amazon原題")
        self.assertEqual(snapshot["source_amazon_asin"], "B000000001")
        conn.commit.assert_called_once()

    def test_missing_or_changed_identity_rolls_back_without_write(self):
        for targets in ([], [("B000000002",)], [("B000000001",), ("B000000002",)]):
            conn = MagicMock()
            conn.__enter__.return_value = conn
            cur = conn.cursor.return_value.__enter__.return_value
            cur.fetchall.return_value = targets
            with patch.object(sync, "_extract_sync_payload", return_value=self.payload()), \
                    patch.object(sync, "_get_store_id", return_value=2), \
                    patch.object(sync, "connect_db", return_value=conn):
                with self.assertRaises(ValueError):
                    sync.sync_listing_content_result_to_db(sync.ListingDbSyncRequest(result_json=None, execute=True))
            self.assertEqual(len(cur.execute.call_args_list), 1)
            conn.commit.assert_not_called()

    def test_bad_amazon_identity_never_saved_as_baseline(self):
        for changes in ({"requested_asin": "B000000002"}, {"page_asin": "B000000002"}, {"system_error": True}):
            payload = self.payload()
            payload["amazon_result"].update(changes)
            cur = MagicMock()
            sync._insert_snapshot(cur, payload, 2)
            self.assertEqual(cur.execute.call_args.args[1][-1].obj["source_amazon_title"], "")


if __name__ == "__main__":
    unittest.main()
