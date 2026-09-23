"""Production selection SQL against VALUES fixtures in a read-only transaction.

Opt in with AMAZON_ROTATION_READONLY_TEST=1. No production tables are accessed.
"""
import os
import unittest
from test_amazon_claim_guards import claim_sql


class RotationContractTests(unittest.TestCase):
    def test_revalidates_current_all_store_stock_and_preserves_guards(self):
        sql = claim_sql('_claim_active_listed_store_asins_without_retry')
        self.assertIn('z.stock_zero_since <= CURRENT_TIMESTAMP', sql)
        self.assertIn('FROM store_products z', sql)
        self.assertIn('COALESCE(z.current_stock, -1) = 0', sql)
        self.assertNotIn('z.store_id =', sql)
        self.assertIn('FOR UPDATE OF s SKIP LOCKED', sql)
        self.assertIn('COALESCE(ap.system_error, FALSE) = FALSE', sql)


@unittest.skipUnless(os.getenv('AMAZON_ROTATION_READONLY_TEST') == '1', 'read-only SQL tests require opt-in')
class RotationSqlTests(unittest.TestCase):
    def test_current_conditions_override_stale_interval(self):
        from db_config import connect_db
        # All identifiers below shadow persistent relations with synthetic CTEs.
        fixtures = """WITH
        fixture(asin,hours,stock,zero_age,err,status,delay) AS (VALUES
          ('restocked',36,1,'8 days',false,'done','1 hour'),
          ('recent_zero',36,0,'1 hour',false,'done','1 hour'),
          ('unknown_since',36,0,NULL,false,'done','1 hour'),
          ('unknown_stock',36,NULL,'8 days',false,'done','1 hour'),
          ('long_zero',36,0,'8 days',false,'done','1 hour'),
          ('due_long_zero',36,0,'8 days',false,'done','-1 hour'),
          ('normal_24',24,1,NULL,false,'done','1 hour'),
          ('error',36,1,NULL,true,'done','1 hour'),
          ('confirmation',0,1,NULL,false,'done','1 hour'),
          ('busy',36,1,NULL,false,'processing','1 hour'),
          ('other_store_stock',36,0,'8 days',false,'done','1 hour'),
          ('inactive_other',36,0,'8 days',false,'done','1 hour')),
        amazon_check_stats AS (
          SELECT asin,status,CURRENT_TIMESTAMP+delay::interval next_check_at,
            CURRENT_TIMESTAMP last_checked_at,100 priority_score,
            CURRENT_TIMESTAMP+interval '30 minutes' lock_expires_at,hours check_interval_hours FROM fixture),
        amazon_products AS (SELECT asin,err system_error,'' ng_reason,CURRENT_TIMESTAMP checked_at FROM fixture),
        stores(id,store_code) AS (VALUES(1,'rakuten_2'),(2,'rakuten_1')),
        store_products AS (
          SELECT asin,1 store_id,true enabled,false force_stop,'listed' current_status,
            stock current_stock,CURRENT_TIMESTAMP-zero_age::interval stock_zero_since FROM fixture
          UNION ALL SELECT 'other_store_stock',2,true,false,'listed',1,NULL::timestamptz
          UNION ALL SELECT 'inactive_other',2,false,false,'listed',1,NULL::timestamptz),
        target_rows AS (
        """
        sql = claim_sql('_claim_active_listed_store_asins_without_retry')
        selection = sql.split('WITH target_rows AS (', 1)[1].split('UPDATE amazon_check_stats s', 1)[0]
        selection = selection.replace('FOR UPDATE OF s SKIP LOCKED', '')
        query = fixtures + selection + 'SELECT asin FROM target_rows'
        with connect_db(options='-c default_transaction_read_only=on -c statement_timeout=10000',connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute(query,dict(store_code='rakuten_2',system_error_only=False,
                    reason_contains='',reason_pattern='%%',long_zero_interval_hours=36,long_zero_days=5,limit=100))
                self.assertEqual({r[0] for r in cur.fetchall()}, {
                    'restocked','recent_zero','unknown_since','unknown_stock',
                    'due_long_zero','normal_24','other_store_stock'})


if __name__ == '__main__':
    unittest.main()
