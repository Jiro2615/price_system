"""Fail-closed product identity policy, independent of navigation and storage.

Keep this file identical to Rakuten/python/amazon_product_identity.py so the
standalone order tool and the shared listing/price checker enforce one policy.
"""
import re
from urllib.parse import urlsplit


PRODUCT_IDENTITY_JS = r"""() => {
    const selected = document.querySelector('#ASIN')?.value || '';
    const canonical = document.querySelector('link[rel="canonical"]')?.getAttribute('href') || '';
    const purchases = [...document.querySelectorAll(
        '#addToCart input[name="ASIN"], #addToCart input[name="ASIN.0"], #buyNow input[name="ASIN"]'
    )].map(node => node.value || '');
    // Only the primary variation module can establish a parent relationship.
    // Never use recommendations, gallery metadata or a page-wide ASIN match.
    const parents = new Set(), children = new Set();
    let variationModules = 0;
    for (const node of document.querySelectorAll('#twister_feature_div script')) {
        const text = (node.textContent || '').trim();
        if (!/^P\.register\(\s*['"]twister-js-init-dpx-data['"]\s*,/.test(text)) continue;
        variationModules++;
        for (const match of text.matchAll(/["'](parentAsin|currentAsin)["']\s*:\s*["']([A-Z0-9]{10})["']/g)) {
            (match[1] === 'parentAsin' ? parents : children).add(match[2]);
        }
    }
    const relationship = variationModules === 1 && parents.size === 1 && children.size === 1
        ? {source: 'twister-js-init-dpx-data', parent_asin: [...parents][0], current_asin: [...children][0]}
        : null;
    const details = [];
    for (const row of document.querySelectorAll(
        '#productDetails_detailBullets_sections1 tr, #productDetails_techSpec_section_1 tr, #detailBullets_feature_div li')) {
        const text = (row.textContent || '').replace(/[\u200e\u200f]/g, '').trim();
        const match = text.match(/^ASIN\s*[:：]?\s*([A-Z0-9]{10})\b/i);
        if (match) details.push(match[1].toUpperCase());
    }
    return {selected_asin: selected, canonical_url: canonical, detail_asins: [...new Set(details)],
        purchase_asins: purchases, parent_relationship: relationship};
}"""


def normalized_asin(value):
    text = str(value or '').strip().upper()
    return text if re.fullmatch(r'[A-Z0-9]{10}', text) else ''


def url_asin(value):
    try:
        parsed = urlsplit(str(value or ''))
        if parsed.scheme != 'https' or parsed.hostname not in {'www.amazon.co.jp', 'amazon.co.jp'}:
            return ''
        match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/ ?]|$)', parsed.path, re.I)
        return match[1].upper() if match else ''
    except ValueError:
        return ''


def identity_error(expected, page_url, observation):
    """Reject conflicts except a proven parent in details of the selected child."""
    expected = normalized_asin(expected)
    if not expected:
        return 'ASIN未確認 指定ASINが不正です'
    observation = observation if isinstance(observation, dict) else {}
    evidence = {'URL': url_asin(page_url)}
    selected = normalized_asin(observation.get('selected_asin'))
    canonical = url_asin(observation.get('canonical_url'))
    details = observation.get('detail_asins')
    purchases = observation.get('purchase_asins')
    relationship = observation.get('parent_relationship')
    # Require independent agreement from URL, canonical, selection, purchase
    # form and primary variation data. This exception applies ONLY to details.
    detail_parent = ''
    if (evidence['URL'] == selected == canonical == expected
            and isinstance(purchases, list) and purchases
            and all(normalized_asin(value) == expected for value in purchases)
            and isinstance(relationship, dict)
            and relationship.get('source') == 'twister-js-init-dpx-data'
            and normalized_asin(relationship.get('current_asin')) == expected):
        detail_parent = normalized_asin(relationship.get('parent_asin'))
    if selected:
        evidence['選択商品'] = selected
    if canonical:
        evidence['正規URL'] = canonical
    if isinstance(purchases, list):
        for index, value in enumerate(purchases):
            if normalized_asin(value):
                evidence[f'購入対象{index+1}'] = normalized_asin(value)
    if isinstance(details, list):
        for index, value in enumerate(details[:5]):
            detail = normalized_asin(value)
            if detail and detail != detail_parent:
                evidence[f'商品詳細{index+1}'] = detail
    conflicts = [f'{source}={value}' for source, value in evidence.items() if value and value != expected]
    if conflicts:
        return f'ASIN不一致 指定={expected} / ' + ' / '.join(conflicts)
    page_identity = selected or canonical or (
        isinstance(details, list) and any(normalized_asin(value) for value in details[:5]))
    if not evidence['URL'] or not page_identity:
        return f'ASIN未確認 指定={expected}（ページ内の商品番号を確認できません）'
    return ''


def block_identity_result(result, reason):
    result.update(business_ng=True, system_error=False, ng_reason=reason,
                  amazon_price=None, available_qty=0, gift_available=False, shipping_status='NG')
