import ast
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import rakuten_inventory_bulk_upsert as inventory


class CompactOutputTests(unittest.TestCase):
    def test_large_target_log_is_bounded(self):
        rows = [{'asin': f'ASIN{i}', 'current_stock': 4, 'target_stock': 0} for i in range(5564)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            inventory.print_targets(rows)
        self.assertLess(len(output.getvalue().splitlines()), 30)
        self.assertIn('5564', output.getvalue())
        self.assertNotIn('ASIN10 ', output.getvalue())
        self.assertEqual(len(rows), 5564)

    def test_skipped_log_is_bounded(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            inventory.print_skipped_rows([({}, 'reason' * 200)] * 5564)
        self.assertLess(len(output.getvalue()), 4000)
        self.assertIn('5564', output.getvalue())

    def test_verbose_is_opt_in(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            inventory.print_targets([{'asin': f'ASIN{i}'} for i in range(11)], verbose=True)
        self.assertIn('ASIN10', output.getvalue())
        self.assertIn('amazon:', output.getvalue())

    def test_dry_run_keeps_complete_payload_without_api_write(self):
        rows = [{'asin': f'A{i}'} for i in range(5564)]
        payload = {'inventories': [{'variantId': str(i), 'quantity': 0} for i in range(5564)]}
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'plan.json'
            with patch.object(sys, 'argv', ['inventory', '--dry-run', '--output', str(destination)]), \
                 patch.object(inventory, 'fetch_inventory_targets', return_value=rows), \
                 patch.object(inventory, 'split_safe_and_skipped_rows', return_value=(rows, [])), \
                 patch.object(inventory, 'build_payload', return_value=payload) as build, \
                 patch.object(inventory, 'call_inventory_bulk_upsert') as send, \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(inventory.main(), 0)
                build.assert_called_once_with(rows)
                send.assert_not_called()
                self.assertIn('inventory_target_count: 5564', output.getvalue())
            self.assertEqual(json.loads(destination.read_text(encoding='utf-8')), payload)

    def test_source_parses(self):
        ast.parse(Path(inventory.__file__).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
