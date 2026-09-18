"""Check argument parsing without importing browsers, DB clients, or API code."""
import ast
from pathlib import Path
import unittest

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

if __name__ == '__main__': unittest.main()
