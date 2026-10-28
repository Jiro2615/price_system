"""Conservative shop-count evidence, not a claim about legal shop ownership."""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

POLICY_VERSION = 'brand_prefix_and_shop_name_v1'
GENERIC_NAMES = {
    '公式', '公式ショップ', '公式ストア', '楽天', '楽天市場', 'ショップ', 'ストア', '通販',
    'オンライン', 'オンラインショップ', 'オンラインストア', '販売', '健康食品', '化粧品',
    'コスメ', 'ビューティー', '日用品', '雑貨', 'ノーブランド', 'ノーブランド品',
    'generic', 'unknown', 'nobrand', 'brand', 'store', 'shop', 'official', 'amazon', 'アマゾン',
}
SUFFIXES = sorted((
    '楽天市場公式ショップ', '楽天市場公式店', '楽天市場ショップ', '楽天市場支店', '楽天市場店',
    '楽天市場', '楽天ショップ', '楽天店', '公式オンラインショップ', '公式オンラインストア',
    '公式ショップ', '公式ストア', '公式通販', 'オンラインショップ', 'オンラインストア',
    'オフィシャルショップ', '本店', '支店',
), key=len, reverse=True)


def shop_identity(item: dict[str, Any]) -> str:
    # Retain the pre-existing raw identity for variants and price comparisons.
    for key in ('shopCode', 'shopUrl', 'shopName'):
        value = re.sub(r'\s+', '', str(item.get(key) or '')).casefold()
        if value:
            return f'{key}:{value}'
    return ''


def _compact(value: str) -> str:
    return re.sub(r'[\W_]+', '', value, flags=re.UNICODE)


def _base_name(value: object) -> str:
    text = unicodedata.normalize('NFKC', html.unescape(str(value or ''))).casefold().strip()
    # Strip only leading official/legal-company labels, not arbitrary words
    # embedded in a retailer name or in its product descriptions.
    for _ in range(4):
        old = text
        text = re.sub(r'^[\s【\[（(]*(?:株式会社|有限会社|合同会社|\(株\)|\(有\))\s*', '', text)
        text = re.sub(r'^[\s【\[（(]*(?:公式|official(?![a-z]))[\s】\]）)]*', '', text)
        text = re.sub(r'\s*(?:株式会社|有限会社|合同会社)$', '', text).strip()
        if text == old:
            break
    return text


def _distinctive(key: str) -> bool:
    if key in GENERIC_NAMES or not key or key.isdecimal():
        return False
    return len(key) >= (3 if re.search(r'[ぁ-んァ-ヶ一-龥]', key) else 4)


def _name_key(name: str) -> str:
    key = _compact(name)
    for _ in range(4):
        suffix = next((suffix for suffix in SUFFIXES if key.endswith(suffix)), None)
        if not suffix:
            break
        candidate = key[:-len(suffix)]
        if not _distinctive(candidate):
            return ''
        key = candidate
    return key if _distinctive(key) else ''


def _prefix_alias(name: str, aliases: list[str]) -> str:
    compact = _compact(name)
    for alias in sorted(aliases, key=len, reverse=True):
        key = _compact(_base_name(alias))
        if not _distinctive(key) or not compact.startswith(key):
            continue
        if re.fullmatch(r'[a-z0-9]+', key):
            # ACME Tokyo is a candidate; ACMEplus is another word. Do not use
            # edit-distance/common-prefix guessing on arbitrary store names.
            pattern = r'^' + r'[\W_]*'.join(re.escape(c) for c in key) + r'(?![a-z0-9])'
            if not re.search(pattern, name):
                continue
        return key
    return ''


def shop_group_evidence(exact_items: list[dict[str, Any]], text_items: list[dict[str, Any]],
                        *, maker_aliases: list[str] | None = None) -> dict[str, Any]:
    """Collapse raw IDs by normalized name or a distinctive maker-name prefix.

    All exact/text results are grouped together so a JAN group cannot also be
    counted as a text-only shop. Product matching and price selection are not
    changed. Empty/generic names alone never join separate shop codes.
    """
    stores: dict[str, dict[str, Any]] = {}
    for exact, items in ((True, exact_items), (False, text_items)):
        for item in items:
            identity = shop_identity(item)
            if not identity:
                continue
            store = stores.setdefault(identity, {'identity': identity, 'names': [], 'codes': [], 'tags': set(), 'exact': False})
            store['exact'] |= exact
            name, code = str(item.get('shopName') or '').strip(), str(item.get('shopCode') or '').strip()
            for field, value in (('names', name), ('codes', code)):
                if value and value not in store[field]:
                    store[field].append(value)
            base = _base_name(name)
            name_key = _name_key(base)
            alias = _prefix_alias(base, maker_aliases or [])
            if name_key:
                store['tags'].add('name:' + name_key)
            if alias:
                store['tags'].add('maker_prefix:' + alias)
    parents = {identity: identity for identity in stores}

    def find(identity):
        while parents[identity] != identity:
            parents[identity] = parents[parents[identity]]
            identity = parents[identity]
        return identity

    first_tag: dict[str, str] = {}
    for identity, store in stores.items():
        for tag in sorted(store['tags']):
            if tag in first_tag:
                parents[find(identity)] = find(first_tag[tag])
            else:
                first_tag[tag] = identity
    groups: dict[str, list[dict]] = {}
    for identity, store in stores.items():
        groups.setdefault(find(identity), []).append(store)
    rows = []
    for members in groups.values():
        names = list(dict.fromkeys(name for member in members for name in member['names']))
        codes = list(dict.fromkeys(code for member in members for code in member['codes']))
        tags = [tag for member in members for tag in member['tags']]
        reasons = sorted(tag for tag in set(tags) if tags.count(tag) > 1)
        rows.append({'representative': (names or codes or [members[0]['identity']])[0],
                     'shop_names': names, 'shop_codes': codes, 'raw_shop_count': len(members),
                     'grouping_reasons': reasons, 'jan_exact': any(member['exact'] for member in members)})
    exact_count = sum(row['jan_exact'] for row in rows)
    return {'shop_grouping_policy': POLICY_VERSION, 'raw_shop_count': len(stores),
            'merged_shop_count': len(stores) - len(rows), 'confirmed_shop_count': len(rows),
            'jan_exact_shop_count': exact_count, 'text_match_shop_count': len(rows) - exact_count,
            'shop_names': [row['representative'] for row in rows],
            # Persist detailed membership only where a merge actually occurred.
            # Independent one-store rows need no duplicate per-product audit.
            'shop_groups': [row for row in rows if row['raw_shop_count'] > 1]}
