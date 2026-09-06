import unittest
from scripts.listing.book_format import digital_book_reason, prepend_book_format
from scripts.listing.keepa_product_client import parse_keepa_product
from scripts.listing.models import KeepaProductData


class BookFormatTests(unittest.TestCase):
    def test_forced_listing_cannot_bypass_digital_guard(self):
        from scripts.listing.listing_evaluator import evaluate_listing
        result = evaluate_listing(
            asin='A', amazon_result=None,
            keepa_result=KeepaProductData('A', binding='Kindle Edition'),
            master_data=None, store_settings=None, management_number='m',
            bypass_rules={'blacklist', 'past_ng', 'prohibited_words', 'missing_attributes'},
        )
        self.assertEqual(result.listing_status, 'business_ng')
        self.assertIn('デジタル書籍', result.listing_reason)

    def test_digital_metadata(self):
        for binding in ('Kindle Edition', 'Kindle版', 'Audible Audiobook', '電子書籍'):
            self.assertTrue(digital_book_reason(KeepaProductData('A', binding=binding)))
        self.assertTrue(digital_book_reason(KeepaProductData('A', product_group='eBooks')))
        self.assertTrue(digital_book_reason(KeepaProductData('A', category_tree=[{'catId': 2250738051}])))

    def test_physical_book_about_kindle_is_not_digital(self):
        product = KeepaProductData('A', title='Kindleの使い方', binding='単行本')
        self.assertFalse(digital_book_reason(product))
        self.assertEqual(prepend_book_format('説明', product), '本商品は単行本です。<br />説明')

    def test_formats_and_unknown(self):
        for binding, label in [('Paperback', 'ペーパーバック'), ('文庫', '文庫'),
                               ('単行本（ソフトカバー）', '単行本（ソフトカバー）')]:
            product = KeepaProductData('A', binding=binding)
            once = prepend_book_format('説明', product)
            self.assertEqual(once, f'本商品は{label}です。<br />説明')
            self.assertEqual(prepend_book_format(once, product), once)
        for binding in ('', 'unknown', 'Kindle Edition'):
            self.assertEqual(prepend_book_format('説明', KeepaProductData('A', binding=binding)), '説明')

    def test_parser_retains_format(self):
        product = parse_keepa_product('A', {'binding': 'Paperback', 'productGroup': 'Book'})
        self.assertEqual(product.binding, 'Paperback')
        self.assertEqual(product.raw_summary['binding'], 'Paperback')
        self.assertEqual(product.product_group, 'Book')


if __name__ == '__main__':
    unittest.main()
