import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import calc_store_targets as calc


class RecalcBulkTests(unittest.TestCase):
    def test_batches_keep_every_result(self):
        conn = MagicMock()
        rows = list(range(1201))
        with patch.object(calc, 'fetch_calc_targets', return_value=rows), \
             patch.object(calc, 'calc_target_for_row', side_effect=lambda i: {'store_product_id': i, 'target_price': 1000, 'target_stock': 4}), \
             patch.object(calc, 'update_target_batch', side_effect=lambda c, targets: {targets[0]['store_product_id']}) as update:
            result = calc.recalc_targets(conn)
        self.assertEqual([len(call.args[1]) for call in update.call_args_list], [500,500,201])
        self.assertEqual(len(result['targets']),1201)
        self.assertEqual(result['updated'],1201)
        self.assertEqual(result['db_updated_count'],3)
        conn.commit.assert_called_once()

    def test_dry_run_never_updates(self):
        conn = MagicMock()
        with patch.object(calc,'fetch_calc_targets',return_value=[1]), \
             patch.object(calc,'calc_target_for_row',return_value={'store_product_id':1}), \
             patch.object(calc,'update_target_batch') as update:
            result=calc.recalc_targets(conn,dry_run=True)
        update.assert_not_called()
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()
        self.assertEqual(len(result['targets']),1)

    def test_db_failure_rolls_back_and_raises(self):
        conn=MagicMock()
        with patch.object(calc,'fetch_calc_targets',return_value=[1]), \
             patch.object(calc,'calc_target_for_row',return_value={'store_product_id':1}), \
             patch.object(calc,'update_target_batch',side_effect=RuntimeError('DB failure')):
            with self.assertRaisesRegex(RuntimeError,'DB failure'):
                calc.recalc_targets(conn)
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_null_safe_update(self):
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value=[(2,)]
        result=calc.update_target_batch(conn,[{'store_product_id':2,'target_price':None,'target_stock':0}])
        sql,params=cur.execute.call_args.args
        self.assertIn('IS DISTINCT FROM',sql)
        self.assertEqual(params,([2],[None],[0]))
        self.assertEqual(result,{2})

    def test_cli_writes_full_results_with_short_log(self):
        summary={'rows':1201,'updated':1201,'errors':0,'db_updated_count':2,'targets':[{'asin':str(i)} for i in range(1201)]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'result.json'
            with patch.object(sys,'argv',['calc','--output',str(path)]),patch.object(calc,'connect_db'),patch.object(calc,'recalc_targets',return_value=summary),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(calc.main(),0)
            self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))['targets']),1201)
            self.assertLess(len(output.getvalue().splitlines()),5)


if __name__=='__main__': unittest.main()
