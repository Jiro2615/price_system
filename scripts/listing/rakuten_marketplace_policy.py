from __future__ import annotations

import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from dotenv import load_dotenv
from scripts.listing.rakuten_search_client import search_items


ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION = 5
MAX_TEXT_SEARCHES = 4
# A documented company/brand spelling pair, not a fuzzy prefix rule.
KNOWN_MAKER_ALIASES = {"象印マホービン": ("象印", "ZOJIRUSHI")}
SENSITIVE_MARKERS = (
    "医療", "医薬", "薬", "コンドーム", "性", "育毛", "殺菌", "除菌", "治療", "効能", "効果",
    "治癒", "予防", "疲労回復", "老化防止", "血液サラサラ", "バストアップ", "デトックス",
    "脂肪燃焼", "代謝促進", "病気", "成人病", "便秘", "精力剤", "性的機能",
)
ALCOHOL_WORD = "アルコール"
COSMETICS_CATEGORY_MARKERS = ("ビューティー", "beauty", "化粧品", "cosmetics")


def _jan_evidence_sources(item: object, jan: str) -> list[str]:
    """Explicit JAN fields or the product slug of a trusted Rakuten item URL."""
    if not isinstance(item, dict) or not jan:
        return []
    pattern = re.compile(r"(?<!\d)" + re.escape(jan) + r"(?!\d)")
    sources = [key for key in ("itemName", "itemCaption", "itemCode")
               if pattern.search(unicodedata.normalize("NFKC", str(item.get(key) or "")))]
    try:
        parsed = urlsplit(str(item.get("itemUrl") or ""))
        parts = [part for part in unquote(parsed.path, errors="strict").split("/") if part]
        shop_code = str(item.get("shopCode") or "").casefold()
        if (parsed.scheme in {"http", "https"} and parsed.hostname == "item.rakuten.co.jp"
                and not parsed.username and not parsed.password
                and parsed.port in {None, 80 if parsed.scheme == "http" else 443}
                and len(parts) == 2 and (not shop_code or parts[0].casefold() == shop_code)
                and pattern.search(unicodedata.normalize("NFKC", parts[1]))):
            sources.append("itemUrl_path")
    except (ValueError, UnicodeDecodeError):
        pass
    return sources


def _item_mentions_exact_jan(item: object, jan: str) -> bool:
    return bool(_jan_evidence_sources(item, jan))


def _search_items(keyword: str, timeout: float, *, postage_included: bool = True) -> list[dict[str, Any]] | None:
    """API failures are acquisition errors, never an empty-product result."""
    return search_items(keyword, timeout, postage_included=postage_included)


def _shop_identity(item: dict[str, Any]) -> str:
    """Return a stable shop key so multiple variants from one shop count once."""
    for key in ("shopCode", "shopUrl", "shopName"):
        value = re.sub(r"\s+", "", str(item.get(key) or "")).casefold()
        if value:
            return f"{key}:{value}"
    # A result without shop information cannot demonstrate a separate seller.
    return ""


def _shop_names(items: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in items:
        identity = _shop_identity(item)
        name = str(item.get("shopName") or item.get("shopCode") or "").strip()
        if identity and identity not in seen:
            names.append(name or identity)
            seen.add(identity)
    return names


def _normalise_product_text(value: object) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]", "", unicodedata.normalize("NFKC", str(value or "")).casefold())


def _item_product_text(item: dict[str, Any]) -> str:
    return _normalise_product_text(" ".join(str(item.get(key) or "") for key in ("itemName", "itemCaption", "itemCode")))


def _model_tokens(*values: object) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
        for token in re.findall(r"(?=[a-z0-9_-]{4,})(?=[a-z0-9_-]*[a-z])(?=[a-z0-9_-]*\d)[a-z0-9_-]+", normalized):
            compact = re.sub(r"[^a-z0-9]", "", token)
            # SPF is a sun-protection specification, not a supplier model.
            # SPF26/PA++ and SPF50PA++++ must not contradict TYU-987.
            if len(compact) >= 4 and not re.fullmatch(r"spf\d+(?:pa)?|\d+(?:mg|kg|g|ml|l|gb|tb|mb|w|v|mm|cm|mah|hz|ghz|dpi)|(?:jan|ean|upc|isbn)\d{8,14}", compact):
                tokens.add(compact)
    return tokens


def _variant_tokens(value: object) -> set[str]:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold().replace(" ", "")
    return {
        re.sub(r"\s+", "", token)
        for token in re.findall(r"\d+(?:\.\d+)?(?:ml|l|g|kg|個|本|枚|包|袋|組|セット|pack)", normalized)
    }


def _strip_pack_quantities(value: object) -> str:
    """Remove sale-pack counts, retaining capacities and model identifiers."""
    text = unicodedata.normalize("NFKC", str(value or ""))

    def remove_count(match: re.Match[str]) -> str:
        if match.group("unit").casefold() == "枚" and (
            re.match(r"焼", text[match.end():])
            or ("食パン" in text[max(0, match.start("number") - 5):match.start("number")]
                and not re.match(r"セット|入|組", text[match.end("unit"):]))
        ):
            return match.group(0)
        return " "

    text = re.sub(
        r"(?:[×*]\s*)?(?P<number>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>個|本|枚|包|袋|組|セット|packs?|pcs)(?:セット|入り|入)?",
        remove_count, text, flags=re.IGNORECASE,
    )
    # Multipliers without a Japanese count unit: 80g×4, 80g (x 4).
    # Do not remove dimensions (10cm×20cm) or an uppercase model such as X4.
    text = re.sub(r"(?:[×*]\s*|(?<![A-Za-z0-9])x\s+)(\d+)(?!\d)"
                  r"(?!\s*(?:ml|mg|kg|gb|tb|mb|l|g|mm|cm|インチ))"
                  r"(?=\s*(?:[)\]】,、。]|$|\s))", " ", text)
    text = re.sub(r"[([【]\s*[)\]】]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _variant_groups(value: object) -> dict[str, set[Decimal]]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    groups: dict[str, set[Decimal]] = {}
    factors = {"ml": ("volume", 1), "l": ("volume", 1000), "mg": ("weight", Decimal("0.001")),
               "g": ("weight", 1), "kg": ("weight", 1000)}
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(ml|mg|kg|gb|tb|mb|l|g|個|本|枚|包|袋|組|セット|pack|pcs)(?![a-z])", text):
        number, unit = match.groups()
        group, factor = factors.get(unit, (unit if unit in {"gb", "tb", "mb"} else "count", 1))
        if unit == "枚" and (re.match(r"焼", text[match.end():]) or
                             ("食パン" in text[max(0, match.start() - 5):match.start()]
                              and not re.match(r"セット|入|組", text[match.end():]))):
            group = "bread_capacity"
        groups.setdefault(group, set()).add(Decimal(number) * factor)
    for count in re.findall(r"(?:[×*]\s*|(?<![a-z0-9])x\s+)(\d+)(?!\d)"
                            r"(?!\s*(?:ml|mg|kg|gb|tb|mb|l|g|mm|cm|インチ))"
                            r"(?=\s*(?:個|本|枚|包|袋|組|セット|packs?|pcs|[)\]】,、。]|$|\s))", text):
        groups.setdefault("count", set()).add(Decimal(count))
    for age, qualifier in re.findall(r"(\d+)\s*[歳才]\s*(以上|から|まで|未満)?", text):
        group = "age_min" if qualifier in {"以上", "から"} else "age_max" if qualifier in {"まで", "未満"} else "age"
        groups.setdefault(group, set()).add(Decimal(age))
    for volume in re.findall(r"(?:第)?(\d+)\s*巻(?!き)", text):
        groups.setdefault("volume_number", set()).add(Decimal(volume))
    return groups


def _colours(value: object) -> set[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    words = {"black": ("ブラック", r"\bblack\b"), "white": ("ホワイト", r"\bwhite\b"),
             "red": ("レッド", r"\bred\b"), "blue": ("ブルー", r"\bblue\b"),
             "silver": ("シルバー", r"\bsilver\b"), "grey": ("グレー", r"\bgr[ae]y\b")}
    return {name for name, patterns in words.items() if any(re.search(pattern, text) for pattern in patterns)}


def _skin_shades(value: object) -> set[str]:
    text = _normalise_product_text(value)
    return {name for name, word in (("natural_skin", "自然な肌色"), ("light_skin", "明るい肌色"))
            if word in text}


def _sun_protection(value: object) -> dict[str, set[str]]:
    """Keep SPF/PA as product specifications, never as model identifiers."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    result = {}
    spf = {str(int(number)) + suffix for number, suffix in
           re.findall(r"(?<![a-z0-9])spf\s*[-_]?\s*(\d+)\s*(\+?)(?!\d)", text)}
    pa = set(re.findall(r"(?<![a-z])pa\s*(\+{1,4})(?!\+)", text))
    if spf:
        result["spf"] = spf
    if pa:
        result["pa"] = pa
    return result


def _distinctive_terms(value: object) -> set[str]:
    text = _normalise_product_text(value)
    return {word for word in ("チキン", "ターキー", "サーモン", "ツナ", "白身魚", "グレインフリー",
                              "避妊", "去勢", "毛玉", "腎臓", "尿路", "詰め替え", "本体別売", "ケーブル付き")
            if word in text}


def _variant_rejection_reason(item: dict[str, Any], title: str, *, ignore_pack_count: bool = False,
                              ignore_postage: bool = False) -> str | None:
    try:
        if "availability" in item and int(item["availability"]) != 1:
            return "unavailable"
        if not ignore_postage and "postageFlag" in item and int(item["postageFlag"]) != 0:
            return "shipping_not_included"
    except (ValueError, TypeError):
        return "invalid_offer_flags"
    if any(word in str(item.get("itemName") or "") for word in ("中古", "整備済", "電子書籍")):
        return "used_or_digital"
    reference_colours, candidate_colours = _colours(title), _colours(item.get("itemName"))
    if reference_colours and candidate_colours and reference_colours.isdisjoint(candidate_colours):
        return "colour_mismatch"
    reference_shades, candidate_shades = _skin_shades(title), _skin_shades(item.get("itemName"))
    if reference_shades and candidate_shades and reference_shades != candidate_shades:
        return "shade_mismatch"
    reference_protection, candidate_protection = _sun_protection(title), _sun_protection(item.get("itemName"))
    if any(reference_protection[key] != candidate_protection[key]
           for key in reference_protection.keys() & candidate_protection.keys()):
        return "sun_protection_mismatch"
    reference_terms, candidate_terms = _distinctive_terms(title), _distinctive_terms(item.get("itemName"))
    for family in ({"チキン", "ターキー", "サーモン", "ツナ", "白身魚"}, {"グレインフリー", "避妊", "去勢", "毛玉", "腎臓", "尿路"}):
        ref, cand = reference_terms & family, candidate_terms & family
        if ref and cand and ref != cand:
            return "product_line_mismatch"
    reference, candidate = _variant_groups(title), _variant_groups(item.get("itemName"))
    ref_age = {key: values for key, values in reference.items() if key.startswith("age")}
    cand_age = {key: values for key, values in candidate.items() if key.startswith("age")}
    if ref_age and cand_age and ref_age != cand_age:
        return "age_mismatch"
    # Conflicting capacities cannot be rescued by a JAN in a mixed-SKU caption.
    # Shop evidence explicitly ignores pack counts; price comparisons do not.
    for group, values in candidate.items():
        if ignore_pack_count and group == "count":
            continue
        if group not in {"count", "bread_capacity", "age", "age_min", "age_max"} and group not in reference and any(key not in {"count", "bread_capacity", "age", "age_min", "age_max"} for key in reference):
            return "capacity_mismatch"
        if group in reference and values != reference[group]:
            return "pack_mismatch" if group == "count" else "capacity_or_spec_mismatch"
    expected_count, actual_count = reference.get("count", {Decimal(1)}), candidate.get("count", {Decimal(1)})
    return None if ignore_pack_count or expected_count == actual_count else "pack_mismatch"


def _candidate_matches_variant(item: dict[str, Any], title: str) -> bool:
    return _variant_rejection_reason(item, title) is None


def _reference_price_summary(items: list[dict[str, Any]], title: str) -> dict[str, Any]:
    candidates = []
    excluded_ambiguous = 0
    excluded_unknown_variant = 0
    excluded_pack = 0
    reference_variants = _variant_groups(title)
    seen_items: set[str] = set()
    for item in items:
        identity = _shop_identity(item) + ":" + (str(item.get("itemCode") or item.get("itemUrl") or "") or str(item.get("itemName") or ""))
        if identity in seen_items:
            continue
        seen_items.add(identity)
        candidate_variants = _variant_groups(item.get("itemName"))
        if candidate_variants.get("count", {Decimal(1)}) != reference_variants.get("count", {Decimal(1)}):
            excluded_pack += 1
            continue
        if any(candidate_variants.get(group) != values for group, values in reference_variants.items() if group != "count"):
            excluded_unknown_variant += 1
            continue
        try:
            price = Decimal(str(item.get("itemPrice")))
            if not price.is_finite() or price <= 0 or price != price.to_integral_value():
                continue
            if int(item.get("availability", 0)) != 1 or int(item.get("postageFlag", 1)) != 0 or int(item.get("taxFlag", 1)) != 0:
                continue
            ambiguous = False
            has_price_range = False
            for index in (1, 2, 3):
                low, high = item.get(f"itemPriceMin{index}"), item.get(f"itemPriceMax{index}")
                if low is not None or high is not None:
                    has_price_range = True
                    if low is None or high is None or Decimal(str(low)) != price or Decimal(str(high)) != price:
                        ambiguous = True
            if ambiguous or not has_price_range:
                excluded_ambiguous += 1
                continue
        except (ValueError, TypeError, InvalidOperation):
            continue
        candidates.append((int(price), item))
    minimum, cheapest = min(candidates, key=lambda pair: pair[0]) if candidates else (None, {})
    item_url = ""
    try:
        parsed_url = urlsplit(str(cheapest.get("itemUrl") or ""))
        if parsed_url.scheme in {"http", "https"} and parsed_url.hostname == "item.rakuten.co.jp" and not parsed_url.username and not parsed_url.password:
            item_url = urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", ""))
    except ValueError:
        pass
    return {
        "reference_min_price": minimum,
        "reference_price_scope": "取得した条件一致商品内の参考最安値（全商品の最安保証なし）",
        "reference_price_item_name": str(cheapest.get("itemName") or ""),
        "reference_price_item_url": item_url,
        "reference_price_shop_name": str(cheapest.get("shopName") or ""),
        "reference_price_candidate_count": len(candidates),
        "ambiguous_price_items_excluded": excluded_ambiguous,
        "unidentified_variant_price_items_excluded": excluded_unknown_variant,
        "different_pack_price_items_excluded": excluded_pack,
    }


def _keyword_query(*, title: str, brand: str, manufacturer: str, model: str, part_number: str) -> str:
    """Build one precise, conservative query for the fallback evidence search."""
    model_values = [str(value).strip() for value in (model, part_number) if str(value).strip()]
    maker = str(brand or manufacturer or "").strip()
    if model_values:
        return " ".join(dict.fromkeys([maker, *model_values])).strip()
    # The title is the only remaining product identifier.  Keep it bounded so
    # marketing copy at the end does not make the API search needlessly broad.
    return " ".join(dict.fromkeys([maker, str(title or "").strip()]))[:120].strip()


def _maker_aliases(brand: str, manufacturer: str) -> list[str]:
    aliases = []
    for raw in (brand, manufacturer):
        normalized = unicodedata.normalize("NFKC", str(raw or "")).strip()
        plain = re.sub(r"\([^)]*\)", " ", normalized).strip()
        plain = re.sub(r"株式会社|有限会社|\(株\)", "", plain).strip()
        aliases.extend(KNOWN_MAKER_ALIASES.get(plain, ()))
        aliases.extend([plain, *re.findall(r"\(([^)]+)\)", normalized)])
    seen, result = set(), []
    for alias in aliases:
        key = _normalise_product_text(alias)
        if len(key) >= 2 and key not in seen:
            seen.add(key)
            result.append(alias)
    # Prefer a Japanese shop-facing spelling, not a literal bilingual label.
    return sorted(result, key=lambda value: not bool(re.search(r"[ぁ-んァ-ヶ一-龥]", value)))


def _title_without_identity(title: str, aliases: list[str], identifiers: tuple[str, ...]) -> str:
    text = unicodedata.normalize("NFKC", str(title or ""))
    for alias in sorted(aliases, key=len, reverse=True):
        pattern = r"\s*".join(re.escape(char) for char in alias if not char.isspace())
        if pattern:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    for code in identifiers:
        if len(code) >= 4:
            text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(code) + r"(?![A-Za-z0-9])", " ", text, flags=re.IGNORECASE)
    return re.sub(r"[()\[\]【】・,／/&]+", " ", text).strip()


def _keyword_queries(*, title: str, brand: str, manufacturer: str, model: str, part_number: str) -> list[str]:
    aliases = _maker_aliases(brand, manufacturer)
    maker = aliases[0] if aliases else ""
    identifiers = tuple(dict.fromkeys(str(value).strip() for value in (model, part_number) if str(value).strip()))
    visible_models = [value for value in identifiers if _model_tokens(value)]
    core = _strip_pack_quantities(_title_without_identity(title, aliases, identifiers))
    core = re.sub(r"Amazon(?:\.co\.jp)?限定|アマゾン限定|送料無料|国内正規品|正規品", " ", core, flags=re.IGNORECASE)
    words = [word for word in re.split(r"\s+", core) if word]
    name_query = " ".join([maker, *words[:6]]).strip()
    compact_name = " ".join([maker, *words[:3], *words[-2:]]).strip()
    proposals = []
    if visible_models:
        proposals.append(" ".join([maker, *visible_models]).strip())
        proposals.append(" ".join(visible_models))
    proposals.extend([name_query, compact_name])
    if len(aliases) > 1 and words:
        proposals.append(" ".join([aliases[1], *words[:4], *words[-1:]]))
    result, seen = [], set()
    for query in proposals:
        query = " ".join(dict.fromkeys(query.split())).encode("utf-8")[:128].decode("utf-8", errors="ignore").strip()
        if query and query not in seen:
            seen.add(query)
            result.append(query)
    return result[:MAX_TEXT_SEARCHES]


def _is_high_confidence_text_match(
    item: dict[str, Any],
    *,
    title: str,
    brand: str,
    manufacturer: str,
    model: str,
    part_number: str,
    ignore_pack_count: bool = False,
) -> bool:
    """Require enough shared evidence that a title search cannot pass lookalikes."""
    candidate = _item_product_text(item)
    candidate_name = str(item.get("itemName") or "")
    reference_name = title
    if ignore_pack_count:
        candidate_name = _strip_pack_quantities(candidate_name)
        reference_name = _strip_pack_quantities(reference_name)
    candidate_title = _normalise_product_text(candidate_name)
    reference_title = _normalise_product_text(reference_name)
    if not candidate or not reference_title:
        return False

    candidate_models = _model_tokens(candidate_name)
    declared_models = _model_tokens(model, part_number)
    exact_model = bool(declared_models.intersection(candidate_models))
    if declared_models and candidate_models and not exact_model:
        return False
    model_matches = _model_tokens(model, part_number, title).intersection(candidate_models)
    brand_values = {
        _normalise_product_text(value)
        for value in _maker_aliases(brand, manufacturer)
        if len(_normalise_product_text(value)) >= 2
    }
    brand_match = any(value in candidate for value in brand_values)
    variants = _variant_groups(title)
    if ignore_pack_count:
        variants.pop("count", None)
    candidate_variants = _variant_groups(item.get("itemName"))
    # Without exact JAN evidence, an explicit complexion shade must be proven
    # in the candidate title, not merely inferred from a similar product name.
    reference_shades = _skin_shades(title)
    if reference_shades and _skin_shades(item.get("itemName")) != reference_shades:
        return False
    reference_protection, candidate_protection = _sun_protection(title), _sun_protection(item.get("itemName"))
    if any(reference_protection[key] != candidate_protection[key]
           for key in reference_protection.keys() & candidate_protection.keys()):
        return False
    # Captions often enumerate every SKU capacity; only the product title can
    # support the fallback's exact capacity/count check.
    variants_match = all(candidate_variants.get(group, {Decimal(1)} if group == "count" else set()) == values
                         or (exact_model and group == "bread_capacity" and group not in candidate_variants)
                         for group, values in variants.items())
    required_terms = _distinctive_terms(title)
    if required_terms and not required_terms.issubset(_distinctive_terms(item.get("itemName"))):
        return False
    similarity = SequenceMatcher(None, reference_title, candidate_title).ratio()
    aliases = _maker_aliases(brand, manufacturer)
    ref_core = _normalise_product_text(_title_without_identity(reference_name, aliases, (model, part_number)))
    cand_core = _normalise_product_text(_title_without_identity(candidate_name, aliases, (model, part_number)))
    core_similarity = SequenceMatcher(None, ref_core, cand_core).ratio() if len(ref_core) >= 4 else 0.0

    # A model/part number is an exact product key.  Otherwise require the
    # maker, all stated capacity/count variants, and a close title match.
    if model_matches and (brand_match or similarity >= 0.78):
        return variants_match
    threshold = 0.88 if (str(model or "").strip() or str(part_number or "").strip()) and not exact_model else 0.78
    return brand_match and variants_match and len(ref_core) >= 4 and max(similarity, core_similarity) >= threshold


def rakuten_marketplace_evidence(
    *,
    jan_code: str,
    title: str,
    brand: str = "",
    manufacturer: str = "",
    model: str = "",
    part_number: str = "",
    minimum_shops: int = MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION,
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Confirm independent Rakuten shops for a forced-listing product.

    Exact JAN is preferred.  If merchants omit JANs, a high-confidence title
    match may also pass, but only after deduplicating by shop identity.  This
    deliberately does not accept a broad name-only hit. Sale-pack counts are
    not product-identity requirements here, but remain price requirements.
    """
    minimum_shops = max(1, int(minimum_shops))
    attempts: list[dict[str, Any]] = []
    jan = re.sub(r"\D", "", str(jan_code or ""))
    jan_items = _search_items(jan, timeout, postage_included=False) if jan else []
    if jan_items is None:
        return None
    exact_items, jan_rejected = [], Counter()
    for item in jan_items:
        if not _item_mentions_exact_jan(item, jan):
            jan_rejected["jan_not_attested"] += 1
        else:
            reason = _variant_rejection_reason(item, title, ignore_pack_count=True, ignore_postage=True)
            if reason:
                jan_rejected[reason] += 1
            else:
                exact_items.append(item)
    exact_shops = _shop_names(exact_items)
    if jan:
        attempts.append({"kind": "jan", "query": jan, "raw_result_count": len(jan_items),
                         "matched_item_count": len(exact_items), "matched_shop_count": len(exact_shops),
                         "postage_included_only": False,
                         "jan_url_match_count": sum("itemUrl_path" in _jan_evidence_sources(item, jan) for item in exact_items),
                         "rejected_counts": dict(jan_rejected)})
    if len(exact_shops) >= minimum_shops:
        return {
            "accepted": True,
            "source": "jan_exact",
            "minimum_shops": minimum_shops,
            "pack_count_required": False,
            "postage_included_required": False,
            "jan_exact_shop_count": len(exact_shops),
            "text_match_shop_count": 0,
            "confirmed_shop_count": len(exact_shops),
            "query": jan,
            "shop_names": exact_shops[:minimum_shops],
            "search_attempts": attempts,
            **_reference_price_summary(exact_items, title),
        }

    queries = _keyword_queries(
        title=title,
        brand=brand,
        manufacturer=manufacturer,
        model=model,
        part_number=part_number,
    )
    # A fallback search without either a product title or an identifying maker
    # cannot prove that several shops sell the same product.
    if not queries or not _normalise_product_text(title):
        return {
            "accepted": False,
            "source": "insufficient_product_identity",
            "minimum_shops": minimum_shops,
            "pack_count_required": False,
            "postage_included_required": False,
            "jan_exact_shop_count": len(exact_shops),
            "text_match_shop_count": 0,
            "confirmed_shop_count": len(exact_shops),
            "query": "",
            "shop_names": exact_shops[:minimum_shops],
            "search_attempts": attempts,
            **_reference_price_summary(exact_items, title),
        }

    matching_text_items = []
    query = ""
    for query in queries:
        text_items = _search_items(query, timeout, postage_included=False)
        if text_items is None:
            return None
        matched, matched_jan, matched_text, rejected = [], [], [], Counter()
        for item in text_items:
            reason = _variant_rejection_reason(item, title, ignore_pack_count=True, ignore_postage=True)
            if reason:
                rejected[reason] += 1
            elif jan and _item_mentions_exact_jan(item, jan):
                matched.append(item)
                matched_jan.append(item)
            elif not _is_high_confidence_text_match(item, title=title, brand=brand,
                    manufacturer=manufacturer, model=model, part_number=part_number, ignore_pack_count=True):
                rejected["identity_not_proven"] += 1
            else:
                matched.append(item)
                matched_text.append(item)
        exact_items.extend(matched_jan)
        matching_text_items.extend(matched_text)
        attempts.append({"kind": "text", "query": query, "raw_result_count": len(text_items),
                         "matched_item_count": len(matched), "matched_shop_count": len(_shop_names(matched)),
                         "postage_included_only": False,
                         "jan_url_match_count": sum("itemUrl_path" in _jan_evidence_sources(item, jan) for item in matched_jan),
                         "rejected_counts": dict(rejected)})
        if len(_shop_names([*exact_items, *matching_text_items])) >= minimum_shops:
            break
    exact_shops = _shop_names(exact_items)
    text_shops = _shop_names(matching_text_items)
    confirmed_shops = _shop_names([*exact_items, *matching_text_items])
    return {
        "accepted": len(confirmed_shops) >= minimum_shops,
        "source": "jan_and_text_high_confidence" if exact_shops and text_shops else ("jan_exact" if exact_shops else "text_high_confidence"),
        "minimum_shops": minimum_shops,
        "pack_count_required": False,
        "postage_included_required": False,
        "jan_exact_shop_count": len(exact_shops),
        "text_match_shop_count": len(text_shops),
        "confirmed_shop_count": len(confirmed_shops),
        "query": query,
        "shop_names": confirmed_shops[:minimum_shops],
        "search_attempts": attempts,
        **_reference_price_summary([*exact_items, *matching_text_items], title),
    }


def is_cosmetics_category(category_tree: list[dict[str, Any]] | None) -> bool:
    """Whether Keepa classifies the item in a beauty/cosmetics category."""
    for category in category_tree or []:
        name = str(category.get("name") or "").casefold()
        if any(marker.casefold() in name for marker in COSMETICS_CATEGORY_MARKERS):
            return True
    return False


def has_sensitive_forbidden_word(matches: list[dict[str, Any]], *, cosmetics_category: bool = False) -> bool:
    """Return true for hard-guard matches, with a cosmetics-only alcohol exception.

    ``アルコール`` and ``ノンアルコール`` may use the same-JAN Rakuten
    marketplace confirmation path only for cosmetics.  Medical, efficacy,
    adult, and sterilisation-related words remain hard guards for every genre.
    """
    for item in matches:
        word = str(item.get("word") or "")
        if word == ALCOHOL_WORD:
            if cosmetics_category:
                continue
            return True
        if any(marker in word for marker in SENSITIVE_MARKERS):
            return True
    return False


def rakuten_listing_count_for_jan(jan_code: str, timeout: float = 15.0) -> int | None:
    """Return active, postage-included Rakuten search hits for a JAN.

    Acquisition failures raise ``RakutenSearchError`` instead of being
    mistaken for zero matches. A single result is not
    sufficient resale evidence for a blocked word: callers must explicitly
    apply ``MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION``.
    """
    jan = re.sub(r"\D", "", str(jan_code or ""))
    if not jan:
        return 0
    return sum(1 for item in _search_items(jan, timeout) if _item_mentions_exact_jan(item, jan))
