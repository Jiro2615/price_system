import unittest
from unittest.mock import patch
from scripts.listing import listing_duplicate_check as duplicate


class Cursor:
    def __init__(self,ready=True,reservations=None):
        self.ready=ready; self.reservations=reservations or []; self.sql=''; self.history=[]
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def cursor(self):return self
    def execute(self,sql,params=None):self.sql=sql;self.history.append((sql,params))
    def fetchone(self):return (self.ready,) if 'to_regclass' in self.sql else None
    def fetchall(self):return self.reservations if 'listing_asin_replacements' in self.sql else []


class ReplacementReservationsTests(unittest.TestCase):
    def test_partial_replacement_blocks_normal_listing(self):
        cur=Cursor(reservations=[('B000NEW001','item1')])
        with patch.object(duplicate,'connect_db',return_value=cur):
            result=duplicate.find_existing_listing('B000NEW001','rakuten_1')
        self.assertTrue(result['replacement_reserved'])
        self.assertEqual(result['management_number'],'item1')
        self.assertNotIn('needs_attention',cur.history[-1][0].split('NOT IN')[1])

    def test_batch_precheck_also_respects_reservation(self):
        cur=Cursor(reservations=[('B000NEW001','item1')])
        with patch.object(duplicate,'connect_db',return_value=cur):
            result=duplicate.find_existing_listings(['B000NEW001'],'rakuten_1')
        self.assertTrue(result['B000NEW001']['replacement_reserved'])

    def test_legacy_database_without_feature_is_supported(self):
        cur=Cursor(ready=False)
        with patch.object(duplicate,'connect_db',return_value=cur):
            self.assertIsNone(duplicate.find_existing_listing('B000NEW001','rakuten_1'))
        self.assertFalse(any('FROM listing_asin_replacements' in sql for sql,_ in cur.history))
