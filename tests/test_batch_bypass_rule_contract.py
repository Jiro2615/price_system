"""Check argument parsing without importing browsers, DB clients, or API code."""
import ast
import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def parser_scope():
    source = ROOT / 'scripts/rakuten_listing_batch_dry_run.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FORCE_BYPASS_RULES' for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name == 'parse_bypass_rules')]
    scope = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
    return scope

class BypassContractTests(unittest.TestCase):
    def test_web_payload_rules_accepted(self):
        rules = ('blacklist', 'past_ng', 'prohibited_words', 'missing_attributes',
                 'seller_count', 'regulated_evidence', 'rakuten_marketplace_evidence')
        self.assertEqual(parser_scope()['parse_bypass_rules'](','.join(rules)), rules)

    def test_unknown_rule_still_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsupported ignore rules'):
            parser_scope()['parse_bypass_rules']('unrecognized_rule')

    def test_normal_listing_does_not_bypass_anything(self):
        self.assertEqual(parser_scope()['parse_bypass_rules'](''), ())

    def test_whitespace_and_duplicates(self):
        self.assertEqual(parser_scope()['parse_bypass_rules'](' rakuten_marketplace_evidence, ,rakuten_marketplace_evidence '), ('rakuten_marketplace_evidence',))

    def test_execute_uses_shared_parser(self):
        tree = ast.parse((ROOT/'scripts/rakuten_listing_batch_execute.py').read_text(encoding='utf-8-sig'))
        self.assertTrue(any(isinstance(n, ast.ImportFrom) and n.module == 'scripts.rakuten_listing_batch_dry_run'
                            and any(x.name == 'parse_bypass_rules' for x in n.names) for n in tree.body))
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'parse_bypass_rules' for n in ast.walk(tree)))

    def test_both_cli_parsers_validate_threshold_and_default_to_five(self):
        shared_tree = ast.parse((ROOT / 'scripts/rakuten_listing_batch_dry_run.py').read_text(encoding='utf-8-sig'))
        shared = next(n for n in shared_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'parse_minimum_rakuten_shops')
        for filename in ('rakuten_listing_batch_dry_run.py', 'rakuten_listing_batch_execute.py'):
            tree = ast.parse((ROOT / 'scripts' / filename).read_text(encoding='utf-8-sig'))
            parser = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'parse_args')
            scope = {'argparse': argparse, 'Path': Path, 'MAX_ASINS': 10000, '__doc__': ''}
            exec(compile(ast.Module(body=[shared, parser], type_ignores=[]), filename, 'exec'), scope)
            base = ['test', '--asin-file', 'asins.txt', '--store', 'shop', '--output-dir', 'unused']
            for value in (None, '1', '3', '30'):
                with self.subTest(filename=filename, value=value), patch.object(sys, 'argv', base + ([] if value is None else ['--minimum-rakuten-shops', value])):
                    self.assertEqual(scope['parse_args']().minimum_rakuten_shops, 5 if value is None else int(value))
            for value in ('0', '-1', '31', '2.5', 'abc'):
                with self.subTest(filename=filename, value=value), patch.object(sys, 'argv', base + ['--minimum-rakuten-shops', value]), patch('sys.stderr'):
                    with self.assertRaises(SystemExit):
                        scope['parse_args']()

if __name__ == '__main__': unittest.main()
