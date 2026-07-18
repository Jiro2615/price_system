from __future__ import annotations

from scripts.listing.attribute_policy import resolve_required_attributes
from scripts.listing.attribute_resolver import build_resolved_fields
from scripts.listing.common_settings import build_seller_count_evaluation, load_listing_common_settings
from scripts.listing.models import AmazonCheckResult, EvaluationResult, KeepaProductData, ListingCommonSettings, MasterData, MatchedRule, StoreSettings
from scripts.listing.prohibited_word_masking import analyze_prohibited_word_issues, detect_legacy_spacing_reviews
from scripts.listing.provisional_genre import suggest_provisional_genre


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
) -> EvaluationResult:
    asin = asin.strip().upper()
    matched_rules: list[MatchedRule] = []
    warnings: list[str] = []
    allowed_phrase_matches: list[dict[str, object]] = []
    matched_forbidden_words: list[dict[str, object]] = []
    required_separate_checks: list[str] = []
    matched_separate_check_phrases: list[dict[str, object]] = []
    legacy_spacing_reviews: list[dict[str, object]] = []

    if master_data.missing_files:
        warnings.append("missing master files: " + ", ".join(master_data.missing_files))

    if asin in master_data.kako_ng:
        matched_rules.append(MatchedRule("kakoNG", asin, master_data.kako_ng[asin]))
        return EvaluationResult(
            "business_ng",
            f"\u904e\u53bbNG: {master_data.kako_ng[asin]}",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if asin in master_data.blacklist:
        matched_rules.append(MatchedRule("blacklist", asin, "ASIN matched blacklist"))
        return EvaluationResult(
            "business_ng",
            "\u30d6\u30e9\u30c3\u30af\u30ea\u30b9\u30c8",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    if asin in master_data.listed_asins:
        management = master_data.listed_asins.get(asin, "")
        matched_rules.append(MatchedRule("shuppinlist", asin, management or "already listed"))
        return EvaluationResult(
            "already_listed",
            f"\u65e2\u306b\u51fa\u54c1\u6e08\u307f: {management}",
            matched_rules,
            warnings,
            allowed_phrase_matches=allowed_phrase_matches,
            matched_forbidden_words=matched_forbidden_words,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

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

    title_original = _coalesce_title(amazon_result, keepa_result)
    description_pc_original, description_sp_original = _build_descriptions(title_original, keepa_result)

    title, replacement_hits = apply_cleanup_replacements(title_original, master_data.cleanup_replacements)
    description_pc, replacement_hits_pc = apply_cleanup_replacements(description_pc_original, master_data.cleanup_replacements)
    description_sp, replacement_hits_sp = apply_cleanup_replacements(description_sp_original, master_data.cleanup_replacements)
    matched_rules.extend(replacement_hits)
    matched_rules.extend(replacement_hits_pc)
    matched_rules.extend(replacement_hits_sp)

    prohibited_analysis = analyze_prohibited_word_issues(
        {
            "title": title,
            "description_pc": description_pc,
            "description_sp": description_sp,
        },
        list(master_data.prohibited_words_rakuten) + list(master_data.prohibited_words_other),
        master_data.allowed_phrase_rules,
        separate_check_rules=master_data.allowed_phrase_separate_checks,
    )
    allowed_phrase_matches.extend(prohibited_analysis["allowed_phrase_matches"])
    matched_forbidden_words.extend(prohibited_analysis["matched_forbidden_words"])
    for check in prohibited_analysis["required_separate_checks"]:
        if check not in required_separate_checks:
            required_separate_checks.append(check)
    matched_separate_check_phrases.extend(prohibited_analysis["matched_separate_check_phrases"])
    if matched_forbidden_words:
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
            required_separate_checks=required_separate_checks,
            matched_separate_check_phrases=matched_separate_check_phrases,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

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
            required_separate_checks=required_separate_checks,
            matched_separate_check_phrases=matched_separate_check_phrases,
            legacy_spacing_reviews=legacy_spacing_reviews,
        )

    genre_id = master_data.category_map.get(int(keepa_result.category_id))
    provisional_genre_candidate: dict[str, object] = {}
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
                required_separate_checks=required_separate_checks,
                matched_separate_check_phrases=matched_separate_check_phrases,
                legacy_spacing_reviews=legacy_spacing_reviews,
            )

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

    seller_count_evaluation = build_seller_count_evaluation(
        actual_value=keepa_result.avg90_new_offer_count,
        minimum_value=common_settings.min_avg90_new_offer_count,
    )
    if not seller_count_evaluation["passed"]:
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
            required_separate_checks=required_separate_checks,
            matched_separate_check_phrases=matched_separate_check_phrases,
            legacy_spacing_reviews=legacy_spacing_reviews,
            provisional_genre_candidate=provisional_genre_candidate,
        )

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
            required_separate_checks=required_separate_checks,
            matched_separate_check_phrases=matched_separate_check_phrases,
            legacy_spacing_reviews=legacy_spacing_reviews,
            provisional_genre_candidate=provisional_genre_candidate,
        )

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
        required_separate_checks=required_separate_checks,
        matched_separate_check_phrases=matched_separate_check_phrases,
        legacy_spacing_reviews=legacy_spacing_reviews,
        provisional_genre_candidate=provisional_genre_candidate,
    )
