"""Calculation schema reads stay fresh and fail closed; no database access."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import calc_store_targets as calc


MANDATORY = [('column', 'stores', 'max_stock')]
FULL = MANDATORY + [('table', t, None) for t in
                   ('store_settings', 'rakuten_competitor_price_snapshots', 'asin_fixed_price_settings')] + [
    ('column', 'store_settings', name) for name in
    ('rakuten_competitor_price_enabled', 'rakuten_competitor_floor_enabled',
     'rakuten_competitor_undercut_enabled', 'rakuten_competitor_undercut_yen', 'rakuten_competitor_min_profit_amount')]


def connection(schema):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    def rows():
        sql = cur.execute.call_args.args[0]
        return list(schema) if 'information_schema' in sql else [('unchanged calculation inputs',)]
    cur.fetchall.side_effect = rows
    return conn, cur


class TargetSchemaTests(unittest.TestCase):
    def test_one_capability_query_plus_fresh_product_and_setting_query(self):
        conn, cur = connection(FULL)
        with patch.object(calc, 'has_table', side_effect=AssertionError('old per-field query')), \
             patch.object(calc, 'has_table_column', side_effect=AssertionError('old per-field query')):
            result = calc.fetch_calc_targets(conn, 'rakuten_2', ['B000000001'])
        self.assertEqual(result, [('unchanged calculation inputs',)])
        self.assertEqual(cur.execute.call_count, 2)
        sql, params = cur.execute.call_args.args
        self.assertEqual(params, ['rakuten_2', ['B000000001']])
        self.assertIn('ss.rakuten_competitor_undercut_yen', sql)
        self.assertIn('LEFT JOIN asin_fixed_price_settings', sql)
        self.assertIn('FROM rakuten_competitor_price_snapshots', sql)
        self.assertIn('sp.enabled = TRUE', sql)
        conn.commit.assert_not_called()

    def test_missing_max_stock_stops_without_running_product_query(self):
        conn, cur = connection(FULL[1:])
        with self.assertRaisesRegex(RuntimeError, 'stores.max_stock'):
            calc.fetch_calc_targets(conn)
        self.assertEqual(cur.execute.call_count, 1)

    def test_optional_tables_keep_legacy_defaults(self):
        conn, cur = connection(MANDATORY)
        calc.fetch_calc_targets(conn)
        sql = cur.execute.call_args.args[0]
        self.assertIn('FALSE AS rakuten_competitor_price_enabled', sql)
        self.assertIn('0 AS rakuten_competitor_undercut_yen', sql)
        self.assertIn('NULL::integer AS fixed_price', sql)
        self.assertNotIn('LEFT JOIN store_settings', sql)
        self.assertNotIn('FROM rakuten_competitor_price_snapshots', sql)

    def test_optional_columns_are_independent(self):
        schema = MANDATORY + [('table', 'store_settings', None),
                              ('column', 'store_settings', 'rakuten_competitor_floor_enabled')]
        conn, cur = connection(schema)
        calc.fetch_calc_targets(conn)
        sql = cur.execute.call_args.args[0]
        self.assertIn('COALESCE(ss.rakuten_competitor_floor_enabled, FALSE)', sql)
        self.assertIn('FALSE AS rakuten_competitor_undercut_enabled', sql)
        self.assertIn("ss.order_fulfillment_settings_json->>'rakuten_target_price_floor'", sql)

    def test_capabilities_are_rechecked_each_call_and_not_shared_across_connections(self):
        schema = list(MANDATORY)
        conn, cur = connection(schema)
        calc.fetch_calc_targets(conn)
        schema[:] = FULL
        calc.fetch_calc_targets(conn)
        self.assertEqual(cur.execute.call_count, 4)
        self.assertIn('LEFT JOIN asin_fixed_price_settings', cur.execute.call_args.args[0])
        other, other_cur = connection(MANDATORY)
        calc.fetch_calc_targets(other)
        self.assertNotIn('LEFT JOIN asin_fixed_price_settings', other_cur.execute.call_args.args[0])

    def test_catalog_failure_is_not_converted_to_permissive_defaults(self):
        conn, cur = connection(FULL)
        cur.execute.side_effect = RuntimeError('connection lost')
        with self.assertRaisesRegex(RuntimeError, 'connection lost'):
            calc.fetch_calc_targets(conn)
        self.assertEqual(cur.execute.call_count, 1)

    def test_catalog_query_keeps_public_schema_and_permission_aware_views(self):
        conn, cur = connection(FULL)
        tables, columns = calc.fetch_target_schema(conn)
        sql, params = cur.execute.call_args.args
        self.assertEqual(cur.execute.call_count, 1)
        self.assertEqual(sql.count("table_schema = 'public'"), 2)
        self.assertIn('information_schema.tables', sql)
        self.assertIn('information_schema.columns', sql)
        self.assertEqual(tables, {'store_settings', 'rakuten_competitor_price_snapshots', 'asin_fixed_price_settings'})
        self.assertIn(('stores', 'max_stock'), columns)
        self.assertEqual(len(params[1]), 5)


if __name__ == '__main__':
    unittest.main()
