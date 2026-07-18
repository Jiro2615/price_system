from __future__ import annotations

import re
from typing import Any

from scripts.listing.models import AmazonCheckResult, KeepaProductData, MasterData


TOKEN_RE = re.compile(r"[A-Za-z0-9#.+-]+|[ぁ-んァ-ヶ一-龠々ー]+")

DOMAIN_KEYWORD_EXPANSIONS = {
    "コバエ": {"虫除け", "殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "バルサン": {"虫除け", "殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "殺虫": {"殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "虫類": {"殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "カイガラムシ": {"園芸薬剤", "植物活性剤", "殺虫剤", "花・ガーデン・DIY"},
    "エアゾール": {"殺虫スプレー", "スプレー", "虫除け・殺虫剤"},
    "園芸": {"園芸薬剤", "植物活性剤", "花・ガーデン・DIY"},
}


def _build_query_text(
    amazon_result: AmazonCheckResult | None,
    keepa_result: KeepaProductData | None,
) -> str:
    if keepa_result is None:
        return "" if amazon_result is None else amazon_result.title
    parts = [
        "" if amazon_result is None else amazon_result.title,
        keepa_result.title,
        keepa_result.brand,
        keepa_result.manufacturer,
        keepa_result.model,
        keepa_result.part_number,
        keepa_result.color,
        keepa_result.style,
        keepa_result.size,
        keepa_result.description,
        keepa_result.scent,
    ]
    parts.extend(item for item in keepa_result.features if item)
    for node in keepa_result.category_tree:
        if isinstance(node, dict):
            parts.append(str(node.get("name") or ""))
    return "\n".join(part for part in parts if part)


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in TOKEN_RE.finditer(str(text or "").lower()):
        token = match.group(0).strip()
        if len(token) >= 2:
            tokens.add(token)
        if re.fullmatch(r"[ぁ-んァ-ヶ一-龠々ー]+", token):
            max_len = min(8, len(token))
            for size in range(3, max_len + 1):
                for index in range(0, len(token) - size + 1):
                    tokens.add(token[index : index + size])
    return tokens


def _extract_priority_terms(text: str) -> set[str]:
    priority_terms: set[str] = set()
    normalized = str(text or "")
    for source, expansions in DOMAIN_KEYWORD_EXPANSIONS.items():
        if source in normalized:
            priority_terms.add(source)
            priority_terms.update(expansions)
    return priority_terms


def _select_from_candidates(candidates: list[dict[str, Any]], priority_terms: set[str]) -> dict[str, Any] | None:
    if not candidates:
        return None

    def find_by_leaf(needle: str) -> dict[str, Any] | None:
        for candidate in candidates:
            leaf_name = str(candidate.get("genre_path") or "").split(">")[-1]
            if needle in leaf_name:
                return candidate
        return None

    def find_by_leaf_without_country(needle: str) -> dict[str, Any] | None:
        for candidate in candidates:
            leaf_name = str(candidate.get("genre_path") or "").split(">")[-1]
            required = set(candidate.get("required_attributes") or [])
            if needle in leaf_name and "原産国／製造国" not in required:
                return candidate
        return None

    selected = None
    confidence = "low"
    reason = "ジャンル一覧のスコア最上位を仮ジャンルとして選択"
    if {"カイガラムシ", "園芸"} & priority_terms:
        selected = find_by_leaf("殺虫剤")
        confidence = "medium"
        reason = "園芸・カイガラムシ系の語から園芸薬剤の殺虫剤ジャンルを仮選択"
    elif {"コバエ", "バルサン"} & priority_terms:
        selected = find_by_leaf_without_country("殺虫剤") or find_by_leaf("虫除け器具") or find_by_leaf("虫除け芳香剤")
        confidence = "low"
        reason = "コバエ・バルサン系の語から、登録を止めにくい近似ジャンルを仮選択"
    elif {"エアゾール", "スプレー"} & priority_terms:
        selected = find_by_leaf("殺虫スプレー") or find_by_leaf("虫除けスプレー")
        confidence = "medium"
        reason = "エアゾール・スプレー系の語からスプレー系ジャンルを仮選択"

    selected = selected or candidates[0]
    return {
        "genre_id": selected.get("genre_id"),
        "genre_path": selected.get("genre_path"),
        "required_attributes": selected.get("required_attributes", []),
        "confidence": confidence,
        "selection_source": "rakuten_genre_path_similarity",
        "reason": reason,
        "review_required": True,
    }


def suggest_provisional_genre(
    *,
    amazon_result: AmazonCheckResult | None,
    keepa_result: KeepaProductData | None,
    master_data: MasterData,
) -> dict[str, Any] | None:
    if keepa_result is None or not master_data.genre_paths:
        return None
    query_text = _build_query_text(amazon_result, keepa_result)
    query_tokens = _tokenize(query_text)
    priority_terms = _extract_priority_terms(query_text)
    candidates: list[dict[str, Any]] = []
    for genre_id, genre_path in master_data.genre_paths.items():
        path_tokens = _tokenize(genre_path)
        priority_overlap = {term for term in priority_terms if term and term in genre_path}
        overlap = {token for token in (query_tokens & path_tokens) if len(token) >= 3}
        if not priority_overlap and not overlap:
            continue
        score = sum(min(len(token), 12) * 2.0 for token in overlap)
        score += sum(80.0 + min(len(term), 12) * 5.0 for term in priority_overlap)
        leaf_name = genre_path.split(">")[-1] if ">" in genre_path else genre_path
        if any(term in leaf_name for term in priority_overlap):
            score += 60.0
        candidates.append(
            {
                "genre_id": int(genre_id),
                "score": round(score, 3),
                "genre_path": genre_path,
                "required_attributes": master_data.attribute_definitions.get(int(genre_id), []),
                "matched_terms": sorted(overlap | priority_overlap, key=lambda item: (-len(item), item))[:20],
            }
        )
    candidates.sort(key=lambda item: (-float(item["score"]), int(item["genre_id"])))
    selected = _select_from_candidates(candidates, priority_terms)
    if selected:
        selected["keepa_category_id"] = keepa_result.category_id
        selected["top_candidates"] = candidates[:5]
    return selected
