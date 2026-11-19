import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'discover_amazon_stores.py'
spec = importlib.util.spec_from_file_location('discover', SCRIPT)
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)


class DiscoveryTests(unittest.TestCase):
    def test_shipping_notice_is_not_challenge(self):
        notice = '<td>特定の商品へのアクセスが集中した場合、システムの都合上、受注時間に誤差が生じる可能性がございます。</td>'
        self.assertFalse(discovery.has_access_challenge(notice))
        for warning in ['現在アクセスが集中しています。', 'captcha', 'ロボットではないことを確認']:
            self.assertTrue(discovery.has_access_challenge(notice + '<p>' + warning + '</p>'))
        self.assertTrue(discovery.has_access_challenge('<h1>アクセスが集中しています</h1>'))

    def test_503_backoff_then_success(self):
        def response(status, body=b'ok', headers=None):
            r = discovery.requests.Response()
            r.status_code = status
            r._content = body
            r._content_consumed = True
            r.headers.update(headers or {})
            return r
        fetch = discovery.Fetcher(10)
        with patch.object(fetch.session, 'get', side_effect=[response(503), response(503, headers={'Retry-After': '900'}), response(200)]), patch.object(discovery.time, 'sleep') as sleep:
            self.assertEqual(fetch.get('https://example.test'), 'ok')
            waits = [c.args[0] for c in sleep.call_args_list]
            self.assertEqual(sum(waits), 1200)
            self.assertLessEqual(max(waits), 60)
        fetch.session.close()

    def test_503_challenge_and_429_stop(self):
        for status, body in [(503, b'captcha'), (429, b'limited'), (403, b'forbidden')]:
            r = discovery.requests.Response()
            r.status_code = status
            r._content = body
            r._content_consumed = True
            fetch = discovery.Fetcher(10)
            with patch.object(fetch.session, 'get', return_value=r) as get, patch.object(discovery.time, 'sleep'):
                with self.assertRaises(RuntimeError):
                    fetch.get('https://example.test')
                self.assertEqual(get.call_count, 1)
            fetch.session.close()

    def test_snowball_dedup_and_fairness(self):
        state = {'seeds': ['OWN'], 'snow_queries': [], 'expanded_shops': [],
                 'seed_product_urls': [], 'search_done': [], 'snow_streak': 0}
        products = [{'rakuten_url': f'https://item.rakuten.co.jp/shop/{i}/', 'rakuten_title': f'Product {i}'} for i in range(12)]
        products += [products[0], {'rakuten_url': 'https://item.rakuten.co.jp/foreign/1/', 'rakuten_title': 'Foreign'}]
        discovery.expand_shop(state, 'shop', products, 8)
        self.assertEqual(len(state['snow_queries']), 8)
        discovery.expand_shop(state, 'shop', products, 8)
        self.assertEqual(len(state['snow_queries']), 8)
        self.assertEqual(discovery.term_key('ＡＢＣ　test'), discovery.term_key('abc test'))
        sources = []
        for _ in range(4):
            key, page, query = discovery.next_query(state, 1, True)
            sources.append(query['source'])
            state['search_done'].append(key)
        self.assertEqual(sources, ['candidate', 'candidate', 'candidate', 'own'])

    def test_snowball_live_flow_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            keywords = folder / 'keywords.txt'
            keywords.write_text('Own seed', encoding='utf-8')
            argv = ['discover', '--keywords', str(keywords), '--output-dir', str(folder/'out'),
                    '--snowball', '--target-candidates', '2', '--execute']
            def inspected(fetch, slug, entry):
                return {'sid': slug, 'eligible': True, 'first_product': entry['product'],
                        'row': {'店舗ID': slug},
                        'products': [{'rakuten_url': entry['product'], 'rakuten_title': f'New product {slug}'}]}
            with patch.object(discovery.sys, 'argv', argv), patch.object(discovery, 'inspect_shop', side_effect=inspected), patch.object(discovery.Fetcher, 'get', side_effect=[
                    '<a href="https://item.rakuten.co.jp/a/1/">First</a>',
                    '<a href="https://item.rakuten.co.jp/b/1/">Second</a>']) as fetch:
                discovery.main()
                self.assertEqual(fetch.call_count, 2)
            state = json.loads((folder/'out'/'state.json').read_text(encoding='utf-8'))
            self.assertEqual(len(state['results']), 2)
            self.assertEqual(state['queue']['b']['source_shop'], 'a')
            self.assertEqual(state['source_stats']['candidate']['candidates'], 1)
            with patch.object(discovery.sys, 'argv', argv), patch.object(discovery.Fetcher, 'get') as fetch:
                discovery.main()
                fetch.assert_not_called()

    def test_missing_product_continues_without_negative_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            keywords = folder/'keywords.txt'
            keywords.write_text('test', encoding='utf-8')
            argv = ['discover', '--keywords', str(keywords), '--output-dir', str(folder/'out'), '--execute']
            response = discovery.requests.Response()
            response.status_code = 404
            error = discovery.requests.HTTPError('gone', response=response)
            result = {'sid': '2', 'eligible': False, 'first_product': 'url', 'row': None, 'products': []}
            with patch.object(discovery.sys, 'argv', argv), patch.object(discovery.Fetcher, 'get', return_value='<a href="https://item.rakuten.co.jp/gone/1/">gone</a><a href="https://item.rakuten.co.jp/ok/1/">ok</a>'), patch.object(discovery, 'inspect_shop', side_effect=[error, result]):
                discovery.main()
            state = json.loads((folder/'out'/'state.json').read_text(encoding='utf-8'))
            self.assertIn('gone', state['errors'])
            self.assertNotIn('gone', state['done'])
            self.assertIn('ok', state['done'])

    def test_seed_diversity_and_dedup(self):
        rows = [{'title': 'A', 'brand': 'one'}, {'title': 'B', 'brand': 'one'},
                {'title': 'C', 'brand': 'two'}, {'title': 'a', 'brand': 'other'}]
        self.assertEqual(discovery.select_seeds(rows, 3), ['A', 'C', 'B'])

    def test_sid(self):
        html = '<script id="item-page-app-data" type="application/json">{"api":{"data":{"itemInfoSku":{"shopId":"253414"}}}}</script>'
        self.assertEqual(discovery.sid_from_html(html), '253414')
        self.assertEqual(discovery.sid_from_html('<a href="https://evil.example/?sid=123">x</a>'), '')
        self.assertEqual(discovery.sid_from_html('<a href="https://review.rakuten.co.jp/shop/4/427886_1.1/">review</a>'), '427886')

    def test_metadata_ignores_product_rating(self):
        product = '<script type="application/ld+json">{"@type":"Product","aggregateRating":{"ratingValue":4.9}}</script>'
        row = discovery.store_metadata('<title>Shop</title><meta name="description" content="About">', '全 12,345 件', product)
        self.assertEqual(row['出品数'], '12345')
        self.assertEqual(row['評価'], '')
        row = discovery.store_metadata('', '', product.replace('Product', 'Store'))
        self.assertEqual(row['評価'], '4.9')

    def test_keyword_compatible(self):
        self.assertTrue(discovery.amazon_keyword_context('<p>Amazon配送サービスを利用</p>')[0])
        self.assertFalse(discovery.amazon_keyword_context('<p>normal</p>')[0])

    def test_live_search_header_shape(self):
        html = '''<div class="content"><div class="description shop">
          <h2 class="item title"><a>ECプライム</a></h2>
          <a href="https://review.rakuten.co.jp/shop/4/429519_429519/1.1/">
            <span class="score">4.42</span><span>138件</span></a></div>
          <div class="description text">雑貨を中心に様々なものを手ごろな価格でお届けします。</div></div>
          <div>検索結果 <span>1〜45件 （42,757件）</span></div>
          <div class="score">4.99</div>'''
        row = discovery.store_metadata('<meta name="description" content="定型文">', html, '')
        self.assertEqual(row['店舗名'], 'ECプライム')
        self.assertEqual(row['評価'], '4.42')
        self.assertEqual(row['評価数'], '138')
        self.assertEqual(row['出品数'], '42757')
        self.assertTrue(row['店舗紹介文'].startswith('雑貨を中心'))

    def test_no_boilerplate_or_product_score(self):
        row = discovery.store_metadata('<meta name="description" content="人気商品を多数">', '<span class="score">4.99</span>', '')
        self.assertEqual(row['店舗紹介文'], '')
        self.assertEqual(row['評価'], '')

    def test_review_count_is_shop_only_and_missing_is_not_zero(self):
        template = '<div class="description shop"><a href="https://review.rakuten.co.jp/shop/4/123/"><span class="score">4.5</span><span class="legend">(%s件)</span></a></div><a href="https://review.rakuten.co.jp/item/1/123/">999件</a>全 888 件'
        for raw, expected in [('1,234', '1234'), ('0', '0')]:
            self.assertEqual(discovery.store_metadata('', template % raw, '')['評価数'], expected)
        self.assertEqual(discovery.store_metadata('', '<a href="https://review.rakuten.co.jp/item/1/123/">999件</a>全 888 件', '')['評価数'], '')

    def test_tsv_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {'results': [{'店舗名': '日本語\t店', '店舗紹介文': '紹介\n文'}]}
            discovery.save(Path(tmp), state)
            text = (Path(tmp) / 'stores.tsv').read_text(encoding='utf-8-sig')
            self.assertIn('日本語 店', text)
            self.assertEqual(len(text.splitlines()), 2)
            self.assertEqual(json.loads((Path(tmp) / 'state.json').read_text(encoding='utf-8')), state)

    def test_execute_exclusion_and_resume_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            keywords = folder / 'keywords.txt'
            keywords.write_text('test', encoding='utf-8')
            argv = ['discover', '--keywords', str(keywords), '--output-dir', str(folder / 'out'),
                    '--exclude-shop', 'own', '--execute']
            search = '<a href="https://item.rakuten.co.jp/own/a/">own</a><a href="https://item.rakuten.co.jp/other/b/">other</a>'
            item = '<script id="item-page-app-data" type="application/json">{"api":{"data":{"itemInfoSku":{"shopId":"123"}}}}</script><p>Amazon配送</p>'
            store = '<div class="content"><div class="description shop"><h2 class="title"><a>Other</a></h2><a href="https://review.rakuten.co.jp/shop/4/123/"><span class="score">4.5</span></a></div><div class="description text">店舗紹介</div></div>検索結果 1〜45件（100件）<a href="https://item.rakuten.co.jp/other/b/">b</a>'
            with patch.object(discovery.sys, 'argv', argv), patch.object(discovery.Fetcher, 'get', side_effect=[search,item,store]) as fetch:
                discovery.main()
                self.assertEqual(fetch.call_count, 3)
            state = json.loads((folder/'out'/'state.json').read_text(encoding='utf-8'))
            self.assertEqual(state['excluded_shops'], ['own'])
            self.assertEqual(len(state['results']), 1)
            self.assertEqual(state['results'][0]['出品数'], '100')
            # Explicit exclusions survive omission on resume.
            argv = argv[:-3] + ['--execute']
            with patch.object(discovery.sys, 'argv', argv), patch.object(discovery.Fetcher, 'get') as fetch:
                discovery.main()
                fetch.assert_not_called()
            state['search_done'] = []
            discovery.save(folder/'out', state)
            with patch.object(discovery.sys, 'argv', argv + ['--target-candidates', '1']), patch.object(discovery.Fetcher, 'get') as fetch:
                discovery.main()
                fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
