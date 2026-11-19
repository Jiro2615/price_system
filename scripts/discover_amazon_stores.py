"""Read-only store discovery. No browser, marketplace writes or DB updates."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from email.utils import parsedate_to_datetime
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rakuten_competitor_researcher import (
    amazon_keyword_context, decode_response, normalize_space, parse_store_products,
)
import requests
from bs4 import BeautifulSoup

FIELDS = ['店舗名', '評価', '評価数', '出品数', '店舗紹介文', '店舗URL', '店舗ID',
          '判定', '判定根拠', '確認商品URL', '検索語', '取得日時', '未取得項目', '検索元', '検索元店舗']


def term_key(term):
    return normalize_space(unicodedata.normalize('NFKC', term)).casefold()


def expand_shop(state, slug, products, limit):
    """Use only the already fetched first shop page, spread across its products."""
    if slug in state['expanded_shops']:
        return
    seen = {term_key(t) for t in state['seeds']}
    seen.update(term_key(q['term']) for q in state['snow_queries'])
    urls = set(state['seed_product_urls'])
    options = []
    for product in products:
        url = product['rakuten_url']
        title = normalize_space(product.get('rakuten_title', ''))
        key = term_key(title)
        if urlsplit(url).path.split('/')[1] != slug or len(title) < 4 or key in seen or url in urls:
            continue
        seen.add(key)
        urls.add(url)
        options.append((title, url))
    count = min(limit, len(options), max(0, 1000 - len(state['snow_queries'])))
    for i in range(count):
        title, url = options[i * len(options) // count]
        state['snow_queries'].append({'term': title, 'source': 'candidate', 'source_shop': slug})
        state['seed_product_urls'].append(url)
    state['expanded_shops'].append(slug)
    print(f'Expanded {slug}: {count} search terms', flush=True)


def next_query(state, pages, snowball):
    def pending(items, prefix):
        for index, item in enumerate(items):
            for page in range(1, pages + 1):
                key = f'{prefix}{index}:{page}'
                if key not in state['search_done']:
                    return key, page, item
    own = pending([{'term': t, 'source': 'own', 'source_shop': ''} for t in state['seeds']], '')
    snow = pending(state['snow_queries'], 'snow:') if snowball else None
    if snow and (not own or state['snow_streak'] < 3):
        state['snow_streak'] += 1
        return snow
    if own:
        state['snow_streak'] = 0
    return own


def inspect_shop(fetch, slug, entry):
    discovered = fetch.get(entry['product'])
    sid = sid_from_html(discovered)
    if not sid:
        return {'error': 'Store ID not found'}
    url = f'https://search.rakuten.co.jp/search/mall/?sid={sid}'
    search = fetch.get(url)
    products = [p for p in parse_store_products(search)
                if urlsplit(p['rakuten_url']).path.split('/')[1] == slug]
    if not products:
        return {'error': 'First product not found'}
    first = products[0]['rakuten_url']
    eligible, evidence = amazon_keyword_context(discovered if first == entry['product'] else fetch.get(first))
    row = None
    if eligible:
        row = store_metadata('', search, '')
        missing = [k for k, v in row.items() if not v]
        row.update({'店舗URL': url, '店舗ID': sid, '判定': 'Amazon関連語あり（候補）',
                    '判定根拠': evidence, '確認商品URL': first, '検索語': entry['term'],
                    '取得日時': time.strftime('%Y-%m-%dT%H:%M:%S%z'), '未取得項目': ','.join(missing),
                    '検索元': entry.get('source', 'own'), '検索元店舗': entry.get('source_shop', '')})
    return {'sid': sid, 'eligible': eligible, 'first_product': first, 'row': row, 'products': products}


def select_seeds(rows, limit):
    groups = defaultdict(deque)
    seen = set()
    for row in rows:
        title = normalize_space(row.get('title', ''))
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        groups[(str(row.get('genre') or ''), str(row.get('brand') or ''))].append(title)
    result = []
    while groups and len(result) < limit:
        for key in list(groups):
            result.append(groups[key].popleft())
            if not groups[key]:
                del groups[key]
            if len(result) == limit:
                break
    return result


def db_seeds(store, limit):
    from scripts.db_config import connect_db
    with connect_db(options='-c default_transaction_read_only=on', connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT COALESCE(NULLIF(to_jsonb(ap)->>'title',''),sp.item_name),
                       COALESCE(to_jsonb(ap)->>'brand',''),
                       COALESCE(to_jsonb(sp)->>'rakuten_genre_id','')
                FROM store_products sp JOIN stores s ON s.id=sp.store_id
                LEFT JOIN amazon_products ap ON ap.asin=sp.asin
                WHERE s.store_code=%s AND COALESCE(sp.enabled,TRUE)
                  AND NOT COALESCE(sp.force_stop,FALSE)
                  AND COALESCE(sp.current_status,'') NOT IN ('deleted','delete_pending')
                  AND COALESCE(sp.mall_item_code,'')<>''
                ORDER BY sp.asin, sp.mall_item_code
            ''', (store,))
            rows = [dict(zip(('title','brand','genre'), row)) for row in cur.fetchall()]
    return select_seeds(rows, limit)


def db_own_shops():
    """Exclude shops represented by our store product URLs, across own stores."""
    from scripts.db_config import connect_db
    with connect_db(options='-c default_transaction_read_only=on', connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT split_part(rakuten_item_url, '/', 4)
                           FROM store_products
                           WHERE rakuten_item_url ~ '^https?://item[.]rakuten[.]co[.]jp/[^/]+/'""")
            return sorted({row[0] for row in cur.fetchall() if row[0]})


def sid_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    data = soup.select_one('script#item-page-app-data[type="application/json"]')
    if data:
        try:
            sid = str(json.loads(data.get_text())['api']['data']['itemInfoSku']['shopId'])
            if sid.isdecimal():
                return sid
        except (ValueError, KeyError, TypeError):
            pass
    for a in soup.select('a[href]'):
        href = a['href']
        parsed = urlsplit(href)
        if parsed.hostname not in {'review.rakuten.co.jp', 'search.rakuten.co.jp'}:
            continue
        match = re.search(r'(?:[?&]sid=|/shop/4/|/item/1/)(\d+)', href)
        if match:
            return match[1]
    return ''


def store_metadata(home_html, search_html, review_html):
    home = BeautifulSoup(home_html, 'html.parser')
    meta = home.select_one('meta[property="og:title"]') or home.find('title')
    name = normalize_space(meta.get('content', '') or meta.get_text()) if meta else ''
    # The meta description is Rakuten boilerplate, not the merchant introduction.
    description = ''
    search = BeautifulSoup(search_html, 'html.parser')
    header = search.select_one('.description.shop')
    header_rating = ''
    review_count = ''
    if header:
        title = header.select_one('h2.title a')
        if title:
            name = normalize_space(title.get_text(' ', strip=True))
        rating_node = header.select_one('a[href*="review.rakuten.co.jp/shop/"] .score')
        if rating_node:
            header_rating = normalize_space(rating_node.get_text())
        review_link = header.select_one('a[href*="review.rakuten.co.jp/shop/"]')
        if review_link:
            match = re.search(r'([0-9][0-9,]*)\s*件', review_link.get_text(' ', strip=True))
            if match:
                review_count = match[1].replace(',', '')
        intro = header.parent.select_one('.description.text')
        if intro:
            description = normalize_space(intro.get_text(' ', strip=True))
    search_text = search.get_text(' ', strip=True)
    count = re.search(r'検索結果\s*[\d,]+\s*[〜～~\-]\s*[\d,]+\s*件\s*[（(]\s*([\d,]+)\s*件', search_text)
    if not count:
        count = re.search(r'(?:全\s*|検索結果\s*[:：]?\s*)([\d,]+)\s*件', search_text)
    rating = ''
    # Only store entities on the dedicated shop review page; never item ratings.
    review = BeautifulSoup(review_html, 'html.parser')
    def walk(value):
        nonlocal rating
        if isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            kinds = value.get('@type', [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if set(kinds) & {'Store', 'Organization', 'LocalBusiness'}:
                raw = value.get('aggregateRating', {}).get('ratingValue', '')
                try:
                    if 0 <= float(raw) <= 5:
                        rating = str(raw)
                except (TypeError, ValueError):
                    pass
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)
    for script in review.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(script.get_text()))
        except (ValueError, TypeError, AttributeError):
            continue
    if re.fullmatch(r'[0-4](?:\.\d+)?|5(?:\.0+)?', header_rating):
        rating = header_rating
    return {'店舗名': name, '評価': rating, '評価数': review_count,
            '出品数': count[1].replace(',', '') if count else '', '店舗紹介文': description}


def has_access_challenge(html):
    # Keep CAPTCHA/robot checks conservative. Only exempt the known conditional
    # shipping notice, not the whole shop or any other congestion message.
    if re.search(r'captcha|ロボットではない', html, re.I):
        return True
    text = BeautifulSoup(html, 'html.parser').get_text('', strip=True)
    text = re.sub(r'\s+', '', text)
    text = text.replace(
        '特定の商品へのアクセスが集中した場合、システムの都合上、受注時間に誤差が生じる可能性がございます。',
        '',
    )
    return 'アクセスが集中' in text


class Fetcher:
    def __init__(self, interval):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'StoreResearch/1.0 (read-only)'
        self.interval = interval
        self.last = 0

    def get(self, url):
        time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        attempt = 0
        unavailable = 0
        while True:
            self.last = time.monotonic()
            r = self.session.get(url, timeout=30)
            if r.status_code in {403, 429}:
                raise RuntimeError('Access limited; stopping (HTTP %s)' % r.status_code)
            html = decode_response(r)
            if has_access_challenge(html):
                r.close()
                raise RuntimeError('Access challenge; stopping without bypass')
            if r.status_code == 503:
                delay = max(self.interval, min(1800, 300 * 2 ** min(unavailable, 3)))
                retry_after = r.headers.get('Retry-After', '').strip()
                try:
                    requested = float(retry_after) if retry_after.isdecimal() else parsedate_to_datetime(retry_after).timestamp() - time.time()
                    delay = max(delay, requested)
                except (ValueError, TypeError, OverflowError):
                    pass
                unavailable += 1
                r.close()
                print(f'HTTP 503: automatic retry #{unavailable} in {delay:.0f}s; same request, checkpoint retained.', flush=True)
                remaining = delay
                while remaining > 0:
                    pause = min(60, remaining)
                    time.sleep(pause)
                    remaining -= pause
                continue
            if r.status_code not in {500, 502, 504} or attempt == 2:
                break
            r.close()
            time.sleep(max(self.interval, 5 * (attempt + 1)))
            attempt += 1
        r.raise_for_status()
        r.close()
        return html


def save(folder, state):
    temporary = folder / 'state.tmp'
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(folder / 'state.json')
    temporary = folder / 'stores.tmp'
    with temporary.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter='\t')
        writer.writeheader()
        for row in state['results']:
            writer.writerow({k: str(row.get(k, '')).replace('\t',' ').replace('\r',' ').replace('\n',' ')
                             for k in FIELDS})
    temporary.replace(folder / 'stores.tsv')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', default='rakuten_1')
    parser.add_argument('--keywords', type=Path, help='Optional UTF-8 search terms, one per line; no DB needed')
    parser.add_argument('--exclude-shop', action='append', default=[], help='Shop slug to exclude; repeatable')
    parser.add_argument('--seed-limit', type=int, default=100)
    parser.add_argument('--pages', type=int, default=1)
    parser.add_argument('--max-stores', type=int, default=300)
    parser.add_argument('--target-candidates', type=int, default=0, help='Stop after this many matching shops; 0 disables')
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--startup-delay', type=int, default=0, help='Wait before requests when restarting during cooldown')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Allow public web reads; otherwise only prepare seeds')
    parser.add_argument('--retry-errors', action='store_true', help='Retry previously unsupported stores')
    parser.add_argument('--snowball', action='store_true', help='Expand searches from matching shops')
    parser.add_argument('--products-per-shop', type=int, default=8)
    args = parser.parse_args()
    if not (1 <= args.seed_limit <= 1000 and 1 <= args.pages <= 10 and
            1 <= args.max_stores <= 10000 and 1 <= args.interval <= 60 and
            0 <= args.target_candidates <= 10000 and 1 <= args.products_per_shop <= 10 and
            0 <= args.startup_delay <= 86400):
        parser.error('Invalid bounds: seeds 1..1000, pages 1..10, stores 1..10000, interval 1..60')
    folder = args.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    config = {'store': args.store, 'pages': args.pages, 'seed_limit': args.seed_limit,
              'keywords': str(args.keywords.resolve()) if args.keywords else ''}
    if (folder / 'state.json').exists():
        state = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
        if state['config'] != config:
            parser.error('Settings differ from checkpoint; use a new output directory')
    else:
        seeds = (list(dict.fromkeys(line.strip() for line in args.keywords.read_text(encoding='utf-8-sig').splitlines()
                                   if line.strip()))[:args.seed_limit] if args.keywords else db_seeds(args.store, args.seed_limit))
        if not seeds:
            parser.error('No seed titles found')
        state = {'config': config, 'seeds': seeds, 'search_done': [], 'queue': {}, 'done': {}, 'results': []}
    if 'own_shops' not in state:
        state['own_shops'] = db_own_shops() if not args.keywords else []
    excluded = set(state['own_shops']) | set(args.exclude_shop) | set(state.get('excluded_shops', []))
    state['excluded_shops'] = sorted(excluded)
    # Correct old checkpoints too: do not retain own shops among candidates.
    excluded_sids = {v['sid'] for slug,v in state['done'].items() if slug in excluded and v.get('sid')}
    state['results'] = [row for row in state['results'] if row['店舗ID'] not in excluded_sids]
    state.setdefault('errors', {})
    state.setdefault('snow_queries', [])
    state.setdefault('expanded_shops', [])
    state.setdefault('seed_product_urls', [])
    state.setdefault('snow_streak', 0)
    state.setdefault('source_stats', {})
    if args.retry_errors:
        state['errors'] = {}
    save(folder, state)
    print('Seeds:', len(state['seeds']), 'Output:', folder, flush=True)
    if not args.execute:
        print('Prepared only. Add --execute to start public web requests.')
        return
    fetch = Fetcher(args.interval)
    try:
        if args.startup_delay:
            print(f'Startup cooldown: {args.startup_delay}s before requests.', flush=True)
            remaining = args.startup_delay
            while remaining > 0:
                time.sleep(min(60, remaining))
                remaining -= min(60, remaining)
        if args.target_candidates and len(state['results']) >= args.target_candidates:
            print('Candidate target reached.', flush=True)
            return
        # Bootstrap existing candidates only once; new candidates reuse their fetched search page.
        if args.snowball:
            for slug, item in state['done'].items():
                if slug in excluded or not item.get('eligible') or slug in state['expanded_shops']:
                    continue
                search = fetch.get(f'https://search.rakuten.co.jp/search/mall/?sid={item["sid"]}')
                products = parse_store_products(search)
                if not products:
                    raise RuntimeError(f'Expansion page format unknown: {slug}')
                expand_shop(state, slug, products, args.products_per_shop)
                save(folder, state)
        while True:
            if args.target_candidates and len(state['results']) >= args.target_candidates:
                print('Candidate target reached.', flush=True)
                return
            pending = [(slug, entry) for slug, entry in state['queue'].items()
                       if slug not in excluded and slug not in state['done'] and slug not in state['errors']]
            if not pending:
                query = next_query(state, args.pages, args.snowball)
                if query is None:
                    break
                key, page, entry = query
                term = entry['term']
                print(f'Search {key} [{entry["source"]}]: {term}', flush=True)
                html = fetch.get(f'https://search.rakuten.co.jp/search/mall/{quote(term, safe="")}/?p={page}')
                products = parse_store_products(html)
                if not products and not re.search(r'該当する商品が|見つかりません|検索結果.*?0件', html):
                    raise RuntimeError('Search page format unknown; checkpoint kept')
                stats = state['source_stats'].setdefault(entry['source'], {'searches': 0, 'checked': 0, 'candidates': 0})
                stats['searches'] += 1
                for product in products:
                    slug = urlsplit(product['rakuten_url']).path.split('/')[1]
                    state['queue'].setdefault(slug, {'product': product['rakuten_url'], **entry})
                state['search_done'].append(key)
                save(folder, state)
                continue
            slug, entry = pending[0]
            if len(state['done']) >= args.max_stores:
                print('Store limit reached. Increase --max-stores to continue.', flush=True)
                return
            try:
                result = inspect_shop(fetch, slug, entry)
            except requests.HTTPError as exc:
                if exc.response is None or exc.response.status_code not in {404, 410}:
                    raise
                result = {'error': f'HTTP {exc.response.status_code}; not classified'}
            if 'error' in result:
                state['errors'][slug] = {**entry, 'error': result['error']}
                print(f'Unresolved (not negative): {slug}: {result["error"]}', flush=True)
                save(folder, state)
                continue
            sid = result['sid']
            if any(item.get('sid') == sid for item in state['done'].values()):
                state['done'][slug] = {'sid': sid, 'duplicate': True}
                save(folder, state)
                continue
            stats = state['source_stats'].setdefault(entry.get('source', 'own'), {'searches': 0, 'checked': 0, 'candidates': 0})
            stats['checked'] += 1
            if result['eligible']:
                stats['candidates'] += 1
                state['results'].append(result['row'])
                if args.snowball:
                    expand_shop(state, slug, result['products'], args.products_per_shop)
            state['done'][slug] = {k: result[k] for k in ('sid', 'eligible', 'first_product')}
            save(folder, state)
            print(f'Stores {len(state["done"])} / candidates {len(state["results"])}: {slug}', flush=True)
        print(f'Search seeds exhausted. Candidates: {len(state["results"])}', flush=True)
    finally:
        save(folder, state)
        fetch.session.close()


if __name__ == '__main__':
    main()
