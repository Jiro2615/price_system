"""Fail-safe target calculation, including older persisted mismatch errors."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
from amazon_result_classification import classify_purchase_restriction
from calc_store_targets import calc_target_for_row


def row(reason, system_error=True, business_ng=False):
    return (1, 'rakuten_1', True, None, 'amount', False, .116, 10, 0, 4,
            'B08713SQHV', 'manage', 'sku', 3372, 4, False, 2690, 0, 30,
            business_ng, system_error, reason, None, None, '', 0, 0, None,
            0, 0, .116, 0, 10, False, None, False, False, 0, 0, None, None)


class IdentityStockTests(unittest.TestCase):
    def test_new_and_legacy_mismatches_always_target_stock_zero(self):
        for reason in ('ASIN不一致 current=B0DXPWV7XS', 'ASIN不一致（別商品へ遷移）',
                       'ASIN不一致 指定=B08713SQHV / 選択商品=B0DXPWV7XS', 'ASIN未確認 指定=B08713SQHV'):
            with self.subTest(reason=reason):
                classified = classify_purchase_restriction({'ng_reason': reason, 'system_error': True})
                self.assertTrue(classified['business_ng'])
                self.assertFalse(classified['system_error'])
                # Even an older DB row with system_error=True must not preserve 4.
                target = calc_target_for_row(row(reason))
                self.assertEqual(target['target_stock'], 0)
                self.assertIsNone(target['target_price'])

    def test_unrelated_technical_errors_keep_existing_stock(self):
        target = calc_target_for_row(row('Timeout 60000ms exceeded'))
        self.assertEqual(target['target_stock'], 4)
        self.assertIsNone(target['target_price'])

    def test_valid_purchase_still_uses_normal_stock_cap(self):
        self.assertEqual(calc_target_for_row(row('', system_error=False))['target_stock'], 4)


if __name__ == '__main__':
    unittest.main()
