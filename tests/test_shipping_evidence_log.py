import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import price_check_one_asin_db as checker


class ShippingEvidenceTests(unittest.TestCase):
    def test_excerpt_filters_and_caps(self):
        text = '￥2,273\n無料配送 10月6日-24日にお届け\nお届け先中央区 132-8501\n通常2～4週間以内に発送します。\n数量:30'
        excerpt = checker.shipping_log_excerpt(text)
        self.assertIn('10月6日-24日', excerpt)
        self.assertIn('2～4週間', excerpt)
        self.assertNotIn('132-8501', excerpt)
        self.assertNotIn('2,273', excerpt)
        self.assertLessEqual(len(checker.shipping_log_excerpt('配送' * 1000)), 320)

    def test_one_line_and_worker(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['worker', '--worker-id', 'PC-amazon-3']), redirect_stdout(output):
            checker.log_shipping_evidence('B01BLBQZ9Q', '無料配送\n10月6日-24日', 'NG', '発送遅い')
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        data = json.loads(output.getvalue().split(' ', 1)[1])
        self.assertEqual(data['worker'], 'PC-amazon-3')
        self.assertIn('10月6日', data['text'])

    def test_logging_failure_is_nonfatal(self):
        with patch.object(checker, 'print', side_effect=OSError('closed')):
            checker.log_shipping_evidence('B01BLBQZ9Q', '', 'NG', '発送遅い')

    def test_empty(self):
        self.assertEqual(checker.shipping_log_excerpt(''), '')


if __name__ == '__main__':
    unittest.main()
