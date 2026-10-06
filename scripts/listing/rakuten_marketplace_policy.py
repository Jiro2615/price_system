from __future__ import annotations

import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from dotenv import load_dotenv
from scripts.listing.rakuten_search_client import search_items


ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
MIN_SAME_JAN_LISTINGS_FOR_PROHIBITED_WORD_EXCEPTION = 5
SENSITIVE_MARKERS = (
    "医療", "医薬", "薬", "コンドーム", "性", "育毛", "殺菌", "除菌", "治療", "効能", "効果",
    "治癒", "予防", "疲労回復", "老化防止", "血液サラサラ", "バストアップ", "デトックス",
    "脂肪燃焼", "代謝促進", "病気", "成人病", "便秘", "精力剤", "性的機能",
)
ALCOHOL_WORD = "アルコール"
COSMETICS_CATEGORY_MARKERS = ("ビューティー", "beauty", "化粧品", "cosmetics")


def _item_mentions_exact_jan(item: object, jan: str) -> bool:
    """Whether a Rakuten search result explicitly carries the requested JAN."""
    if not isinstance(item, dict):
        return False
    text = unicodedata.normalize("NFKC", " ".join(str(item.get(key) or "") for key in ("itemName", "itemCaption", "itemCode")))
    return bool(jan and re.search(r"(?<!\d)" + re.escape(jan) + r"(?!\d)", text))


def _search_items(keyword: str, timeout: float) -> list[dict[str, Any]] | None:
    """API failures are acquisition errors, never an empty-product result."""
    return search_items(keyword, timeout)


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
            if len(compact) >= 4:
                tokens.add(compact)
    return tokens


def _variant_tokens(value: object) -> set[str]:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold().replace(" ", "")
    return {
        re.sub(r"\s+", "", token)
        for token in re.findall(r"\d+(?:\.\d+)?(?:ml|l|g|kg|個|本|枚|包|袋|組|セット|pack)", normalized)
    }


def _variant_groups(value: object) -> dict[str, set[Decimal]]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    groups: dict[str, set[Decimal]] = {}
    factors = {"ml": ("volume", 1), "l": ("volume", 1000), "mg": ("weight", Decimal("0.001")),
               "g": ("weight", 1), "kg": ("weight", 1000)}
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(ml|mg|kg|gb|tb|mb|l|g|個|本|枚|包|袋|組|セット|pack|pcs)(?![a-z])", text):
        group, factor = factors.get(unit, (unit if unit in {"gb", "tb", "mb"} else "count", 1))
        groups.setdefault(group, set()).add(Decimal(number) * factor)
    return groups


def _candidate_matches_variant(item: dict[str, Any], title: str) -> bool:
    try:
        if "availability" in item and int(item["availability"]) != 1:
            return False
        if "postageFlag" in item and int(item["postageFlag"]) != 0:
            return False
    except (ValueError, TypeError):
        return False
    if any(word in str(item.get("itemName") or "") for word in ("中古", "整備済", "電子書籍")):
        return False
    reference, candidate = _variant_groups(title), _variant_groups(item.get("itemName"))
    # Known conflicting capacities/counts cannot be rescued by a JAN in the
    # caption: the page may be a multipack or list several different SKUs.
    for group, values in candidate.items():
        if group != "count" and group not in reference and any(key != "count" for key in reference):
            return False
        if group in reference and values != reference[group]:
            return False
    expected_count, actual_count = reference.get("count", {Decimal(1)}), candidate.get("count", {Decimal(1)})
    return expected_count == actual_count


def _reference_price_summary(items: list[dict[str, Any]], title: str) -> dict[str, Any]:
    candidates = []
    excluded_ambiguous = 0
    excluded_unknown_variant = 0
    reference_variants = _variant_groups(title)
    seen_items: set[str] = set()
    for item in items:
        identity = _shop_identity(item) + ":" + (str(item.get("itemCode") or item.get("itemUrl") or "") or str(item.get("itemName") or ""))
        if identity in seen_items:
            continue
        seen_items.add(identity)
        candidate_variants = _variant_groups(item.get("itemName"))
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


def _is_high_confidence_text_match(
    item: dict[str, Any],
    *,
    title: str,
    brand: str,
    manufacturer: str,
    model: str,
    part_number: str,
) -> bool:
    """Require enough shared evidence that a title search cannot pass lookalikes."""
    candidate = _item_product_text(item)
    candidate_title = _normalise_product_text(item.get("itemName"))
    reference_title = _normalise_product_text(title)
    if not candidate or not reference_title:
        return False

    candidate_models = _model_tokens(item.get("itemName"))
    declared_models = _model_tokens(model, part_number)
    if declared_models and not declared_models.intersection(candidate_models):
        return False
    model_matches = _model_tokens(model, part_number, title).intersection(candidate_models)
    brand_values = {
        _normalise_product_text(value)
        for value in (brand, manufacturer)
        if len(_normalise_product_text(value)) >= 2
    }
    brand_match = any(value in candidate for value in brand_values)
    variants = _variant_groups(title)
    candidate_variants = _variant_groups(item.get("itemName"))
    # Captions often enumerate every SKU capacity; only the product title can
    # support the fallback's exact capacity/count check.
    variants_match = all(candidate_variants.get(group, {Decimal(1)} if group == "count" else set()) == values
                         for group, values in variants.items())
    similarity = SequenceMatcher(None, reference_title, candidate_title).ratio()

    # A model/part number is an exact product key.  Otherwise require the
    # maker, all stated capacity/count variants, and a close title match.
    if model_matches and (brand_match or similarity >= 0.78):
        return variants_match
    return brand_match and variants_match and similarity >= 0.78


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
    deliberately does not accept a broad name-only hit.
    """
    minimum_shops = max(1, int(minimum_shops))
    jan = re.sub(r"\D", "", str(jan_code or ""))
    jan_items = _search_items(jan, timeout) if jan else []
    if jan_items is None:
        return None
    exact_items = [item for item in jan_items if _item_mentions_exact_jan(item, jan)
                   and _candidate_matches_variant(item, title)] if jan else []
    exact_shops = _shop_names(exact_items)
    if len(exact_shops) >= minimum_shops:
        return {
            "accepted": True,
            "source": "jan_exact",
            "minimum_shops": minimum_shops,
            "jan_exact_shop_count": len(exact_shops),
            "text_match_shop_count": 0,
            "confirmed_shop_count": len(exact_shops),
            "query": jan,
            "shop_names": exact_shops[:minimum_shops],
            **_reference_price_summary(exact_items, title),
        }

    query = _keyword_query(
        title=title,
        brand=brand,
        manufacturer=manufacturer,
        model=model,
        part_number=part_number,
    )
    # A fallback search without either a product title or an identifying maker
    # cannot prove that several shops sell the same product.
    if not query or not _normalise_product_text(title):
        return {
            "accepted": False,
            "source": "insufficient_product_identity",
            "minimum_shops": minimum_shops,
            "jan_exact_shop_count": len(exact_shops),
            "text_match_shop_count": 0,
            "confirmed_shop_count": len(exact_shops),
            "query": query,
            "shop_names": exact_shops[:minimum_shops],
            **_reference_price_summary(exact_items, title),
        }

    text_items = _search_items(query, timeout)
    if text_items is None:
        return None
    matching_text_items = [
        item
        for item in text_items
        if _is_high_confidence_text_match(
            item,
            title=title,
            brand=brand,
            manufacturer=manufacturer,
            model=model,
            part_number=part_number,
        )
        and _candidate_matches_variant(item, title)
    ]
    text_shops = _shop_names(matching_text_items)
    confirmed_shops = _shop_names([*exact_items, *matching_text_items])
    return {
        "accepted": len(confirmed_shops) >= minimum_shops,
        "source": "text_high_confidence" if not exact_shops else "jan_and_text_high_confidence",
        "minimum_shops": minimum_shops,
        "jan_exact_shop_count": len(exact_shops),
        "text_match_shop_count": len(text_shops),
        "confirmed_shop_count": len(confirmed_shops),
        "query": query,
        "shop_names": confirmed_shops[:minimum_shops],
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
