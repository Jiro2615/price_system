"""Fail-closed product identity policy, independent of navigation and storage.

Keep this file identical to Rakuten/python/amazon_product_identity.py so the
standalone order tool and the shared listing/price checker enforce one policy.
"""
import re
from urllib.parse import urlsplit


PRODUCT_IDENTITY_JS = r"""() => {
    const selected = document.querySelector('#ASIN')?.value || '';
    const canonical = document.querySelector('link[rel="canonical"]')?.getAttribute('href') || '';
    const details = [];
    for (const row of document.querySelectorAll(
        '#productDetails_detailBullets_sections1 tr, #productDetails_techSpec_section_1 tr, #detailBullets_feature_div li')) {
        const text = (row.textContent || '').replace(/[\u200e\u200f]/g, '').trim();
        const match = text.match(/^ASIN\s*[:：]?\s*([A-Z0-9]{10})\b/i);
        if (match) details.push(match[1].toUpperCase());
    }
    return {selected_asin: selected, canonical_url: canonical, detail_asins: [...new Set(details)]};
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
    """Any explicit conflicting identity is unsafe; URL alone is not proof."""
    expected = normalized_asin(expected)
    if not expected:
        return 'ASIN未確認 指定ASINが不正です'
    observation = observation if isinstance(observation, dict) else {}
    evidence = {'URL': url_asin(page_url)}
    selected = normalized_asin(observation.get('selected_asin'))
    canonical = url_asin(observation.get('canonical_url'))
    details = observation.get('detail_asins')
    if selected:
        evidence['選択商品'] = selected
    if canonical:
        evidence['正規URL'] = canonical
    if isinstance(details, list):
        for index, value in enumerate(details[:5]):
            if normalized_asin(value):
                evidence[f'商品詳細{index+1}'] = normalized_asin(value)
    conflicts = [f'{source}={value}' for source, value in evidence.items() if value and value != expected]
    if conflicts:
        return f'ASIN不一致 指定={expected} / ' + ' / '.join(conflicts)
    if not evidence['URL'] or len(evidence) == 1:
        return f'ASIN未確認 指定={expected}（ページ内の商品番号を確認できません）'
    return ''


def block_identity_result(result, reason):
    result.update(business_ng=True, system_error=False, ng_reason=reason,
                  amazon_price=None, available_qty=0, gift_available=False, shipping_status='NG')
