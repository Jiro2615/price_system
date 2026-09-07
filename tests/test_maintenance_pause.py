import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import maintenance_control as control
import rakuten_price_continuous_worker as price
import rakuten_inventory_continuous_worker as inventory


class PauseTests(unittest.TestCase):
    def test_unmanaged_process_does_not_query_db(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(control, 'connect_db') as connect:
            self.assertFalse(control.maintenance_pause_requested())
        connect.assert_not_called()

    def test_managed_signal(self):
        conn = MagicMock()
        cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        for value, expected in [('true', True), ('false', False), (None, False)]:
            cur.fetchone.return_value = (value,)
            with patch.object(control, 'connect_db', return_value=conn):
                self.assertEqual(control.maintenance_pause_requested('test'), expected)
            self.assertEqual(cur.execute.call_args.args[1], ('test',))

    def test_continuous_workers_honor_pause_and_stopped(self):
        for module in (price, inventory):
            for row, expected in [(('running', None), True), (('running', 'true'), False),
                                  (('stopped', None), False), (None, False)]:
                conn = MagicMock()
                conn.cursor.return_value.__enter__.return_value.fetchone.return_value = row
                with patch.object(module, 'connect_db', return_value=conn):
                    self.assertEqual(module.run_is_enabled('test'), expected)
                conn.close.assert_called_once()

    def test_paused_workers_start_no_child(self):
        for module in (price, inventory):
            with patch.object(sys, 'argv', ['worker', '--run-id', 'test']), \
                 patch.object(module, 'run_is_enabled', return_value=False), \
                 patch.object(module.subprocess, 'run') as run:
                self.assertEqual(module.main(), 0)
                run.assert_not_called()

    def test_pause_after_batch_never_starts_second_child(self):
        for module in (price, inventory):
            with patch.object(sys, 'argv', ['worker', '--run-id', 'test']), \
                 patch.object(module, 'run_is_enabled', side_effect=[True, False]), \
                 patch.object(module.subprocess, 'run', return_value=MagicMock(returncode=0)) as run:
                self.assertEqual(module.main(), 0)
                run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
