"""Use ASIN metadata, never title keywords or sibling edition labels."""
import unicodedata


def _normalized(value):
    return unicodedata.normalize('NFKC', str(value or '')).strip().casefold()


def digital_book_reason(product):
    metadata = [product.binding, product.product_group]
    metadata += [node.get('name', '') for node in product.category_tree]
    digital_names = {'kindle', 'kindle版', 'kindle本', 'kindleストア', 'kindle store',
                     'kindle edition', 'kindle_edition', 'ebook', 'ebooks', 'e-book', '電子書籍',
                     'audible', 'audible版', 'audible audiobook', 'audible audiobooks',
                     'audibleオーディオブック', 'audibleオーディオブック版',
                     'audible books & originals', 'audio download', 'audible_audiobook', 'audio_download'}
    for value in metadata:
        normalized = _normalized(value)
        if normalized in digital_names or normalized.startswith(('audible ', 'kindle edition')):
            return f'デジタル書籍は出品対象外: {value}'
    if any(str(node.get('catId') or '') == '2250738051' for node in product.category_tree):
        return 'デジタル書籍は出品対象外: Kindleストア'
    return ''


def book_format_label(product):
    if digital_book_reason(product):
        return ''
    labels = {
        '単行本': '単行本', '単行本(ソフトカバー)': '単行本（ソフトカバー）',
        'paperback': 'ペーパーバック', 'ペーパーバック': 'ペーパーバック',
        'hardcover': 'ハードカバー', 'ハードカバー': 'ハードカバー',
        '文庫': '文庫', '新書': '新書', '大型本': '大型本', 'コミック': 'コミック',
        '雑誌': '雑誌', 'ムック': 'ムック', 'mook': 'ムック',
        'オンデマンド(ペーパーバック)': 'オンデマンド（ペーパーバック）',
        'ボードブック': 'ボードブック', 'board book': 'ボードブック',
        '楽譜': '楽譜', 'sheet music': '楽譜',
        'tankobon_hardcover': '単行本',
        'tankobon_softcover': '単行本（ソフトカバー）',
        'paperback_bunko': '文庫', 'paperback_shinsho': '新書',
        'jp_oversized_book': '大型本', 'comic': 'コミック',
        'magazine': '雑誌', 'sheet_music': '楽譜', 'board_book': 'ボードブック',
        'consumer_magazine': '雑誌', 'map': '地図', 'diary': '手帳',
    }
    return labels.get(_normalized(product.binding), '')


def prepend_book_format(description, product):
    label = book_format_label(product)
    if not label:
        return description
    notice = f'本商品は{label}です。'
    # Idempotent for repeat preparation / historical updates.
    if description.startswith(notice):
        return description
    return notice + '<br />' + description
