"""Offline ranking tests: never connect to Keepa or the database."""
import ast
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/keepa_product_finder.py'

class RankingTests(unittest.TestCase):
    def setup_scope(self, responses, categories='5267102051', root='52374051', limit=50):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        names = {'comma_values', 'integer_values', 'asin_only_candidates', 'token_snapshot', 'ranking_candidates'}
        scope = {'json': json, 'ASIN_PATTERN': re.compile(r'^[A-Z0-9]{10}$'), 'KEEPA_BESTSELLERS_ENDPOINT':'bestsellers'}
        exec('from __future__ import annotations\n' + '\n'.join(ast.unparse(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names), scope)
        calls, saved = [], []
        def request(*args, **kwargs):
            calls.append(kwargs['params'])
            return responses[len(calls)-1]
        scope.update(request_json=request, save_candidates=lambda *a: saved.append(a[2]))
        args = SimpleNamespace(include_categories=categories,root_categories=root,candidate_limit=limit,run_id='test',store='test')
        return scope, args, calls, saved

    def test_direct_subcategory_and_provenance(self):
        s,a,c,w = self.setup_scope([{'bestSellersList':{'categoryId':5267102051,'asinList':['B000000001','B000000001','bad','B000000002']}}, {'bestSellersList':None}])
        result=s['ranking_candidates'](None,'test',a)
        self.assertEqual(result['candidate_count'],2)
        self.assertEqual([p['sublist'] for p in c],[0,1])
        self.assertTrue(all(p['category']==5267102051 for p in c))
        self.assertIsNone(w[-1][0]['category_id'])
        self.assertEqual(w[-1][0]['finder_selection']['ranking_sources'][0]['category_id'],5267102051)

    def test_missing_list_no_finder_fallback(self):
        s,a,c,w=self.setup_scope([{'bestSellersList':None},{'bestSellersList':None}])
        result=s['ranking_candidates'](None,'test',a)
        self.assertEqual(len(c),2)
        self.assertEqual(w[-1],[])
        self.assertFalse(result['categories'][0]['list_available'])

    def test_root_and_global_limit(self):
        s,a,c,w=self.setup_scope([{'bestSellersList':{'asinList':['B000000001','B000000002']}}],categories='1,2',root='1',limit=1)
        s['ranking_candidates'](None,'test',a)
        self.assertEqual(c[0]['sublist'],0)
        self.assertEqual(len(c),1)
        self.assertEqual(len(w[-1]),1)

    def test_cross_category_duplicate(self):
        s,a,c,w=self.setup_scope([{'bestSellersList':{'asinList':['B000000001']}},{'bestSellersList':None},{'bestSellersList':{'asinList':['B000000001','B000000002']}},{'bestSellersList':None}],categories='2,3',root='1')
        s['ranking_candidates'](None,'test',a)
        self.assertEqual(len(w[-1]),2)
        self.assertEqual(len(w[-1][0]['finder_selection']['ranking_sources']),2)

    def test_both_lists_even_when_first_fills_cap(self):
        s,a,c,w=self.setup_scope([{'bestSellersList':{'asinList':['B000000001','B000000002','B000000003']}},{'bestSellersList':{'asinList':['B000000004','B000000001']}}],limit=3)
        s['ranking_candidates'](None,'test',a)
        self.assertEqual(len(c),2)
        self.assertEqual([r['asin'] for r in w[-1]],['B000000001','B000000004','B000000002'])
        self.assertEqual([r['sublist'] for r in w[-1][0]['finder_selection']['ranking_sources']],[0,1])

    def test_empty_selection_and_bad_response(self):
        s,a,c,w=self.setup_scope([],categories='',root='')
        with self.assertRaises(ValueError): s['ranking_candidates'](None,'test',a)
        self.assertEqual(c,[])
        s,a,c,w=self.setup_scope([{'bestSellersList':{'categoryId':99}}])
        with self.assertRaises(ValueError): s['ranking_candidates'](None,'test',a)
        self.assertEqual(w,[])

    def test_main_dispatch_does_not_build_finder_query(self):
        from datetime import datetime, timezone
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        args = SimpleNamespace(ranking=True, run_id='test', store='test')
        calls = []
        scope = {'parse_args':lambda:args, 'load_keepa_api_key':lambda:'test',
                 'requests':SimpleNamespace(Session=lambda:None), 'datetime':datetime,
                 'timezone':timezone, 'json':json,
                 'ranking_candidates':lambda *a: calls.append(a) or {'candidate_count':0}}
        exec(ast.unparse(main),scope)
        self.assertEqual(scope['main'](),0)
        self.assertEqual(len(calls),1)

if __name__ == '__main__': unittest.main()
