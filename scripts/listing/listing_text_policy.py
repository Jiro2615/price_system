"""Listing-specific brand boundaries and advertising-expression screening.

This is an expression filter, not proof of approval, efficacy or sale eligibility.
Do not rewrite product copy or manufacture substantiation to pass this filter.
"""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

from scripts.listing.prohibited_word_masking import analyze_prohibited_word_issues


POLICY_VERSION = "listing_text_20260925"
# Only the reviewed legacy short terms change meaning. Other master entries,
# including official-shop claims and regulated-product terms, stay in force.
WORD_OR_BRAND_TERMS = frozenset({"OU", "ＯＲ", "イラ", "スリー", "スキン", "スカルプ"})
CONTEXTUAL_CLAIM_TERMS = frozenset({
    "治癒", "治す", "予防", "防ぐ", "改善", "効能", "効果", "疲労回復", "老化防止",
    "血液サラサラ", "バストアップ", "デトックス", "脂肪燃焼", "代謝促進", "精力剤", "性的機能",
})


def plain_text(value: str) -> str:
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    value = unicodedata.normalize("NFKC", html.unescape(value)).casefold()
    # Keep spaces, punctuation and the long-vowel mark: they determine whether
    # a word is standalone. Removing them confuses スリー with スリム.
    return re.sub(r"[\u200b-\u200d\ufeff]", "", value)


def claim_text(value: str) -> str:
    # Detect presentation-only splitting without joining separate sentences.
    # Unlike the old keyword normalizer, keep Japanese long-vowel marks intact.
    return re.sub(r"[^\S\n]|[・･\-‐‑‒–—―./,、()\[\]]", "", plain_text(value))


def whole_word_pattern(word: str) -> re.Pattern[str]:
    # Japanese has no spaces between many words. Be conservative: a matching
    # substring inside another Japanese/Latin word is not a standalone token.
    return re.compile(r"(?<![\wー])" + re.escape(plain_text(word).strip()) + r"(?![\wー])")


def _match_record(word: str, field: str, text: str, match: re.Match[str], kind: str) -> dict[str, Any]:
    return {
        "word": word, "field": field, "start": match.start(), "end": match.end(),
        "context": text[max(0, match.start() - 35):match.end() + 60],
        "rule_kind": kind, "policy_version": POLICY_VERSION,
        "coordinate_space": "normalized_plain_text",
    }


def brand_word_matches(fields: dict[str, str], words: list[str], brand: str) -> list[dict[str, Any]]:
    matches = []
    for word in words:
        pattern = whole_word_pattern(word)
        for field, value in {**fields, "brand": brand}.items():
            text = plain_text(value)
            for match in pattern.finditer(text):
                matches.append(_match_record(word, field, text, match,
                                             "brand" if field == "brand" else "whole_word"))
    return matches


# Generic nouns (効果/効能) and verbs (防ぐ/改善) alone are not violations.
# These patterns instead describe treatment, disappearance, guaranteed efficacy,
# or physiological claims. Conservative negation and makeup qualifiers below
# apply to the individual match, never to the entire product description.
_CLAIM_PATTERNS = (
    ("treatment", re.compile(r"治癒|完治|根治|(?:ニキビ|にきび|吹き出物|病気|疾患|傷|けが|ケガ|アトピー|腰痛|関節痛|感染症)(?:を|が)?(?:完全に|根本から)?(?:治す|治る|治療)")),
    ("physiological", re.compile(r"疲労回復|老化防止|血液サラサラ|バストアップ|デトックス|脂肪燃焼|代謝促進|精力剤|性的機能")),
    ("spot_removal", re.compile(r"(?:シミ|しみ|シワ|しわ)(?:を|が)?(?:完全に|根本から)?(?:消す|消える|消失|除去|なくす|なくなる)")),
    ("medical_effect", re.compile(r"(?:がん|癌|糖尿病|高血圧|アトピー|感染症|花粉症|不眠症)(?:の|を|に|が|への)?(?:治療|予防|改善|効く|効果|効能)")),
    ("guaranteed_effect", re.compile(r"(?:必ず|絶対に|100%)(?:.{0,10}?)(?:効く|効果がある|効果を実感|改善|治る)")),
)
_NEGATED_TAIL = re.compile(
    r"^(?:する|される|をうたう)?(?:効果|効能)?(?:が|は|を)?"
    r"(?:ありません|ない(?:です)?|認められていません|保証しません|ものでは(?:ありません|ない)|ことは(?:ありません|ない))"
)
_MAKEUP_QUALIFIER = re.compile(r"(?:メイク(?:アップ)?|メーキャップ|メーキャプ)(?:効果)?(?:によ(?:り|る|って))?")
_MATERIAL_TARGET = re.compile(
    r"(?:衣類|衣服|洋服|シャツ|布地|カーペット|ソファ|家具|ガラス|金属|木材|床|靴|車体)"
    r"(?:の|に(?:付いた|ついた|できた))$"
)


def advertising_expression_matches(fields: dict[str, str]) -> list[dict[str, Any]]:
    matches = []
    for field, value in fields.items():
        text = claim_text(value)
        # Newlines and sentence boundaries prevent one permitted disclaimer
        # from exempting a separate positive therapeutic claim.
        for sentence_match in re.finditer(r"[^。！？!?\n]+", text):
            sentence = sentence_match.group()
            for rule, pattern in _CLAIM_PATTERNS:
                for match in pattern.finditer(sentence):
                    tail = sentence[match.end():].lstrip()
                    if _NEGATED_TAIL.match(tail):
                        continue
                    # Removing a stain/wrinkle from an explicitly named material
                    # is not a cosmetic claim. Do not exempt the rest of the copy.
                    if rule == "spot_removal" and _MATERIAL_TARGET.search(sentence[:match.start()]):
                        continue
                    if rule == "spot_removal" and _MAKEUP_QUALIFIER.search(sentence[:match.start()]):
                        # Only an explicitly cosmetic/visual effect qualifies;
                        # a makeup mention must not excuse actual removal.
                        if re.match(r"(?:ように)?(?:見せる|見える)", tail):
                            continue
                    start = sentence_match.start() + match.start()
                    end = sentence_match.start() + match.end()
                    matches.append({
                        "word": match.group(), "field": field, "start": start, "end": end,
                        "context": text[max(0, start - 35):end + 60],
                        "rule_kind": "advertising_expression", "expression_rule": rule,
                        "policy_version": POLICY_VERSION, "coordinate_space": "normalized_claim_text",
                    })
    return matches


def analyze_listing_text_policy(
    fields: dict[str, str], forbidden_words: list[str], allowed_phrase_rules: dict[str, list[str]],
    *, brand: str = "", separate_check_rules: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    strict_words = list(dict.fromkeys(word for word in forbidden_words if word in WORD_OR_BRAND_TERMS))
    contains_words = [word for word in forbidden_words
                      if word not in WORD_OR_BRAND_TERMS and word not in CONTEXTUAL_CLAIM_TERMS]
    analysis = analyze_prohibited_word_issues(
        fields, contains_words, allowed_phrase_rules, separate_check_rules=separate_check_rules,
    )
    analysis["matched_forbidden_words"].extend(brand_word_matches(fields, strict_words, brand))
    analysis["matched_forbidden_words"].extend(advertising_expression_matches(fields))
    analysis["policy_version"] = POLICY_VERSION
    return analysis
