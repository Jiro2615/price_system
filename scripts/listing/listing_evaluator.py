from __future__ import annotations

from scripts.listing.attribute_policy import resolve_required_attributes
from scripts.listing.attribute_resolver import build_resolved_fields
from scripts.listing.common_settings import build_seller_count_evaluation, load_listing_common_settings
from scripts.listing.models import AmazonCheckResult, EvaluationResult, KeepaProductData, ListingCommonSettings, MasterData, MatchedRule, ResolvedField, StoreSettings
from scripts.listing.prohibited_word_masking import analyze_prohibited_word_issues, detect_legacy_spacing_reviews
from scripts.listing.provisional_genre import suggest_provisional_genre
from scripts.listing.rakuten_marketplace_policy import (
    MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION,
    has_sensitive_forbidden_word,
    is_cosmetics_category,
    rakuten_marketplace_evidence,
    rakuten_listing_count_for_jan,
)


# These effectiveness/sexual-function expressions remain non-overridable even
# if the same JAN is already listed on Rakuten.  Product-category terms such as
# "医薬部外品" are intentionally not included here.
MANDATORY_COMPLIANCE_FORBIDDEN_WORDS = (
    "治癒", "治す", "予防", "防ぐ", "改善", "効能", "効果", "疲労回復", "老化防止",
    "血液サラサラ", "バストアップ", "デトックス", "脂肪燃焼", "代謝促進", "精力剤", "性的機能",
)

# These are not generally permitted words.  They can only be used when the
# same JAN has been confirmed as a Japanese quasi-drug and the mandatory
# disclosure block is appended below.
QUASI_DRUG_CONDITIONALLY_ALLOWED_WORDS = {
    "医薬", "医薬部外品", "部外品", "薬用", "ニキビケア", "ニキビ ケア",
    "美白", "殺菌", "消炎", "予防", "防ぐ", "効果", "効能",
}
COSMETICS_CONDITIONALLY_ALLOWED_WORDS = {"化粧品"}
AMAZON_BOOK_ROOT_NAMES = {"本", "洋書", "Kindle本"}
RAKUTEN_BOOK_ROOT = "本・雑誌・コミック"
RAKUTEN_GENERIC_BOOK_PATH = f"{RAKUTEN_BOOK_ROOT}>その他"


def _amazon_category_names(keepa_result: KeepaProductData | None) -> list[str]:
    if keepa_result is None:
        return []
    return [
        str(node.get("name") or "").strip()
        for node in keepa_result.category_tree
        if isinstance(node, dict) and str(node.get("name") or "").strip()
    ]


def _is_amazon_book_category(keepa_result: KeepaProductData | None) -> bool:
    names = _amazon_category_names(keepa_result)
    return bool(names and names[0] in AMAZON_BOOK_ROOT_NAMES)


def _is_rakuten_book_genre(genre_id: int | None, master_data: MasterData) -> bool:
    if genre_id is None:
        return False
    return str(master_data.genre_paths.get(int(genre_id)) or "").startswith(f"{RAKUTEN_BOOK_ROOT}>")


def _generic_rakuten_book_genre_id(master_data: MasterData) -> int | None:
    for genre_id, genre_path in master_data.genre_paths.items():
        if str(genre_path or "") == RAKUTEN_GENERIC_BOOK_PATH:
            return int(genre_id)
    return None


def _book_safe_genre_id(genre_id: int | None, master_data: MasterData) -> int | None:
    """Never use a non-book Rakuten genre for an Amazon book category.

    A legacy leaf-category mapping can be wrong.  For Amazon's book root we
    retain an already-book genre, but otherwise use the broad, low-attribute
    ``本・雑誌・コミック>その他`` genre instead of guessing a more specific
    branch from an overlapping word such as "ドイツ語".
    """
    if _is_rakuten_book_genre(genre_id, master_data):
        return genre_id
    return _generic_rakuten_book_genre_id(master_data)


def same_jan_prohibited_word_exception(
    *,
    matched_words: list[dict[str, object]],
    keepa_result: KeepaProductData,
    warnings: list[str],
) -> dict[str, object] | None:
    """Return the audit payload when a non-sensitive word is market-exempt.

    The exception is deliberately exact-JAN only.  It does not apply to
    efficacy/medical-sensitive terms, even when the item is widely listed.
    """
    if not matched_words:
        return None
    jan_code = str(keepa_result.ean or "").strip()
    cosmetics_category = is_cosmetics_category(keepa_result.category_tree)
    same_jan_listing_count = rakuten_listing_count_for_jan(jan_code)
    if same_jan_listing_count is None:
        warnings.append("Rakuten same-JAN listing count: unavailable")
        return None
    warnings.append(f"Rakuten same-JAN listing count: {same_jan_listing_count}")
    if has_sensitive_forbidden_word(matched_words, cosmetics_category=cosmetics_category):
        return None
    if same_jan_listing_count < MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION:
        return None

    words = list(dict.fromkeys(str(item.get("word") or "").strip() for item in matched_words))
    words = [word for word in words if word]
    message = (
        "禁止語一致だが楽天同一JAN "
        f"{same_jan_listing_count}件のため例外通過: {', '.join(words)}"
    )
    warnings.append(message)
    return {
        "type": "same_jan_marketplace",
        "message": message,
        "matched_words": words,
        "jan_code": jan_code,
        "same_jan_listing_count": int(same_jan_listing_count),
        "minimum_listing_count": MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION,
    }


def apply_cleanup_replacements(text: str, replacements: list[tuple[str, str]]) -> tuple[str, list[MatchedRule]]:
    result = text
    matched: list[MatchedRule] = []
    for source, target in replacements:
        if source and source in result:
            result = result.replace(source, target)
            matched.append(MatchedRule("replacement", source, f"{source} -> {target}"))
    return result, matched


def build_image_candidates(
    images_csv: str,
    management_number: str,
    *,
    image_urls: list[str] | None = None,
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    raw_tokens = image_urls if image_urls else (images_csv or "").split(",")
    for index, token in enumerate(raw_tokens, start=1):
        value = token.strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            source = value
        elif "." in value:
            source = f"https://m.media-amazon.com/images/I/{value}"
        else:
            source = f"https://m.media-amazon.com/images/I/{value}.jpg"
        candidates.append(
            {
                "source": source,
                "target": f"/{management_number}_{index}.jpg",
            }
        )
    return candidates


def _coalesce_title(amazon_result: AmazonCheckResult | None, keepa_result: KeepaProductData | None) -> str:
    if amazon_result and amazon_result.title:
        return amazon_result.title.strip()
    if keepa_result and keepa_result.title:
        return keepa_result.title.strip()
    return ""


def _build_descriptions(title: str, keepa_result: KeepaProductData | None) -> tuple[str, str]:
    if keepa_result is None:
        return "", ""

    intro_parts: list[str] = []
    if keepa_result.size:
        intro_parts.append(f"\u30b5\u30a4\u30ba: {keepa_result.size}")
    if title or keepa_result.title:
        intro_parts.append(f"\u5546\u54c1\u540d: {title or keepa_result.title}")

    feature_lines = [item for item in keepa_result.features if item]
    description = keepa_result.description.strip()

    body_parts = ["<br />".join(intro_parts)] if intro_parts else []
    if feature_lines:
        body_parts.append("<br />".join(feature_lines[:10]))
    if description:
        body_parts.append(description)
    final_text = "<br />".join(part for part in body_parts if part)
    return final_text, final_text


def build_regulated_product_disclosure(evidence: dict[str, object]) -> str:
    """Build the mandatory factual disclosure without any other shop's copy."""
    lines = [
        f"広告文責: {evidence['advertiser_name']}",
        f"電話番号: {evidence['advertiser_phone']}",
        f"メーカー名または販売業者名: {evidence['manufacturer']}",
        "原産国: 日本",
        f"商品区分: {evidence['product_category']}",
    ]
    return "<br />".join(lines)


def append_regulated_product_disclosure(description: str, evidence: dict[str, object]) -> str:
    """Append the disclosure once, preserving the existing product description."""
    disclosure = build_regulated_product_disclosure(evidence)
    text = str(description or "").strip()
    if not text:
        return disclosure
    if disclosure in text:
        return text
    return f"{text}<br /><br />{disclosure}"


def _build_quasi_drug_descriptions(title: str, keepa_result: KeepaProductData, evidence: dict[str, object]) -> tuple[str, str]:
    """Keep product facts, then append only the mandatory disclosure."""
    base_pc, base_sp = _build_descriptions(title, keepa_result)
    if not base_pc:
        base_pc = f"商品名: {title}"
    if not base_sp:
        base_sp = f"商品名: {title}"
    return (
        append_regulated_product_disclosure(base_pc, evidence),
        append_regulated_product_disclosure(base_sp, evidence),
    )


def _is_quasi_drug_allowed_match(item: dict[str, object], evidence: dict[str, object]) -> bool:
    if not evidence:
        return False
    allowed = QUASI_DRUG_CONDITIONALLY_ALLOWED_WORDS if evidence.get("product_category") == "医薬部外品" else COSMETICS_CONDITIONALLY_ALLOWED_WORDS
    return str(item.get("word") or "") in allowed


def evaluate_listing(
    *,
    asin: str,
    amazon_result: AmazonCheckResult | None,
    keepa_result: KeepaProductData | None,
    master_data: MasterData,
    store_settings: StoreSettings,
    management_number: str,
    resolved_fields: dict[str, object] | None = None,
    common_settings: ListingCommonSettings | None = None,
    quasi_drug_evidence: dict[str, object] | None = None,
    bypass_rules: set[str] | frozenset[str] | None = None,
    require_minimum_same_jan_listings: bool = False,
) -> EvaluationResult:
    asin = asin.strip().upper()
    bypass_rules = set(bypass_rules or ())
    matched_rules: list[MatchedRule] = []
    warnings: list[str] = []
    allowed_phrase_matches: list[dict[str, object]] = []
    matched_forbidden_words: list[dict[str, object]] = []
    required_separate_checks: list[str] = []
    matched_separate_check_phrases: list[dict[str, object]] = []
    prohibited_word_exceptions: list[dict[str, object]] = []
    legacy_spacing_reviews: list[dict[str, object]] = []
    forced_bypass_checks: list[dict[str, object]] = []

    def record_bypass(rule: str, reason: str) -> None:
        forced_bypass_checks.append({"rule": rule, "reason": reason})
        warnings.append(f"条件無視で通過: {reason}")

    if master_data.missing_files:
        warnings.append("missing master files: " + ", ".join(master_data.missing_files))

    if asin in master_data.kako_ng:
        matched_rules.append(MatchedRule("kakoNG", asin, master_data.kako_ng[asin]))
        if "past_ng" not in bypass_rules:
            return EvaluationResult(
                "business_ng",
                f"\u904e\u53bbNG: {master_data.kako_ng[asin]}",
                matched_rules,
                warnings,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                legacy_spacing_reviews=legacy_spacing_reviews,
            )
        record_bypass("past_ng", f"過去NG: {master_data.kako_ng[asin]}")

    if asin in master_data.blacklist:
        matched_rules.append(MatchedRule("blacklist", asin, "ASIN matched blacklist"))
        if "blacklist" not in bypass_rules:
            return EvaluationResult(
                "business_ng",
                "\u30d6\u30e9\u30c3\u30af\u30ea\u30b9\u30c8",
                matched_rules,
                warnings,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                legacy_spacing_reviews=legacy_spacing_reviews,
            )
        record_bypass("blacklist", "ブラックリスト")

    if amazon_result is None:
        return EvaluationResult(
            "missing_required_data",
            "Amazon\u78ba\u8a8d\u7d50\u679c\u304c\u3042\u308a\u307e\u305b\u3093",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if amazon_result.system_error:
        return EvaluationResult(
            "system_error",
            amazon_result.ng_reason or "Amazon\u78ba\u8a8d\u3067\u30b7\u30b9\u30c6\u30e0\u30a8\u30e9\u30fc",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if amazon_result.business_ng:
        return EvaluationResult(
            "business_ng",
            amazon_result.ng_reason or "Amazon\u78ba\u8a8d\u3067NG",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if amazon_result.page_asin and amazon_result.page_asin != asin:
        return EvaluationResult(
            "business_ng",
            "ASIN\u4e0d\u4e00\u81f4",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if amazon_result.amazon_price is None or amazon_result.amazon_price <= 0:
        return EvaluationResult(
            "business_ng",
            "Amazon\u4fa1\u683c\u304c\u53d6\u5f97\u3067\u304d\u307e\u305b\u3093",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if amazon_result.available_qty is None or amazon_result.available_qty <= 0:
        return EvaluationResult(
            "business_ng",
            "Amazon\u5728\u5eab\u304c\u3042\u308a\u307e\u305b\u3093",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if amazon_result.gift_available is not True:
        return EvaluationResult(
            "business_ng",
            "Amazon\u30ae\u30d5\u30c8\u8a2d\u5b9a\u304c\u7121\u52b9\u3067\u3059",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if keepa_result is None:
        return EvaluationResult(
            "missing_required_data",
            "Keepa\u7d50\u679c\u304c\u3042\u308a\u307e\u305b\u3093",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if keepa_result.is_adult:
        return EvaluationResult(
            "business_ng",
            "Keepa isAdult=true",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    # The dedicated forced-listing page intentionally relaxes only selected
    # master/data rules.  It always retains external resale evidence: five
    # distinct Rakuten shops must sell the exact JAN, or the same product must
    # be confirmed through a high-confidence maker/model/title match.
    if require_minimum_same_jan_listings:
        marketplace_evidence = rakuten_marketplace_evidence(
            jan_code=keepa_result.ean,
            title=amazon_result.title or keepa_result.title,
            brand=keepa_result.brand,
            manufacturer=keepa_result.manufacturer,
            model=keepa_result.model,
            part_number=keepa_result.part_number,
            minimum_shops=MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION,
        )
        if marketplace_evidence is None:
            return EvaluationResult(
                "business_ng", "楽天の複数店舗確認を取得できないため出品不可", matched_rules, warnings,
                forced_bypass_checks=forced_bypass_checks,
            )
        jan_shop_count = int(marketplace_evidence.get("jan_exact_shop_count") or 0)
        text_shop_count = int(marketplace_evidence.get("text_match_shop_count") or 0)
        confirmed_shop_count = int(marketplace_evidence.get("confirmed_shop_count") or 0)
        minimum_shops = int(marketplace_evidence.get("minimum_shops") or MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION)
        query = str(marketplace_evidence.get("query") or "")
        source = str(marketplace_evidence.get("source") or "")
        evidence_summary = (
            f"楽天複数店舗確認: JAN一致 {jan_shop_count}店舗 / "
            f"高精度文言一致 {text_shop_count}店舗 / 合計 {confirmed_shop_count}店舗"
        )
        if query:
            evidence_summary += f" / 検索: {query}"
        warnings.append(evidence_summary)
        if not marketplace_evidence.get("accepted"):
            return EvaluationResult(
                "business_ng",
                f"楽天複数店舗確認が不足: {confirmed_shop_count} < {minimum_shops}店舗（JAN一致 {jan_shop_count} / 高精度文言一致 {text_shop_count}）",
                matched_rules,
                warnings,
                forced_bypass_checks=forced_bypass_checks,
            )
        forced_bypass_checks.append(
            {
                "rule": "rakuten_marketplace_evidence",
                "reason": f"{evidence_summary} / 根拠: {source}",
            }
        )

    quasi_drug_evidence = dict(quasi_drug_evidence or {})
    title_original = _coalesce_title(amazon_result, keepa_result)
    description_pc_original, description_sp_original = _build_descriptions(title_original, keepa_result)

    title, replacement_hits = apply_cleanup_replacements(title_original, master_data.cleanup_replacements)
    description_pc, replacement_hits_pc = apply_cleanup_replacements(description_pc_original, master_data.cleanup_replacements)
    description_sp, replacement_hits_sp = apply_cleanup_replacements(description_sp_original, master_data.cleanup_replacements)
    matched_rules.extend(replacement_hits)
    matched_rules.extend(replacement_hits_pc)
    matched_rules.extend(replacement_hits_sp)
    if quasi_drug_evidence:
        # The mandatory disclosure labels are compliance text, not product copy.
        # Do not let legacy product-word cleanup rules alter them.
        description_pc, description_sp = _build_quasi_drug_descriptions(title, keepa_result, quasi_drug_evidence)

    prohibited_analysis = analyze_prohibited_word_issues(
        {
            "title": title,
            "description_pc": description_pc,
            "description_sp": description_sp,
        },
        list(dict.fromkeys(list(master_data.prohibited_words_rakuten) + list(master_data.prohibited_words_other) + list(MANDATORY_COMPLIANCE_FORBIDDEN_WORDS))),
        master_data.allowed_phrase_rules,
        separate_check_rules=master_data.allowed_phrase_separate_checks,
    )
    allowed_phrase_matches.extend(prohibited_analysis["allowed_phrase_matches"])
    matched_forbidden_words.extend(prohibited_analysis["matched_forbidden_words"])
    if quasi_drug_evidence:
        matched_forbidden_words = [
            item for item in matched_forbidden_words
            if not _is_quasi_drug_allowed_match(item, quasi_drug_evidence)
        ]
    for check in prohibited_analysis["required_separate_checks"]:
        if check not in required_separate_checks:
            required_separate_checks.append(check)
    matched_separate_check_phrases.extend(prohibited_analysis["matched_separate_check_phrases"])
    if matched_forbidden_words:
        exception = same_jan_prohibited_word_exception(
            matched_words=matched_forbidden_words,
            keepa_result=keepa_result,
            warnings=warnings,
        )
        if exception:
            prohibited_word_exceptions.append(exception)
            matched_forbidden_words = []
        elif "prohibited_words" not in bypass_rules:
            word = str(matched_forbidden_words[0]["word"])
            matched_rules.append(MatchedRule("kinsiword", word, f"prohibited word matched: {word}"))
            return EvaluationResult(
                "business_ng",
                f"prohibited word matched: {word}",
                matched_rules,
                warnings,
                title=title,
                description_pc=description_pc,
                description_sp=description_sp,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                prohibited_word_exceptions=prohibited_word_exceptions,
                required_separate_checks=required_separate_checks,
                matched_separate_check_phrases=matched_separate_check_phrases,
                legacy_spacing_reviews=legacy_spacing_reviews,
                compliance_evidence=quasi_drug_evidence,
            )
        else:
            words = ", ".join(
                str(item.get("word") or "").strip()
                for item in matched_forbidden_words
                if str(item.get("word") or "").strip()
            )
            record_bypass("prohibited_words", f"禁止語: {words or '一致あり'}")
            matched_forbidden_words = []

    if keepa_result.category_id is None:
        return EvaluationResult(
            "unknown_category",
            "Keepa category id \u304c\u3042\u308a\u307e\u305b\u3093",
            matched_rules,
            warnings,
            title=title,
            description_pc=description_pc,
            description_sp=description_sp,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            prohibited_word_exceptions=prohibited_word_exceptions,
            required_separate_checks=required_separate_checks,
            matched_separate_check_phrases=matched_separate_check_phrases,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    genre_id = master_data.category_map.get(int(keepa_result.category_id))
    provisional_genre_candidate: dict[str, object] = {}
    amazon_book_category = _is_amazon_book_category(keepa_result)
    if amazon_book_category:
        original_genre_id = genre_id
        genre_id = _book_safe_genre_id(genre_id, master_data)
        if genre_id is None:
            return EvaluationResult(
                "unknown_category",
                "Amazonカテゴリが本ですが、汎用書籍ジャンルをマスターに見つけられません",
                matched_rules,
                warnings,
                title=title,
                description_pc=description_pc,
                description_sp=description_sp,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                prohibited_word_exceptions=prohibited_word_exceptions,
                required_separate_checks=required_separate_checks,
                matched_separate_check_phrases=matched_separate_check_phrases,
                legacy_spacing_reviews=legacy_spacing_reviews,
            )
        if genre_id != original_genre_id:
            original_path = str(master_data.genre_paths.get(int(original_genre_id or 0)) or "").strip()
            matched_rules.append(
                MatchedRule(
                    "book_generic_genre_fallback",
                    str(genre_id),
                    "Amazonカテゴリの本ルートと不整合のため汎用書籍ジャンルを選択"
                    + (f": {original_path}" if original_path else ""),
                )
            )
            warnings.append(
                f"Amazonカテゴリの本ルートのため、汎用書籍ジャンルを選択しました: {genre_id}"
            )
    if genre_id is None:
        provisional = suggest_provisional_genre(
            amazon_result=amazon_result,
            keepa_result=keepa_result,
            master_data=master_data,
        )
        if not provisional or not provisional.get("genre_id"):
            return EvaluationResult(
                "unknown_category",
                f"\u30ab\u30c6\u30b4\u30ea\u672a\u5bfe\u5fdc: {keepa_result.category_id}",
                matched_rules,
                warnings,
                title=title,
                description_pc=description_pc,
                description_sp=description_sp,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                prohibited_word_exceptions=prohibited_word_exceptions,
                required_separate_checks=required_separate_checks,
                matched_separate_check_phrases=matched_separate_check_phrases,
                legacy_spacing_reviews=legacy_spacing_reviews,
                provisional_genre_candidate=provisional_genre_candidate,
            )
        genre_id = int(provisional["genre_id"])
        provisional_genre_candidate = dict(provisional)
        matched_rules.append(
            MatchedRule(
                "provisional_genre",
                str(genre_id),
                f"Keepa category {keepa_result.category_id} used provisional genreId {genre_id}",
            )
        )
        warnings.append(
            f"仮ジャンルを使用しています: Keepa category {keepa_result.category_id} -> genreId {genre_id}; RMSで確認・必要なら編集してください"
        )

    if resolved_fields is None:
        resolved_fields = build_resolved_fields(
            amazon_result=amazon_result,
            keepa_result=keepa_result,
            master_data=master_data,
        )
    if amazon_book_category:
        resolved_fields["genre_id"] = ResolvedField(
            value=int(genre_id),
            source="book_root_fallback",
            raw_path="products[0].categoryTree[0].name",
            transform="amazon_book_root -> generic_rakuten_book_genre",
            confidence="high",
            evidence="Amazon category root is a book category",
            fallback_used=True,
            resolution_action="use_book_generic_genre",
        )

    attr_names = master_data.attribute_definitions.get(int(genre_id), [])
    resolved_attributes = resolve_required_attributes(
        genre_id=int(genre_id),
        attr_names=attr_names,
        resolved_fields=resolved_fields,
        keepa_result=keepa_result,
        amazon_result=amazon_result,
        asin=asin,
    )
    attribute_fields: dict[str, str] = {}
    for attr_name, field in resolved_attributes.items():
        value = str(field.value or "").strip()
        if not value:
            continue
        cleaned_value, replacement_hits = apply_cleanup_replacements(value, master_data.cleanup_replacements)
        matched_rules.extend(replacement_hits)
        attribute_fields[f"attribute:{attr_name}"] = cleaned_value

    if attribute_fields:
        attribute_analysis = analyze_prohibited_word_issues(
            attribute_fields,
            list(master_data.prohibited_words_rakuten) + list(master_data.prohibited_words_other),
            master_data.allowed_phrase_rules,
            separate_check_rules=master_data.allowed_phrase_separate_checks,
        )
        allowed_phrase_matches.extend(attribute_analysis["allowed_phrase_matches"])
        matched_forbidden_words.extend(attribute_analysis["matched_forbidden_words"])
        for check in attribute_analysis["required_separate_checks"]:
            if check not in required_separate_checks:
                required_separate_checks.append(check)
        matched_separate_check_phrases.extend(attribute_analysis["matched_separate_check_phrases"])
        if matched_forbidden_words:
            exception = same_jan_prohibited_word_exception(
                matched_words=matched_forbidden_words,
                keepa_result=keepa_result,
                warnings=warnings,
            )
            if exception:
                prohibited_word_exceptions.append(exception)
                matched_forbidden_words = []
            elif "prohibited_words" not in bypass_rules:
                word = str(matched_forbidden_words[0]["word"])
                matched_rules.append(MatchedRule("kinsiword", word, f"prohibited word matched: {word}"))
                return EvaluationResult(
                    "business_ng",
                    f"prohibited word matched: {word}",
                    matched_rules,
                    warnings,
                    title=title,
                    description_pc=description_pc,
                    description_sp=description_sp,
                    genre_id=genre_id,
                    resolved_attributes=resolved_attributes,
                    allowed_phrase_matches=allowed_phrase_matches,
                    matched_forbidden_words=matched_forbidden_words,
                    prohibited_word_exceptions=prohibited_word_exceptions,
                    required_separate_checks=required_separate_checks,
                    matched_separate_check_phrases=matched_separate_check_phrases,
                    legacy_spacing_reviews=legacy_spacing_reviews,
                )
            else:
                words = ", ".join(
                    str(item.get("word") or "").strip()
                    for item in matched_forbidden_words
                    if str(item.get("word") or "").strip()
                )
                record_bypass("prohibited_words", f"属性の禁止語: {words or '一致あり'}")
                matched_forbidden_words = []

    legacy_spacing_reviews = detect_legacy_spacing_reviews(
        {
            "title": title_original,
            "description_pc": description_pc_original,
            "description_sp": description_sp_original,
            **{
                f"attribute:{attr_name}": str(field.value or "").strip()
                for attr_name, field in resolved_attributes.items()
                if str(field.value or "").strip()
            },
        },
        master_data.legacy_spacing_replacements,
        master_data.allowed_phrase_rules,
    )
    if legacy_spacing_reviews:
        warnings.append("legacy spacing-only replacement rules remain unmigrated; execute must stop until reviewed")
    if required_separate_checks:
        warnings.append("separate review required: " + ", ".join(required_separate_checks))

    if common_settings is None:
        common_settings, common_setting_warnings = load_listing_common_settings(store_settings)
        warnings.extend(common_setting_warnings)

    if keepa_result.avg90_new_offer_count is None:
        if "seller_count" not in bypass_rules:
            return EvaluationResult(
                "business_ng",
                "過去90日の新品出品者数平均が未取得のため出品不可",
                matched_rules,
                warnings,
                title=title,
                description_pc=description_pc,
                description_sp=description_sp,
                genre_id=genre_id,
                resolved_attributes=resolved_attributes,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                prohibited_word_exceptions=prohibited_word_exceptions,
                required_separate_checks=required_separate_checks,
                matched_separate_check_phrases=matched_separate_check_phrases,
                legacy_spacing_reviews=legacy_spacing_reviews,
                provisional_genre_candidate=provisional_genre_candidate,
            )
        record_bypass("seller_count", "過去90日の新品出品者数平均が未取得")
        seller_count_evaluation = {
            "actual_value": None,
            "minimum_value": common_settings.min_avg90_new_offer_count,
            "passed": True,
            "reason": "条件無視",
        }
    else:
        seller_count_evaluation = build_seller_count_evaluation(
            actual_value=keepa_result.avg90_new_offer_count,
            minimum_value=common_settings.min_avg90_new_offer_count,
        )
    if not seller_count_evaluation["passed"]:
        if "seller_count" not in bypass_rules:
            return EvaluationResult(
                "business_ng",
                f"過去90日の新品出品者数平均が基準未満: {seller_count_evaluation['actual_value']} < {seller_count_evaluation['minimum_value']}",
                matched_rules,
                warnings,
                title=title,
                description_pc=description_pc,
                description_sp=description_sp,
                genre_id=genre_id,
                attributes=[],
                resolved_attributes=resolved_attributes,
                seller_count_evaluation=seller_count_evaluation,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                prohibited_word_exceptions=prohibited_word_exceptions,
                required_separate_checks=required_separate_checks,
                matched_separate_check_phrases=matched_separate_check_phrases,
                legacy_spacing_reviews=legacy_spacing_reviews,
                provisional_genre_candidate=provisional_genre_candidate,
            )
        record_bypass(
            "seller_count",
            f"過去90日の新品出品者数平均が基準未満: {seller_count_evaluation['actual_value']} < {seller_count_evaluation['minimum_value']}",
        )
        seller_count_evaluation = {**seller_count_evaluation, "passed": True, "reason": "条件無視"}

    attributes: list[dict[str, str]] = []
    missing_attrs: list[str] = []
    for attr_name in attr_names:
        resolved = resolved_attributes.get(attr_name)
        value = "" if resolved is None else str(resolved.value or "").strip()
        if not value or (resolved is not None and resolved.resolution_action == "needs_review"):
            missing_attrs.append(attr_name)
            continue
        attributes.append({"name": attr_name, "value": value})

    if missing_attrs:
        if "missing_attributes" not in bypass_rules:
            return EvaluationResult(
                "missing_required_data",
                "\u5c5e\u6027\u4e0d\u8db3: " + ", ".join(missing_attrs),
                matched_rules,
                warnings,
                title=title,
                description_pc=description_pc,
                description_sp=description_sp,
                genre_id=genre_id,
                attributes=attributes,
                resolved_attributes=resolved_attributes,
                seller_count_evaluation=seller_count_evaluation,
                allowed_phrase_matches=allowed_phrase_matches,
                matched_forbidden_words=matched_forbidden_words,
                prohibited_word_exceptions=prohibited_word_exceptions,
                required_separate_checks=required_separate_checks,
                matched_separate_check_phrases=matched_separate_check_phrases,
                legacy_spacing_reviews=legacy_spacing_reviews,
                provisional_genre_candidate=provisional_genre_candidate,
            )
        for attr_name in missing_attrs:
            resolved_attributes[attr_name] = ResolvedField(
                value="-",
                source="forced_bypass",
                transform="missing_required_attribute",
                confidence="none",
                evidence="条件無視ASIN出品で属性不足を明示的に許可",
                fallback_used=True,
                resolution_action="use_legacy_dash",
            )
            attributes.append({"name": attr_name, "value": "-"})
        record_bypass("missing_attributes", "属性不足: " + ", ".join(missing_attrs))

    article_number = keepa_result.ean or asin

    image_candidates = build_image_candidates(
        keepa_result.images_csv,
        management_number,
        image_urls=keepa_result.image_urls,
    )
    if not image_candidates:
        return EvaluationResult(
            "missing_required_data",
            "\u753b\u50cf\u5019\u88dc\u304c\u3042\u308a\u307e\u305b\u3093",
            matched_rules,
            warnings,
            title=title,
            description_pc=description_pc,
            description_sp=description_sp,
            genre_id=genre_id,
            attributes=attributes,
            resolved_attributes=resolved_attributes,
            seller_count_evaluation=seller_count_evaluation,
            article_number=article_number,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            prohibited_word_exceptions=prohibited_word_exceptions,
            required_separate_checks=required_separate_checks,
            matched_separate_check_phrases=matched_separate_check_phrases,
            legacy_spacing_reviews=legacy_spacing_reviews,
            provisional_genre_candidate=provisional_genre_candidate,
        )

    return EvaluationResult(
        "eligible",
        "\u51fa\u54c1\u53ef\u80fd",
        matched_rules,
        warnings,
        title=title,
        description_pc=description_pc,
        description_sp=description_sp,
        genre_id=genre_id,
        attributes=attributes,
        resolved_attributes=resolved_attributes,
        seller_count_evaluation=seller_count_evaluation,
        article_number=article_number,
        image_candidates=image_candidates,
        allowed_phrase_matches=allowed_phrase_matches,
        matched_forbidden_words=matched_forbidden_words,
        prohibited_word_exceptions=prohibited_word_exceptions,
        required_separate_checks=required_separate_checks,
        matched_separate_check_phrases=matched_separate_check_phrases,
        legacy_spacing_reviews=legacy_spacing_reviews,
        provisional_genre_candidate=provisional_genre_candidate,
        compliance_evidence=quasi_drug_evidence,
        forced_bypass_checks=forced_bypass_checks,
    )
