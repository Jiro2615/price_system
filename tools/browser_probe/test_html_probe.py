import unittest
from unittest.mock import Mock
from html_probe import extract, compare, fetch, price_number


class HtmlTests(unittest.TestCase):
    def test_discount_percentage_is_not_price(self):
        self.assertEqual(price_number('9パーセントの割引で￥899'), 899)
        self.assertIsNone(price_number('9パーセント'))
    def test_absence_is_unknown_not_zero_or_false(self):
        result = extract('<span id="productTitle">Test</span><select id="quantity"><option>30</option></select>', 'B07QP2L8LC')
        self.assertIsNone(result['candidates']['available_qty'])
        self.assertIsNone(result['candidates']['gift_available'])
        self.assertIsNone(result['candidates']['amazon_point'])
        self.assertTrue(result['requires_shell'])

    def test_explicit_price_and_stock(self):
        result = extract('''<input id="ASIN" value="B07QP2L8LC"><span id="productTitle">Test</span>
        <div id="corePriceDisplay_desktop_feature_div"><span class="a-price"><span class="a-offscreen">￥1,234</span></span></div>
        <div id="availability">残り3点</div>''', 'B07QP2L8LC')
        self.assertTrue(result['identity_verified'])
        self.assertEqual(result['candidates']['amazon_price'], 1234)
        self.assertEqual(result['candidates']['available_qty'], 3)

    def test_identity_mismatch_not_comparable(self):
        result = extract('<input id="ASIN" value="B019SKZXV8">', 'B07QP2L8LC')
        self.assertEqual(compare(result, {'amazon_price': 1})['status'], 'not_comparable')

    def test_empty_offscreen_uses_explicit_price_to_pay(self):
        result = extract('''<div id="corePriceDisplay_desktop_feature_div">
        <span class="a-price"><span class="a-offscreen"> </span></span>
        <span id="apex-pricetopay-accessibility-label">￥7,226</span></div>''', 'B07QP2L8LC')
        self.assertEqual(result['candidates']['amazon_price'], 7226)

    def test_matching_candidates_never_certify_conditions(self):
        result = {'identity_verified': True, 'candidates': {'amazon_price': 100, 'gift_available': None}}
        output = compare(result, {'amazon_price': 100, 'gift_available': False})
        self.assertEqual(output['fields']['amazon_price'], 'candidate_match')
        self.assertEqual(output['fields']['gift_available'], 'unknown')
        self.assertFalse(output['conditions_verified'])

    def test_redirect_outside_amazon_stops(self):
        session = Mock()
        session.get.return_value = Mock(status_code=302, headers={'Location': 'https://example.com/'})
        with self.assertRaises(RuntimeError):
            fetch(session, 'B07QP2L8LC')
        self.assertEqual(session.get.call_count, 1)

    def test_challenge_stops_without_retry(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, content=b'validateCaptcha', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            fetch(session, 'B07QP2L8LC')
        self.assertEqual(session.get.call_count, 1)

    def test_normal_navigation_phrase_is_not_a_challenge(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, content=b'<span id="productTitle">Test</span>Continue shopping', encoding='utf-8')
        self.assertIn('productTitle', fetch(session, 'B07QP2L8LC')[0])


if __name__ == '__main__':
    unittest.main()
