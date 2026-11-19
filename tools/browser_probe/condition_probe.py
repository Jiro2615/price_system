"""Compare response HTML with rendered/regular BuyBox in one anonymous context."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from html_probe import extract, price_number
from probe_support import REPO, atomic_json, no_db, challenge
from asin_plan import CONTROLS


def html_conditions(html, asin):
    result = extract(html, asin)
    soup = BeautifulSoup(html, 'html.parser')
    result['purchase_rows'] = [
        {'name': row.get('data-a-accordion-row-name'),
         'text': row.get_text(' ', strip=True)[:2500],
         'radio_classes': [icon.get('class') for icon in row.select('.a-accordion-radio')]}
        for row in soup.select('[data-a-accordion-row-name]')]
    result['alternative_offers_link_present'] = bool(soup.select_one('#aod-ingress-link, a[href*="/gp/offer-listing/"]'))
    regular = soup.select_one('[data-a-accordion-row-name="newAccordionRow"]')
    result['regular_row_candidate'] = None
    if regular is not None:
        result['regular_row_candidate'] = {
            'price': price_number(regular.get_text(' ', strip=True)),
            'purchase_method': 'one_time', 'scope': 'newAccordionRow',
            'certified_for_production': False,
        }
    box = regular or soup.select_one('#buybox, #desktop_buybox')
    match = re.search(r'お届け先[^\n]{0,100}?\d{3}-\d{4}', box.get_text(' ', strip=True) if box else '')
    result['destination_evidence'] = match[0] if match else None
    return result


async def main(out):
    out.mkdir(exist_ok=False, parents=True)
    result = {'cases': [], 'scope': 'Read-only; anonymous same-context response versus DOM; no login, delivery modification, DB writes or Keepa',
              'all_complete': False, 'production_exclusion_enabled': False}
    path = out / 'conditions.json'
    atomic_json(path, result)
    sys.path.insert(0, str(REPO))
    import scripts.db_config as db
    import psycopg
    db.connect_db = psycopg.connect = no_db
    import scripts.price_check_one_asin_db as checker
    checker.connect_db = checker.save_to_db = no_db
    from playwright.async_api import async_playwright
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(locale='ja-JP', service_workers='block')
                async def guard(route):
                    req = route.request
                    target = urlparse(req.url).path.lower()
                    if req.method not in {'GET', 'HEAD', 'OPTIONS'} or any(
                        marker in target for marker in ('/cart/', 'add-to-cart', 'validatecaptcha', '/checkout', '/buy/', '/ap/', '/hz/wishlist/')
                    ):
                        await route.abort()
                    else:
                        await route.continue_()
                await ctx.route('**/*', guard)
                page = await ctx.new_page()
                page.set_default_timeout(3000)
                async def safety():
                    body = await page.locator('body').inner_text()
                    if challenge(page.url, body) or checker.is_amazon_confirmation_page(page.url, body):
                        raise RuntimeError('Challenge/confirmation: stop without bypass')
                async def visible():
                    await safety()
                    data = {}
                    for name, selector in {
                        'destination': '#glow-ingress-line2', 'seller': '#sellerProfileTriggerId',
                        'ships_from': '#fulfillerInfoFeature_feature_div', 'delivery': '#deliveryBlockMessage',
                    }.items():
                        loc = page.locator(selector).first
                        data[name] = await loc.inner_text() if await loc.count() and await loc.is_visible() else None
                    data['purchase_rows'] = await page.locator('[data-a-accordion-row-name]').evaluate_all(
                        "els=>els.map(e=>({name:e.getAttribute('data-a-accordion-row-name'),text:e.innerText,radio:Array.from(e.querySelectorAll('.a-accordion-radio')).map(r=>r.className)}))")
                    data['buybox'] = await checker.read_buybox_info(page)
                    return data
                for asin in list(dict.fromkeys(CONTROLS + ['B0DV8Q76RX'])):
                    if (out / 'STOP').exists():
                        raise RuntimeError('Operator STOP')
                    case = {'asin': asin, 'utc': datetime.now(timezone.utc).isoformat()}
                    result['cases'].append(case)
                    response = await page.goto(checker.build_amazon_product_url(asin), wait_until='domcontentloaded', timeout=30000)
                    if response is None or not response.ok:
                        raise RuntimeError('Navigation failed')
                    await safety()
                    case['response_html'] = html_conditions(await response.text(), asin)
                    if not case['response_html']['identity_verified']:
                        raise RuntimeError('ASIN identity not established')
                    await page.wait_for_timeout(1200)
                    case['before_regular_selection'] = await visible()
                    case['selection_changed'] = await checker.select_one_time_purchase(page)
                    case['regular'] = await visible()
                    # Offers belong to the very same context/destination; this
                    # inspects available offers but does not buy any of them.
                    await checker.open_all_offers(page)
                    await safety()
                    case['offers'] = []
                    offers = page.locator('#aod-offer-list #aod-offer')
                    for index in range(min(await offers.count(), 20)):
                        offer = offers.nth(index)
                        record = {}
                        for key, selector in {'price': '#aod-offer-price', 'seller': '#aod-offer-soldBy',
                                              'ships_from': '#aod-offer-shipsFrom', 'condition': '#aod-offer-heading'}.items():
                            loc = offer.locator(selector).first
                            record[key] = await loc.inner_text() if await loc.count() else None
                        case['offers'].append(record)
                    case['safe_product_exclusion'] = False
                    case['exclusion_note'] = 'Top offer alone does not prove all offers ineligible; destination/gift not certified'
                    atomic_json(path, result)
                    print(asin, 'regular_price', case['regular']['buybox']['price'], 'offers', len(case['offers']), flush=True)
                    await page.goto('about:blank')
                result['all_complete'] = True
            finally:
                await browser.close()
    except Exception as exc:
        result['error'] = str(exc)
        print('Stopped:', exc, flush=True)
    finally:
        atomic_json(path, result)
        print(path, flush=True)


if __name__ == '__main__':
    asyncio.run(main(Path(sys.argv[1])))
