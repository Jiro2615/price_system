import unittest
from unittest.mock import MagicMock, patch
from scripts.listing import listing_db_sync as sync


class MainImageSyncTests(unittest.TestCase):
    def save(self, raw, shop='https://www.rakuten.co.jp/lifeforest/'):
        cur = MagicMock()
        cur.fetchone.return_value = (shop,)
        sync._persist_main_image(cur, {'store_code': 'rakuten_2', 'management_number': 'item', 'raw_execute_result': raw}, 5)
        return cur

    def test_confirmed_relative_image_and_blank_only(self):
        cur = self.save({'rakuten_image_urls_after': ['/13649221/sub/main.jpg']})
        sql, args = cur.execute.call_args.args
        self.assertEqual(args, ('https://tshop.r10s.jp/lifeforest/cabinet/13649221/sub/main.jpg', '/13649221/sub/main.jpg', 5, 'item', '13649221/sub/main.jpg'))
        self.assertEqual(sql.count('%s'), len(args))
        self.assertIn("NULLIF(BTRIM(rakuten_image_url),'') IS NULL", sql)

    def test_actual_payload_and_upload_shapes(self):
        for raw in ({'executed_item_payload': {'images': [{'type': 'CABINET', 'location': '/123/a.jpg'}]}},
                    {'image_upload_results': [{'rakuten_image_url': '/123/a.jpg'}]}):
            self.assertIn('UPDATE store_products', self.save(raw).execute.call_args.args[0])

    def test_empty_or_foreign_image_does_not_write(self):
        for raw in ({}, {'rakuten_image_urls_after': ['https://evil.invalid/cabinet/a.jpg']},
                    {'rakuten_image_urls_after': ['https://tshop.r10s.jp/another/cabinet/123/a.jpg']}):
            cur = self.save(raw)
            self.assertFalse(any('UPDATE ' in call.args[0] for call in cur.execute.call_args_list))

    def test_path_remains_durable_without_store_slug(self):
        with patch.dict('os.environ', {}, clear=True):
            cur = self.save({'rakuten_image_urls_after': ['/123/a.jpg']}, None)
        self.assertIsNone(cur.execute.call_args.args[1][0])
        self.assertEqual(cur.execute.call_args.args[1][1], '/123/a.jpg')

    def test_sync_persists_image_even_without_snapshot(self):
        payload = {'final_status': 'completed', 'asin': 'B000000001', 'store_code': 'rakuten_2',
                   'management_number': 'item', 'raw_execute_result': {
                       'item_result': {'success': True}, 'inventory_result': {'success': True}}}
        with patch.object(sync, 'load_json', return_value=payload), \
                patch.object(sync, '_get_store_id', return_value=5), \
                patch.object(sync, 'connect_db') as connect, \
                patch.object(sync, '_persist_main_image') as save, \
                patch.object(sync, '_insert_snapshot') as snapshot:
            result = sync.sync_listing_result_to_db(sync.ListingDbSyncRequest(
                result_json=None, execute=True, save_snapshot=False))
        self.assertTrue(result['external_db_writes_performed'])
        save.assert_called_once()
        snapshot.assert_not_called()
        connect.assert_called_once()

    def test_preview_does_not_connect(self):
        with patch.object(sync, 'load_json', return_value={}), patch.object(sync, 'connect_db') as connect:
            result = sync.sync_listing_result_to_db(sync.ListingDbSyncRequest(result_json=None))
        self.assertFalse(result['external_db_writes_performed'])
        connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
