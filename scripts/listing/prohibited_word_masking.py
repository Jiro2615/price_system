from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


MASK_CHAR = "\uFFF0"
DEFAULT_ALLOWED_PHRASE_SOURCE = "reference/legacy_listing/allowed_phrases_rakuten.json"
COMPLIANCE_IGNORED_CHARACTERS_RE = re.compile(r"[\s\u200b-\u200d\ufeff\-‐‑‒–—―ーｰ・･./／,，、()（）\[\]［］]", re.UNICODE)


def normalize_compliance_text(value: str) -> str:
    """Normalize presentation-only variants before compliance word matching.

    This is intentionally used for detection only; it never rewrites the
    listing text to evade a prohibited-expression check.
    """
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return COMPLIANCE_IGNORED_CHARACTERS_RE.sub("", normalized)


def load_allowed_phrase_rules(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize_allowed_phrase_payload(payload)


def normalize_allowed_phrase_payload(payload: object) -> dict[str, Any]:
    empty = {
        "meta": {},
        "rules": {},
        "separate_checks": {},
        "rule_count": 0,
        "allowed_phrase_count": 0,
        "separate_check_count": 0,
    }
    if isinstance(payload, dict) and isinstance(payload.get("rules"), list):
        normalized: dict[str, list[str]] = {}
        separate_checks: dict[str, list[dict[str, Any]]] = {}
        for item in payload["rules"]:
            if not isinstance(item, dict):
                continue
            forbidden_word = str(item.get("forbidden_word") or "").strip()
            phrases = item.get("allowed_phrases") or []
            if forbidden_word:
                normalized[forbidden_word] = [str(phrase).strip() for phrase in phrases if str(phrase).strip()]
            for separate_check in item.get("separate_check_phrases") or []:
                if not isinstance(separate_check, dict):
                    continue
                phrase = str(separate_check.get("phrase") or "").strip()
                required_checks = [
                    str(check).strip()
                    for check in (separate_check.get("required_checks") or [])
                    if str(check).strip()
                ]
                if not phrase or not required_checks:
                    continue
                separate_checks.setdefault(phrase, []).append(
                    {
                        "phrase": phrase,
                        "forbidden_word": forbidden_word,
                        "required_checks": required_checks,
                    }
                )
        rules = _dedupe_and_sort_rules(normalized)
        return {
            "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
            "rules": rules,
            "separate_checks": separate_checks,
            "rule_count": len(rules),
            "allowed_phrase_count": sum(len(items) for items in rules.values()),
            "separate_check_count": sum(len(items) for items in separate_checks.values()),
        }

    if isinstance(payload, dict):
        normalized = {
            str(forbidden_word).strip(): [str(phrase).strip() for phrase in (phrases or []) if str(phrase).strip()]
            for forbidden_word, phrases in payload.items()
            if str(forbidden_word).strip()
        }
        rules = _dedupe_and_sort_rules(normalized)
        return {
            "meta": {},
            "rules": rules,
            "separate_checks": {},
            "rule_count": len(rules),
            "allowed_phrase_count": sum(len(items) for items in rules.values()),
            "separate_check_count": 0,
        }

    return empty


def normalize_allowed_phrase_rules(payload: object) -> dict[str, list[str]]:
    return normalize_allowed_phrase_payload(payload)["rules"]


def _dedupe_and_sort_rules(rules: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for forbidden_word, phrases in rules.items():
        deduped: list[str] = []
        seen: set[str] = set()
        for phrase in sorted(phrases, key=lambda item: (-len(item), item)):
            if phrase not in seen:
                deduped.append(phrase)
                seen.add(phrase)
        normalized[forbidden_word] = deduped
    return normalized


def is_spacing_only_replacement(source: str, target: str) -> bool:
    if not source or not target or source == target:
        return False
    return "".join(source.split()) == "".join(target.split())


def split_replacement_rules(
    replacements: list[tuple[str, str]],
    forbidden_words: list[str],
) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    cleanup_replacements: list[tuple[str, str]] = []
    spacing_rules: list[dict[str, Any]] = []

    for source, target in replacements:
        if is_spacing_only_replacement(source, target):
            spacing_rules.append(
                {
                    "source": source,
                    "target": target,
                    "suspected_forbidden_words": _broken_forbidden_words(source, target, forbidden_words),
                    "source_type": "replacelist_rakuten",
                }
            )
        else:
            cleanup_replacements.append((source, target))

    return cleanup_replacements, spacing_rules


def _broken_forbidden_words(source: str, target: str, forbidden_words: list[str]) -> list[str]:
    compact_target = "".join(target.split())
    broken: list[str] = []
    for word in forbidden_words:
        if word and word in source and word in compact_target and word not in target:
            broken.append(word)
    broken.sort(key=lambda item: (-len(item), item))
    return broken


def build_allowed_phrase_matches(
    text: str,
    field: str,
    allowed_phrase_rules: dict[str, list[str]],
    *,
    source: str = DEFAULT_ALLOWED_PHRASE_SOURCE,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for forbidden_word, phrases in allowed_phrase_rules.items():
        for phrase in phrases:
            start = 0
            while True:
                index = text.find(phrase, start)
                if index < 0:
                    break
                end = index + len(phrase)
                candidates.append(
                    {
                        "forbidden_word": forbidden_word,
                        "allowed_phrase": phrase,
                        "field": field,
                        "start": index,
                        "end": end,
                        "context": _build_context(text, index, end),
                        "source": source,
                    }
                )
                start = index + 1

    accepted: list[dict[str, Any]] = []
    occupied = [False] * len(text)
    for candidate in sorted(
        candidates,
        key=lambda item: (-(item["end"] - item["start"]), item["start"], item["allowed_phrase"]),
    ):
        if any(occupied[position] for position in range(candidate["start"], candidate["end"])):
            continue
        for position in range(candidate["start"], candidate["end"]):
            occupied[position] = True
        accepted.append(candidate)

    return sorted(accepted, key=lambda item: (item["start"], item["end"], item["allowed_phrase"]))


def mask_text_with_allowed_phrases(text: str, allowed_phrase_matches: list[dict[str, Any]]) -> str:
    if not allowed_phrase_matches:
        return text

    masked_chars = list(text)
    for match in allowed_phrase_matches:
        for index in range(match["start"], match["end"]):
            if 0 <= index < len(masked_chars):
                masked_chars[index] = MASK_CHAR
    return "".join(masked_chars)


def find_masked_forbidden_word_matches(
    text: str,
    field: str,
    forbidden_words: list[str],
    allowed_phrase_rules: dict[str, list[str]],
    *,
    source: str = DEFAULT_ALLOWED_PHRASE_SOURCE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed_phrase_matches = build_allowed_phrase_matches(text, field, allowed_phrase_rules, source=source)
    masked_text = mask_text_with_allowed_phrases(text, allowed_phrase_matches)

    forbidden_matches: list[dict[str, Any]] = []
    for word in forbidden_words:
        if not word:
            continue
        start = 0
        while True:
            index = masked_text.find(word, start)
            if index < 0:
                break
            end = index + len(word)
            forbidden_matches.append(
                {
                    "word": word,
                    "field": field,
                    "start": index,
                    "end": end,
                    "context": _build_context(text, index, end),
                }
            )
            start = index + 1

    # Detect deliberately split or full/half-width variants too.  Exceptions
    # are applied only to the original exact text above; an obfuscated variant
    # remains blocked for review rather than being silently permitted.
    normalized_text = normalize_compliance_text(text)
    for word in forbidden_words:
        # Exact appearances were already evaluated with allowed-phrase masking.
        if word in text:
            continue
        normalized_word = normalize_compliance_text(word)
        if not normalized_word or normalized_word not in normalized_text:
            continue
        if any(match["word"] == word for match in forbidden_matches):
            continue
        forbidden_matches.append(
            {
                "word": word,
                "field": field,
                "start": None,
                "end": None,
                "context": text[:160],
                "normalized_match": True,
                "normalized_word": normalized_word,
            }
        )

    forbidden_matches.sort(key=lambda item: (item["start"] is None, item["start"] or -1, item["end"] or -1, item["word"]))
    return allowed_phrase_matches, forbidden_matches


def detect_prohibited_word_issues(
    fields: dict[str, str],
    forbidden_words: list[str],
    allowed_phrase_rules: dict[str, list[str]],
    *,
    source: str = DEFAULT_ALLOWED_PHRASE_SOURCE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed_phrase_matches: list[dict[str, Any]] = []
    forbidden_matches: list[dict[str, Any]] = []

    for field, text in fields.items():
        original = str(text or "")
        if not original:
            continue
        field_allowed, field_forbidden = find_masked_forbidden_word_matches(
            original,
            field,
            forbidden_words,
            allowed_phrase_rules,
            source=source,
        )
        allowed_phrase_matches.extend(field_allowed)
        forbidden_matches.extend(field_forbidden)

    return allowed_phrase_matches, forbidden_matches


def build_separate_check_matches(
    allowed_phrase_matches: list[dict[str, Any]],
    separate_check_rules: dict[str, list[dict[str, Any]]],
    *,
    source: str = DEFAULT_ALLOWED_PHRASE_SOURCE,
) -> tuple[list[str], list[dict[str, Any]]]:
    required_checks: list[str] = []
    matched_phrases: list[dict[str, Any]] = []
    seen_required_checks: set[str] = set()

    for match in allowed_phrase_matches:
        phrase = str(match.get("allowed_phrase") or "").strip()
        if not phrase:
            continue
        for rule in separate_check_rules.get(phrase, []):
            checks = [str(item).strip() for item in rule.get("required_checks", []) if str(item).strip()]
            for check in checks:
                if check not in seen_required_checks:
                    seen_required_checks.add(check)
                    required_checks.append(check)
            matched_phrases.append(
                {
                    "phrase": phrase,
                    "forbidden_word": rule.get("forbidden_word") or match.get("forbidden_word"),
                    "field": match.get("field"),
                    "start": match.get("start"),
                    "end": match.get("end"),
                    "context": match.get("context"),
                    "required_checks": checks,
                    "source": source,
                }
            )

    matched_phrases.sort(key=lambda item: (str(item.get("field") or ""), int(item.get("start") or 0), str(item.get("phrase") or "")))
    return required_checks, matched_phrases


def analyze_prohibited_word_issues(
    fields: dict[str, str],
    forbidden_words: list[str],
    allowed_phrase_rules: dict[str, list[str]],
    *,
    separate_check_rules: dict[str, list[dict[str, Any]]] | None = None,
    source: str = DEFAULT_ALLOWED_PHRASE_SOURCE,
) -> dict[str, Any]:
    allowed_phrase_matches, forbidden_matches = detect_prohibited_word_issues(
        fields,
        forbidden_words,
        allowed_phrase_rules,
        source=source,
    )
    required_separate_checks, matched_separate_check_phrases = build_separate_check_matches(
        allowed_phrase_matches,
        separate_check_rules or {},
        source=source,
    )
    return {
        "allowed_phrase_matches": allowed_phrase_matches,
        "matched_forbidden_words": forbidden_matches,
        "required_separate_checks": required_separate_checks,
        "matched_separate_check_phrases": matched_separate_check_phrases,
    }


def detect_legacy_spacing_reviews(
    fields: dict[str, str],
    spacing_rules: list[dict[str, Any]],
    allowed_phrase_rules: dict[str, list[str]],
) -> list[dict[str, Any]]:
    allowed_phrases = {
        phrase
        for phrases in allowed_phrase_rules.values()
        for phrase in phrases
        if phrase
    }
    reviews: list[dict[str, Any]] = []

    for field, text in fields.items():
        original = str(text or "")
        if not original:
            continue
        for rule in spacing_rules:
            source = str(rule.get("source") or "")
            target = str(rule.get("target") or "")
            if not source or not target or source not in original:
                continue
            if source in allowed_phrases:
                continue
            reviews.append(
                {
                    "field": field,
                    "original_text": original,
                    "legacy_replaced_text": original.replace(source, target),
                    "matched_replacement_rule": {
                        "source": source,
                        "target": target,
                    },
                    "suspected_forbidden_word": _first_value(rule.get("suspected_forbidden_words")),
                    "migration_status": "needs_review",
                    "source": "replacelist_rakuten.txt",
                }
            )

    reviews.sort(
        key=lambda item: (
            item["field"],
            item["matched_replacement_rule"]["source"],
            item["matched_replacement_rule"]["target"],
        )
    )
    return reviews


def _first_value(value: object) -> str | None:
    if isinstance(value, list) and value:
        first = str(value[0] or "").strip()
        return first or None
    return None


def _build_context(text: str, start: int, end: int, radius: int = 12) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right]
