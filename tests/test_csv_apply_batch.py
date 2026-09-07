import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import apply_rakuten_csv_success_to_db as apply


class BatchTests(unittest.TestCase):
    def test_commit_per_batch_and_columns_once(self):
        conn = MagicMock()
        with patch.object(apply, 'get_existing_columns', return_value={'asin'}) as columns, \
             patch.object(apply, 'fetch_current_rows', side_effect=lambda c,s,t:t), \
             patch.object(apply, 'apply_updates', side_effect=lambda c,r,*a,**k:(len(r),0)):
            self.assertEqual(apply.apply_targets(conn, 'rakuten_1', list(range(1201)), False, True), (1201,0))
        self.assertEqual(conn.commit.call_count, 3)
        columns.assert_called_once()

    def test_dry_run_never_commits_or_reads_log_schema(self):
        conn = MagicMock()
        with patch.object(apply, 'get_existing_columns') as columns, \
             patch.object(apply, 'fetch_current_rows', return_value=[]):
            apply.apply_targets(conn, 'test', [1], False, False)
        conn.commit.assert_not_called()
        columns.assert_not_called()

    def test_failure_preserves_prior_batch_and_raises(self):
        conn = MagicMock()
        with patch.object(apply, 'get_existing_columns', return_value=set()), \
             patch.object(apply, 'fetch_current_rows', return_value=[]), \
             patch.object(apply, 'apply_updates', side_effect=[(500,0), RuntimeError('failure')]):
            with self.assertRaises(RuntimeError):
                apply.apply_targets(conn, 'test', list(range(600)), False, True)
        conn.commit.assert_called_once()
        conn.rollback.assert_called_once()

    def test_lookup_batches_and_store_scope(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = []
        rows = apply.fetch_current_rows(conn, 'rakuten_2', [{'mall_item_code':str(i),'sku_code':str(i)} for i in range(501)])
        self.assertEqual(cur.execute.call_count, 2)
        self.assertEqual(cur.execute.call_args.args[1][-1], 'rakuten_2')
        self.assertEqual(len(rows), 501)
        self.assertFalse(any(r['found'] for r in rows))

    def test_price_only_update_does_not_change_stock_and_duplicate_last_wins(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [(1,)]
        rows = [{'found':True,'store_product_id':1,'new_price':p,'new_stock':2} for p in [1000,1200]]
        with patch.object(apply, 'insert_batch_logs'):
            self.assertEqual(apply.apply_updates(conn, rows, False, True, log_columns=set()), (1,1))
        self.assertEqual(conn.cursor.return_value.__enter__.return_value.execute.call_args.args[1], ([1],[1200],[None]))


if __name__ == '__main__':
    unittest.main()
