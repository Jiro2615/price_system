"""Read-only, isolated Headless Shell probe; never runs the worker or DB save."""
import argparse
import asyncio
import hashlib
import importlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def git_info(root):
    def run(*args):
        result = subprocess.run(
            ['git', '-C', str(root), *args], capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=15,
        )
        return result.stdout.strip() if result.returncode == 0 else 'unavailable'
    return {'commit': run('rev-parse', 'HEAD'), 'status': run('status', '--short')}


def forbid_db(*args, **kwargs):
    raise RuntimeError('Diagnostic: database access is forbidden')


async def probe(checker, asin, out, report):
    events = report['events']
    original_read = checker.read_buybox_info
    original_parse = checker.parse_shipping_status
    original_save = checker.save_to_db
    original_connect = checker.connect_db

    async def capture(page, name):
        # Artifact failures must not change the checker result.
        for suffix, action in (
            ('png', lambda: page.screenshot(path=str(out / (name + '.png')), full_page=False)),
            ('html', page.content),
        ):
            try:
                value = await action()
                if suffix == 'html':
                    (out / (name + '.html')).write_text(value, encoding='utf-8')
            except Exception as exc:
                report.setdefault('capture_errors', []).append(f'{name}.{suffix}: {exc}')

    async def read(page):
        value = await original_read(page)
        events.append({'stage': 'buybox', 'data': value})
        await capture(page, 'buybox')
        return value

    def parse(text):
        value = original_parse(text)
        events.append({'stage': 'shipping_parse', 'input': text, 'result': value})
        return value

    checker.read_buybox_info = read
    checker.parse_shipping_status = parse
    checker.save_to_db = forbid_db
    checker.connect_db = forbid_db
    resources = None
    try:
        resources = await checker.create_amazon_page(browser_mode='shell')
        page = resources[-1]
        report['result'] = await checker.check_amazon_one(asin, page=page)
        report['destination'] = await checker.get_first_text(page, '#glow-ingress-block')
        report['page_url'] = page.url
        await capture(page, 'final')
    finally:
        checker.read_buybox_info = original_read
        checker.parse_shipping_status = original_parse
        checker.save_to_db = original_save
        checker.connect_db = original_connect
        if resources is not None:
            await checker.close_amazon_page(*resources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asin', default='B01BLBQZ9Q')
    parser.add_argument('--root', type=Path, default=Path('C:/rakuten'))
    args = parser.parse_args()
    asin = args.asin.strip().upper()
    if not re.fullmatch('[A-Z0-9]{10}', asin):
        parser.error('ASIN must be 10 letters/digits')
    repo = args.root / 'price_system_listing'
    source = repo / 'scripts' / 'price_check_one_asin_db.py'
    if not source.is_file():
        parser.error(f'Checker not found: {source}')
    out = args.root / 'output' / 'delivery_diagnostics' / (
        datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + asin
    )
    out.mkdir(parents=True)
    report = {
        'started_at': datetime.now().isoformat(), 'hostname': platform.node(),
        'asin': asin, 'browser_mode': 'shell', 'isolated_context': True,
        'database_access': 'forbidden', 'python': sys.version,
        'checker_path': str(source),
        'checker_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'repositories': {name: git_info(args.root / name)
                         for name in ('price_system', 'price_system_listing')},
        'events': [],
    }
    code = 0
    try:
        sys.path.insert(0, str(repo))
        sys.path.insert(0, str(repo / 'scripts'))
        checker = importlib.import_module('price_check_one_asin_db')
        asyncio.run(probe(checker, asin, out, report))
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        code = 1
    finally:
        report['finished_at'] = datetime.now().isoformat()
        (out / 'result.json').write_text(
            json.dumps(report, ensure_ascii=False, default=str, indent=2), encoding='utf-8',
        )
        print('Diagnostic saved:', out)
        print('Result:', report.get('result', report.get('error')))
        if os.name == 'nt':
            try:
                os.startfile(str(out))
            except OSError:
                pass
    return code


if __name__ == '__main__':
    raise SystemExit(main())
