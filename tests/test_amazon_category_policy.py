"""Category ancestry and last-moment listing gates, with all live I/O forbidden."""
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, patch

from scripts.listing import amazon_category_policy as policy
from scripts.listing import listing_execute_service as execute
from scripts.listing import real_execute_service as real


class CategoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ('psycopg.connect', 'requests.sessions.Session.request', 'urllib.request.OpenerDirector.open'):
            self.stack.enter_context(patch(target, side_effect=AssertionError('Live access forbidden')))
        self.product = {'category_id': 30, 'category_tree': [{'catId': 10}, {'catId': 20}, {'catId': 30}]}

    def test_self_parent_and_root_block_but_other_branches_do_not(self):
        for node in (10, 20, 30):
            result = policy.category_exclusion_result(self.product, {node: '除外'})
            self.assertEqual(result['listing_status'], 'business_ng')
            self.assertEqual(result['matched_category_ids'], [node])
        self.assertIsNone(policy.category_exclusion_result(self.product, {3: '別カテゴリ', 300: '別カテゴリ'}))

    def test_missing_or_malformed_ancestry_holds_only_when_rules_exist(self):
        for product in (None, {}, {'category_tree': 'broken'}, {'category_tree': [{'name': 'no ID'}]},
                        {'category_tree': [{'catId': 30}, None]}):
            self.assertEqual(policy.category_exclusion_result(product, {10: ''})['listing_status'], 'missing_required_data')
            self.assertIsNone(policy.category_exclusion_result(product, {}))
        self.assertEqual(policy.category_exclusion_result({'category_id': 10}, {10: ''})['listing_status'], 'business_ng')

    def test_read_only_absent_table_and_enabled_rules(self):
        conn = MagicMock(); cur = conn.cursor.return_value.__enter__.return_value
        conn.__enter__.return_value = conn
        with patch.object(policy, 'connect_db', return_value=conn) as connect:
            cur.fetchone.return_value = (None,)
            self.assertEqual(policy.load_category_exclusions(), {})
            cur.fetchone.return_value = ('amazon_category_exclusions',)
            cur.fetchall.return_value = [(10, 'parent')]
            self.assertEqual(policy.load_category_exclusions(), {10: 'parent'})
            self.assertIn('read_only=on', connect.call_args.kwargs['options'])
            statements = [call.args[0] for call in cur.execute.call_args_list]
            self.assertTrue(all(sql.startswith('SELECT') for sql in statements))
            self.assertIn('enabled = TRUE', statements[-1])

    def test_db_failure_never_allows_listing(self):
        with patch.object(policy, 'connect_db', side_effect=RuntimeError('secret connection details')):
            with self.assertRaisesRegex(RuntimeError, '出品を停止') as raised:
                policy.load_category_exclusions()
        self.assertNotIn('secret', str(raised.exception))

    def dry_result(self):
        return {'asin': 'B000TEST01', 'store_code': 'rakuten_1', 'management_number': 'test',
                'listing_status': 'eligible', 'execution_allowed': True, 'item_payload': {}, 'inventory_payload': {},
                'keepa_result': self.product, 'forced_bypass_checks': [{'rule': 'category'}]}

    def test_saved_eligible_and_resume_recheck_latest_rules_before_download_or_writes(self):
        for resume in (False, True):
            download, image, item, inventory = Mock(), Mock(), Mock(), Mock()
            with patch.object(policy, 'load_category_exclusions', return_value={20: 'new exclusion'}):
                result = execute.execute_listing(execute.ExecuteListingRequest(
                    self.dry_result(), execute=True, approved=True, resume_after_item_upsert=resume),
                    image_downloader=download, image_client=image, item_client=item, inventory_client=inventory)
            self.assertEqual(result['final_state'], 'blocked')
            self.assertIn('new exclusion', result['errors'][0])
            for client in (download, image, item, inventory):
                self.assertEqual(client.mock_calls, [])

    def test_real_gate_blocks_before_cabinet_folder_or_history_writes(self):
        request = real.RealExecuteRequest(asin='B000TEST01', store='rakuten_1', management_number='test',
            readiness_json=Path('ready'), dry_run_json=Path('dry'), preflight_json=Path('preflight'),
            mock_result_json=Path('mock'), execute=True, approved=True, confirm_real_api=True, allow_live_transport=True)
        self.stack.enter_context(patch.object(real, 'load_json', side_effect=lambda path: self.dry_result() if path == Path('dry') else {}))
        self.stack.enter_context(patch.object(real, '_validate_readiness_inputs', return_value=[]))
        self.stack.enter_context(patch.object(real, '_validate_execute_guards', return_value=[]))
        self.stack.enter_context(patch.object(real, '_build_transport_ready_summary', return_value={'ready': True}))
        self.stack.enter_context(patch.object(real, '_current_history_block_reason', return_value=None))
        history = self.stack.enter_context(patch.object(real, '_write_history', side_effect=AssertionError('History write forbidden')))
        cabinet = Mock(side_effect=AssertionError('Cabinet forbidden'))
        with patch.object(policy, 'load_category_exclusions', return_value={10: 'parent'}):
            result = real.build_real_execute_result(request, cabinet_folder_resolver=cabinet)
        self.assertEqual(result['final_status'], 'blocked')
        self.assertIn('parent', result['blocking_reasons'][0])
        cabinet.assert_not_called(); history.assert_not_called()

    def test_db_unavailable_blocks_saved_eligible_before_writes(self):
        download = Mock()
        with patch.object(policy, 'load_category_exclusions', side_effect=RuntimeError('設定を取得できないため停止')):
            result = execute.execute_listing(execute.ExecuteListingRequest(self.dry_result(), execute=True, approved=True),
                                             image_downloader=download)
        self.assertEqual(result['final_state'], 'blocked')
        download.assert_not_called()

    def test_both_batch_workers_accept_required_capability_marker(self):
        from scripts import rakuten_listing_batch_execute, rakuten_listing_batch_dry_run
        for worker in (rakuten_listing_batch_execute, rakuten_listing_batch_dry_run):
            with patch('sys.argv', ['worker', '--asin-file', 'fake', '--store', 'rakuten_1', '--output-dir', 'fake',
                                    '--require-amazon-category-policy']):
                self.assertTrue(worker.parse_args().require_amazon_category_policy)


if __name__ == '__main__':
    unittest.main()
