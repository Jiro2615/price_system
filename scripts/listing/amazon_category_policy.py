"""Shared Amazon category exclusions; read-only at all listing gates."""
from __future__ import annotations

from scripts.db_config import connect_db


def category_id(value):
    text = str(value).strip()
    if not text.isascii() or not text.isdigit() or len(text) > 19 or not 0 < int(text) <= 9223372036854775807:
        raise ValueError('AmazonカテゴリIDは正の整数で指定してください')
    return int(text)


def load_category_exclusions():
    """No rules before first setup; DB failures must never bypass saved rules."""
    try:
        with connect_db(options='-c default_transaction_read_only=on') as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.amazon_category_exclusions')")
            if not cur.fetchone()[0]:
                return {}
            cur.execute('SELECT category_id, category_name FROM public.amazon_category_exclusions WHERE enabled = TRUE ORDER BY category_id')
            return {category_id(row[0]): str(row[1] or '') for row in cur.fetchall()}
    except Exception as exc:
        raise RuntimeError('Amazonカテゴリ除外設定を取得できないため、出品を停止しました') from exc


def category_exclusion_result(product, rules):
    """Match any ancestor ID. Unknown ancestry is held when rules are active."""
    if not rules:
        return None
    def value(name, default=None):
        return product.get(name, default) if isinstance(product, dict) else getattr(product, name, default)
    tree = value('category_tree', [])
    nodes = tree if isinstance(tree, list) else []
    ids = set()
    malformed = not nodes
    for node in nodes:
        try:
            ids.add(category_id(node.get('catId')))
        except (ValueError, AttributeError):
            malformed = True
    try:
        ids.add(category_id(value('category_id')))
    except ValueError:
        pass
    matched = sorted(ids.intersection(rules))
    if matched:
        labels = [f"{rules[key] or 'カテゴリ'}（{key}）" for key in matched]
        return {'listing_status': 'business_ng',
                'listing_reason': 'Amazonカテゴリ除外（配下を含む）: ' + '、'.join(labels),
                'matched_category_ids': matched}
    if malformed:
        return {'listing_status': 'missing_required_data',
                'listing_reason': 'Amazonカテゴリ階層が未取得のため、除外カテゴリへの該当を確認できません',
                'matched_category_ids': []}
    return None


def check_current_categories(dry_run_result):
    return category_exclusion_result(dry_run_result.get('keepa_result'), load_category_exclusions())
