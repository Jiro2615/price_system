import unittest
from unittest.mock import patch

from scripts.listing import listing_db_sync as sync_module


class Cursor:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


class ListingGenreSyncTests(unittest.TestCase):
    def test_genre_validation(self):
        for value in (None, '', 0, -1, '123.5', 'invalid', True):
            self.assertIsNone(sync_module._normalize_genre_id(value))
        self.assertEqual(sync_module._normalize_genre_id(' 101737 '), 101737)

    def test_executed_payload_has_priority(self):
        request = sync_module.ListingDbSyncRequest(result_json=None)
        with patch.object(sync_module, 'load_json', return_value={
            'raw_execute_result': {'executed_item_payload': {'genreId': '101737'}}
        }), patch.object(sync_module, '_load_related_json', return_value={
            'item_payload': {'genreId': '100000'}
        }):
            self.assertEqual(sync_module._extract_sync_payload(request)['rakuten_genre_id'], 101737)

    def test_update_and_insert_save_genre(self):
        sync = dict(asin='B000000001', variant_id='sku', standard_price=1000,
                    quantity=4, title='item', management_number='manage', rakuten_genre_id=101737)
        for existing in (0, 1):
            cursor = Cursor(existing)
            sync_module._update_or_insert_store_product(cursor, sync, 2)
            self.assertEqual(len(cursor.calls), 1 if existing else 2)
            for sql, params in cursor.calls:
                self.assertIn('rakuten_genre_id', sql)
                self.assertIn(101737, params)
                self.assertEqual(sql.count('%s'), len(params))
            self.assertIn('COALESCE(%s, rakuten_genre_id)', cursor.calls[0][0])


if __name__ == '__main__':
    unittest.main()
