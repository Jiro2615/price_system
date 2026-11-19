import unittest
from condition_probe import html_conditions


class ConditionTests(unittest.TestCase):
    def test_regular_row_not_subscription(self):
        html = '''<input id="ASIN" value="B019SKZXV8">
        <div data-a-accordion-row-name="snsAccordionRowMiddle">定期便 ￥790</div>
        <div data-a-accordion-row-name="newAccordionRow">1回限りの購入 ￥929 お届け先名古屋 461-0001</div>'''
        result = html_conditions(html, 'B019SKZXV8')
        self.assertEqual(result['regular_row_candidate']['price'], 929)
        self.assertFalse(result['regular_row_candidate']['certified_for_production'])
        self.assertEqual(result['destination_evidence'], 'お届け先名古屋 461-0001')

    def test_no_regular_row_is_unknown(self):
        result = html_conditions('<div>在庫なし</div>', 'B07QP2L8LC')
        self.assertIsNone(result['regular_row_candidate'])
        self.assertTrue(result['requires_shell'])


if __name__ == '__main__':
    unittest.main()
