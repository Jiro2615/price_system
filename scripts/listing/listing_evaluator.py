from __future__ import annotations

from typing import Iterable

from .models import AmazonCheckResult, EvaluationResult, KeepaProductData, MasterData, MatchedRule, StoreSettings


ATTRIBUTE_CANDIDATES = {
    "\u30ab\u30e9\u30fc": ("color",),
    "\u7e67\uff7a\u7e5d\uff6b\u7e5d\uff69\u7e67\uff7c": ("color",),
    "\u30d6\u30e9\u30f3\u30c9\u540d": ("brand",),
    "\u7e5d\u6096\u039b\u7e5d\uff73\u7e5d\u7259\u9326": ("brand",),
    "\u30e1\u30fc\u30ab\u30fc\u578b\u756a": ("model",),
    "\u7e5d\uff61\u7e5d\uff7c\u7e67\uff6b\u7e5d\uff7c\u8749\u72d7\u5206": ("model",),
    "\u30b7\u30ea\u30fc\u30ba\u540d": ("style", "title"),
    "\u7e67\uff77\u7e5d\uff6a\u7e5d\uff7c\u7e67\uff7a\u8737\u30fb": ("style", "title"),
    "\u30b5\u30a4\u30ba": ("size",),
    "\u7e67\uff75\u7e67\uff64\u7e67\uff7a": ("size",),
    "\u30b9\u30bf\u30a4\u30eb": ("style",),
    "\u7e67\uff79\u7e67\uff7f\u7e67\uff64\u7e5d\uff6b": ("style",),
    "EAN\u30b3\u30fc\u30c9": ("ean",),
    "EAN\u7e67\uff73\u7e5d\uff7c\u7e5d\u30fb": ("ean",),
    "JAN\u30b3\u30fc\u30c9": ("ean",),
    "JAN\u7e67\uff73\u7e5d\uff7c\u7e5d\u30fb": ("ean",),
}


def apply_replacements(text: str, replacements: list[tuple[str, str]]) -> tuple[str, list[MatchedRule]]:
    result = text
    matched: list[MatchedRule] = []
    for source, target in replacements:
        if source and source in result:
            result = result.replace(source, target)
            matched.append(MatchedRule("replacement", source, f"{source} -> {target}"))
    return result, matched


def detect_prohibited_words(texts: Iterable[str], words: list[str], source_name: str) -> list[MatchedRule]:
    normalized_text = "\r\n".join(part for part in texts if part)
    matches: list[MatchedRule] = []
    for word in words:
        if word and word in normalized_text:
            matches.append(MatchedRule(source_name, word, f"prohibited word matched: {word}"))
    return matches


def build_image_candidates(images_csv: str, management_number: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for index, token in enumerate((images_csv or "").split(","), start=1):
        value = token.strip()
        if not value:
            continue
        candidates.append(
            {
                "source": f"https://images-na.ssl-images-amazon.com/images/I/{value}.jpg",
                "target": f"/{management_number}_{index}.jpg",
            }
        )
    return candidates


def _resolve_attribute_value(attr_name: str, keepa: KeepaProductData, asin: str) -> str:
    for field_name in ATTRIBUTE_CANDIDATES.get(attr_name, ()):
        value = getattr(keepa, field_name, "")
        if value:
            return str(value)
    if attr_name in {"ASIN", "\u5546\u54c1\u7ba1\u7406\u756a\u53f7"}:
        return asin
    return ""


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
) -> EvaluationResult:
    asin = asin.strip().upper()
    matched_rules: list[MatchedRule] = []
    warnings: list[str] = []

    if master_data.missing_files:
        warnings.append("missing master files: " + ", ".join(master_data.missing_files))

    if asin in master_data.kako_ng:
        matched_rules.append(MatchedRule("kakoNG", asin, master_data.kako_ng[asin]))
        return EvaluationResult("business_ng", f"\u904e\u53bbNG: {master_data.kako_ng[asin]}", matched_rules, warnings)

    if asin in master_data.blacklist:
        matched_rules.append(MatchedRule("blacklist", asin, "ASIN matched blacklist"))
        return EvaluationResult("business_ng", "\u30d6\u30e9\u30c3\u30af\u30ea\u30b9\u30c8", matched_rules, warnings)

    if asin in master_data.listed_asins:
        management = master_data.listed_asins.get(asin, "")
        matched_rules.append(MatchedRule("shuppinlist", asin, management or "already listed"))
        return EvaluationResult("already_listed", f"\u65e2\u306b\u51fa\u54c1\u6e08\u307f: {management}", matched_rules, warnings)

    if amazon_result is None:
        return EvaluationResult("missing_required_data", "Amazon\u78ba\u8a8d\u7d50\u679c\u304c\u3042\u308a\u307e\u305b\u3093", matched_rules, warnings)

    if amazon_result.system_error:
        return EvaluationResult("system_error", amazon_result.ng_reason or "Amazon\u78ba\u8a8d\u3067\u30b7\u30b9\u30c6\u30e0\u30a8\u30e9\u30fc", matched_rules, warnings)

    if amazon_result.business_ng:
        return EvaluationResult("business_ng", amazon_result.ng_reason or "Amazon\u78ba\u8a8d\u3067NG", matched_rules, warnings)

    if amazon_result.page_asin and amazon_result.page_asin != asin:
        return EvaluationResult("business_ng", "ASIN\u4e0d\u4e00\u81f4", matched_rules, warnings)

    if amazon_result.amazon_price is None or amazon_result.amazon_price <= 0:
        return EvaluationResult("business_ng", "Amazon\u4fa1\u683c\u304c\u53d6\u5f97\u3067\u304d\u307e\u305b\u3093", matched_rules, warnings)

    if amazon_result.available_qty is None or amazon_result.available_qty <= 0:
        return EvaluationResult("business_ng", "Amazon\u5728\u5eab\u304c\u3042\u308a\u307e\u305b\u3093", matched_rules, warnings)

    if amazon_result.gift_available is not True:
        return EvaluationResult("business_ng", "Amazon\u30ae\u30d5\u30c8\u8a2d\u5b9a\u304c\u7121\u52b9\u3067\u3059", matched_rules, warnings)

    if keepa_result is None:
        return EvaluationResult("missing_required_data", "Keepa\u7d50\u679c\u304c\u3042\u308a\u307e\u305b\u3093", matched_rules, warnings)

    if keepa_result.is_adult:
        return EvaluationResult("business_ng", "Keepa isAdult=true", matched_rules, warnings)

    if keepa_result.avg90_seller_count is not None and keepa_result.avg90_seller_count < store_settings.min_avg90_sellers:
        return EvaluationResult(
            "business_ng",
            f"90\u65e5\u5e73\u5747\u30bb\u30e9\u30fc\u6570\u4e0d\u8db3: {keepa_result.avg90_seller_count} < {store_settings.min_avg90_sellers}",
            matched_rules,
            warnings,
        )

    title = _coalesce_title(amazon_result, keepa_result)
    description_pc, description_sp = _build_descriptions(title, keepa_result)

    title, replacement_hits = apply_replacements(title, master_data.replacements)
    description_pc, replacement_hits_pc = apply_replacements(description_pc, master_data.replacements)
    description_sp, replacement_hits_sp = apply_replacements(description_sp, master_data.replacements)
    matched_rules.extend(replacement_hits)
    matched_rules.extend(replacement_hits_pc)
    matched_rules.extend(replacement_hits_sp)

    prohibited_hits = detect_prohibited_words(
        [title, description_pc, description_sp],
        list(master_data.prohibited_words_rakuten) + list(master_data.prohibited_words_other),
        "kinsiword",
    )
    if prohibited_hits:
        matched_rules.extend(prohibited_hits)
        return EvaluationResult("business_ng", prohibited_hits[0].detail, matched_rules, warnings)

    if keepa_result.category_id is None:
        return EvaluationResult("unknown_category", "Keepa category id \u304c\u3042\u308a\u307e\u305b\u3093", matched_rules, warnings)

    genre_id = master_data.category_map.get(int(keepa_result.category_id))
    if genre_id is None:
        return EvaluationResult("unknown_category", f"\u30ab\u30c6\u30b4\u30ea\u672a\u5bfe\u5fdc: {keepa_result.category_id}", matched_rules, warnings)

    attr_names = master_data.attribute_definitions.get(int(genre_id), [])
    attributes: list[dict[str, str]] = []
    missing_attrs: list[str] = []
    for attr_name in attr_names:
        value = _resolve_attribute_value(attr_name, keepa_result, asin)
        if not value:
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
        )

    article_number = keepa_result.ean or asin
    if not keepa_result.ean:
        warnings.append("EAN \u304c\u306a\u3044\u305f\u3081 articleNumber \u306b ASIN \u3092\u4f7f\u7528\u3057\u307e\u3057\u305f")

    image_candidates = build_image_candidates(keepa_result.images_csv, management_number)
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
            article_number=article_number,
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
        article_number=article_number,
        image_candidates=image_candidates,
    )
