"""Non-bypassable new-listing check for electronically delivered games.

Use only the selected ASIN (never sibling formats, recommendations or the
converted marketplace description). A pass here is not approval to list.
"""
import re
import unicodedata


def _text(value):
    return " ".join(unicodedata.normalize("NFKC", "" if value is None else str(value)).casefold().split())


def _get(product, name):
    return product.get(name) if isinstance(product, dict) else getattr(product, name, None)


_GAME = re.compile(r"ゲームソフト|ゲーム本[編体]|pcゲーム|ゲームキー|ビデオゲーム|(?:video|pc|digital|online) game(?:s|\b)|(?<![a-z])(?:steam|(?:nintendo )?switch(?: 2)?|playstation|xbox|ps[345])(?![a-z])|ニンテンドースイッチ")
_DIGITAL_GROUPS = {"digital video games", "digital video game", "digital games", "digital videogames"}
_DOWNLOAD_BINDINGS = {"software download", "download", "digital download", "online game code", "video game download",
                      "オンラインコード版", "ダウンロード版"}
_ELECTRONIC = re.compile(r"オンライン\s*コード|デジタル\s*(?:コード|版)|ダウンロード\s*(?:番号|コード|版|専用)|dl版|メール納品|電子納品|コードのみ|steamキー|"
                         r"(?:メール|オンライン|電子)(?:にて|で|により)(?:お届け|納品|配信|送信)|"
                         r"(?:digital|online|download|steam|activation)\s+(?:game\s+)?(?:code|key)|digital download|digital edition")
_DIGITAL_NODE = re.compile(r"ダウンロード版ソフト|ゲームダウンロード|ダウンロードゲーム|オンラインゲームコード|downloadable games|game downloads")
_PHYSICAL = re.compile(r"パッケージ版|ゲームキーカード|ダウンロードカード|ゲームカード版|カード版|カートリッジ版|ディスク版|"
                       r"(?:カード|現物|パッケージ)(?:自体)?(?:を|で|にて)(?:郵送|発送|配送|お届け)|"
                       r"コードインボックス|code.in.(?:a.)?box|physical (?:card|copy|edition)|game.key.card")
_NO_PHYSICAL = re.compile(r"(?:パッケージ版?|現物|カード版?|ディスク|ソフト|商品)(?:の?(?:発送|配送|郵送))?(?:は|が)?(?:なく|ない|無し|なし|ありません|ございません|されません|しません|ではない|ではありません)|no physical|not (?:a )?physical")
_PHYSICAL_BINDINGS = {"blu-ray", "blu-ray disc", "dvd", "dvd-rom", "cd-rom", "cartridge", "game cartridge", "ディスク", "カード", "ゲームカード"}
_NON_GAME = re.compile(r"プリペイド|ギフトカード|利用券|会員券|月額会員|シーズンパス|追加コンテンツ|追加ダウンロードコンテンツ|"
                       r"\bdlc\b|gift card|season pass|周辺機器|アクセサリ|保護フィルム|冷却ファン|収納ケース|攻略本|"
                       r"ゲーム機本体|コントローラー|ゲームコンソール|(?:ps[345]|switch|playstation\s*\d)\s*本体|"
                       r"xbox game pass|playstation plus|nintendo switch online.{0,15}(?:か月|ヶ月|利用券|個人プラン)")
_NON_GAME_BRANCHES = {"周辺機器", "アクセサリ", "アクセサリー", "本体", "ゲーム機本体", "ゲーム周辺機器",
                      "コントローラー", "追加コンテンツ", "プリペイドカード", "accessories", "consoles", "controllers"}
_BUNDLE = re.compile(r"(?:ゲーム)?本編\s*(?:を含む|入り|[+&と])|[+&]\s*(?:ゲーム本編|dlc|追加コンテンツ)|"
                     r"(?:dlc|追加コンテンツ|攻略本|アクセサリー?|ギフトカード|コントローラー)(?:同梱|付[き属]?)")
_BONUS = re.compile(r"(?:初回|予約|購入|封入|店舗|限定|早期購入)?特典\s*[】):]?\s*(?:として)?[^|【】()[\]。]{0,32}?(?:(?:オンライン|デジタル)?コード|ダウンロード(?:コード|番号))(?!版)(?:を?封入|付き|付属)?|"
                    r"(?:オンライン|ダウンロード|デジタル)コード(?:の)?(?:特典|を特典として)")
_COMPARISON = re.compile(r"(?:パッケージ版|カード版|ディスク版|ダウンロード版|オンラインコード版)(?:と(?:同じ|同内容|の違い)|とは異なり)")
_DELIVERY = re.compile(r"(?:メール|オンライン|電子)(?:で|にて|により)?(?:お届け|送信|通知|納品|提供|配信)|(?:sent|delivered) (?:by|via) e-?mail")
_CODE = re.compile(r"コード|番号|シリアルキー|ゲームキー|activation key|game code")
_POSTED = re.compile(r"(?:カード|現物|パッケージ|ディスク|カートリッジ)(?:自体)?(?:を|で|にて)(?:郵送|発送|配送|お届け)|物理カード|physical (?:card|copy) (?:is )?(?:sent|shipped)")


def game_delivery_block(product, amazon_title="", fallback_title=""):
    """Return business NG or an evidence hold; independent of word/JAN rules."""
    def field(key):
        return _text(_get(product, key)).replace("_", " ")

    nodes = [n for n in (_get(product, "category_tree") or []) if isinstance(n, dict)]
    ids = {str(n.get("catId")) for n in nodes} | {str(_get(product, key)) for key in ("category_id", "root_category")}
    categories = [_text(n.get("name")) for n in nodes]
    group, binding, keyword = (field(k) for k in ("product_group", "binding", "item_type_keyword"))
    keyword = keyword.replace("-", " ")
    def edition_text(t):
        return _COMPARISON.sub("", _BONUS.sub("", _text(t)))

    titles = [edition_text(t) for t in (_get(product, "title"), amazon_title) if t]
    if not titles:
        titles = [edition_text(fallback_title)]
    title = " | ".join(titles)
    edition_fields = [*titles, edition_text(field("style")), edition_text(field("edition"))]
    evidence = " | ".join(edition_fields)
    digital_node = "206233867051" in ids or any(_DIGITAL_NODE.search(n) for n in categories)
    group_game = group in _DIGITAL_GROUPS or bool(_GAME.search(group + " " + binding))
    game_context = (digital_node or "637394" in ids or group_game or _GAME.search(keyword + " " + evidence)
                    or any(n == "ゲーム" or _GAME.search(n) for n in categories))
    if not game_context:
        return None

    # Exclude products *about* games, accessories, prepaid balance and extras.
    subject = re.sub(r"(?:コントローラー|周辺機器|アクセサリー?)対応", "", title)
    if not _BUNDLE.search(subject) and (_NON_GAME.search(subject) or _NON_GAME_BRANCHES.intersection(categories)):
        return None

    def block(why):
        return {"listing_status": "business_ng", "listing_reason": "ゲーム本体のオンラインコード納品は出品対象外: " + why}

    def hold():
        return {"listing_status": "missing_required_data", "listing_reason": "ゲーム本体の納品形態を確認できないため未出品（現物配送かオンライン納品か要確認）"}

    product_type = field("product_type")
    electronic_format = ("Keepa商品種別：ダウンロード商品" if product_type == "1" else
                         "商品グループ：" + group if group in _DIGITAL_GROUPS else
                         "媒体：" + binding if binding in _DOWNLOAD_BINDINGS else "")
    # Do not use sibling edition labels or bonus codes as delivery evidence.
    features = _get(product, "features") or []
    facts = [_text(v) for v in (features if isinstance(features, list) else [features])] + [field("description")]
    delivery_sentences = [s for fact in facts for s in re.split(r"[。!！\n]|<br\s*/?>", fact)
                          if not re.search(r"特典|bonus|追加コンテンツ", s)]
    sent_code = any(_CODE.search(s) and _DELIVERY.search(s) for s in delivery_sentences)
    no_physical = any(_NO_PHYSICAL.search(s) for s in [evidence, *delivery_sentences])
    # Do not treat “no physical card is sent” as evidence of a shipped card.
    physical = binding in _PHYSICAL_BINDINGS or any(_PHYSICAL.search(t) and not _NO_PHYSICAL.search(t) for t in edition_fields)
    posted = any(_POSTED.search(s) and not _NO_PHYSICAL.search(s) for s in [*delivery_sentences, *edition_fields])
    physical = physical or posted
    if electronic_format:
        return hold() if physical else block(electronic_format)
    if physical:
        # A code printed in a package is not an electronic delivery. Explicitly
        # contradictory delivery evidence must not go through on that basis.
        conflicting_edition = any(_ELECTRONIC.search(t) for t in edition_fields) and not (
            posted or re.search(r"封入|印刷|同梱|code.in.(?:a.)?box", evidence))
        if no_physical or sent_code or _DELIVERY.search(evidence) or conflicting_edition:
            return hold()
        return None
    if _ELECTRONIC.search(evidence):
        return block("選択中の商品の販売形式")
    if sent_code:
        return block("商品の納品説明")
    if digital_node:
        return hold()  # Some download categories also contain physically delivered cards.
    # For otherwise unlabelled game software, use positive shipping evidence,
    # not absence of a price, date or gift option as a digital classification.
    software = ("637394" in ids or binding in {"video game", "video games"} or any(n in {"ゲームソフト", "ソフト", "pcゲーム", "ゲーム本編"} for n in categories)
                or bool(_GAME.search(keyword)) or group_game)
    weight = field("package_weight")
    if software and (no_physical or not (product_type == "0" and weight.isdecimal() and int(weight) > 0)):
        return hold()
    return None


def saved_game_delivery_block(dry_run):
    return game_delivery_block(dry_run.get("keepa_result"), _get(dry_run.get("amazon_result"), "title"),
                               _get(dry_run.get("item_payload"), "title"))
