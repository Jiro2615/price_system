"""Whole-word forced-listing exclusions and per-item human review holds."""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from scripts.listing.listing_text_policy import plain_text
from scripts.listing.models import AmazonCheckResult, KeepaProductData, sanitize_for_output, to_jsonable

GROUPS_PATH = Path(__file__).resolve().parents[2] / "reference/listing_policy/forced_word_groups.json"
HOLD_STATUSES = {"word_review_pending", "company_brand_blocked"}


@lru_cache(maxsize=1)
def load_file_groups() -> tuple[str, dict[str, str]]:
    data = json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
    groups: dict[str, str] = {}
    for group in ("ignore", "review", "block"):
        words = data["groups"][group]
        if not isinstance(words, list) or not all(isinstance(word, str) and word.strip() for word in words):
            raise ValueError("Invalid forced-word classification file")
        for word in words:
            groups[plain_text(word).strip()] = group
    return str(data["version"]), groups


def load_groups(*, use_database: bool = False) -> tuple[str, dict[str, str]]:
    version, base = load_file_groups()
    if not use_database:
        return version, base
    from scripts.listing.forced_word_classification_db import read_overrides
    overrides = read_overrides()
    # No cache for the shared overrides. An unreadable DB must not result in
    # use of older rules, and the final pre-write gate reads the latest values.
    return version + ":shared-db-v2", {**base, **overrides}


def token_word(word: str) -> str:
    word = plain_text(word).strip()
    for opening, closing in (("(", ")"), ("[", "]"), ("【", "】"), ("「", "」")):
        if word.startswith(opening) and word.endswith(closing):
            return word[1:-1].strip()
    return word


@lru_cache(maxsize=8)
def compiled_words(words: tuple[str, ...]):
    tokens = sorted({token_word(word) for word in words if token_word(word)}, key=lambda word: (-len(word), word))
    if not tokens:
        return None
    return re.compile(r"(?<![\wー])(?:" + "|".join(re.escape(word) for word in tokens) + r")(?![\wー])")


def value(obj: object, key: str) -> str:
    return str((obj.get(key) if isinstance(obj, dict) else getattr(obj, key, "")) or "")


def noun_matches(dry: dict, active_words: list[str], *, groups=None) -> tuple[str, list[dict]]:
    version, classification = groups or load_groups(use_database=True)
    active = tuple(sorted(set(word for word in active_words if classification.get(plain_text(word).strip(), "review") != "ignore")))
    pattern = compiled_words(active)
    if pattern is None:
        return version, []
    aliases: dict[str, list[str]] = {}
    for word in active:
        aliases.setdefault(token_word(word), []).append(word)
    amazon, keepa = dry.get("amazon_result"), dry.get("keepa_result")
    descriptions = (dry.get("item_payload") or {}).get("productDescription") or {}
    texts = {"Amazon商品名": value(amazon, "title"), "Keepa商品名": value(keepa, "title"),
             "商品説明PC": str(descriptions.get("pc") or ""), "商品説明SP": str(descriptions.get("sp") or ""),
             "ブランド": value(keepa, "brand"), "メーカー": value(keepa, "manufacturer")}
    matches = []
    seen = set()
    for field, original in texts.items():
        text = plain_text(original)
        found = list(pattern.finditer(text))
        # A corporate designator is not part of a different brand word.
        # In these two structured fields only, also compare the entire name
        # after removing a leading/trailing legal-company designator.
        if field in {"ブランド", "メーカー"}:
            bare = re.sub(r"^(?:株式会社|有限会社|合同会社|\(株\)|\(有\))\s*", "", text.strip())
            bare = re.sub(r"\s*(?:株式会社|有限会社|合同会社)$", "", bare)
            if bare != text.strip() and bare in aliases:
                start = text.find(bare)
                found.append((start, start + len(bare), bare))
        for match in found:
            start, end, token = match if isinstance(match, tuple) else (match.start(), match.end(), match.group())
            for word in aliases[token]:
                key = (word, field, start, end)
                if key in seen:
                    continue
                seen.add(key)
                matches.append({"word": word, "group": classification.get(plain_text(word).strip(), "review"),
                                "field": field, "before": text[max(0, start-35):start],
                                "matched": text[start:end], "after": text[end:end+55],
                                "rule_kind": "whole_word", "coordinate_space": "normalized_plain_text"})
    return version, matches


def review_token(asin: str, store: str, title: str, version: str, matches: list[dict]) -> str:
    normalized = json.dumps([asin, store, title, version, matches], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def screen_forced_words(dry: dict, active_words: list[str], *, block_company: bool = False,
                        review_uncertain: bool = False, approved_token: str = "", groups=None) -> dict:
    if not block_company and not review_uncertain:
        return dry
    version, matches = noun_matches(dry, active_words, groups=groups)
    blockers = [match for match in matches if match["group"] == "block"] if block_company else []
    reviews = [match for match in matches if match["group"] == "review"] if review_uncertain else []
    if not blockers and not reviews:
        return dry
    title = value(dry.get("amazon_result"), "title") or value(dry.get("keepa_result"), "title")
    token = review_token(str(dry["asin"]), str(dry["store_code"]), title, version, reviews)
    decision = {"version": version, "title": title, "matches": blockers + reviews, "review_token": token,
                "block_company": block_company, "review_uncertain": review_uncertain}
    dry["forced_word_review"] = decision
    if not blockers and reviews and token == approved_token:
        decision["state"] = "approved"
        return dry
    # Hold only otherwise executable items. Other NGs must remain NGs and may
    # never be converted into an approvable item by this classification.
    if dry.get("listing_status") != "eligible" or not dry.get("execution_allowed"):
        decision["state"] = "other_blocked"
        return dry
    state = "company_brand_blocked" if blockers else "word_review_pending"
    decision["state"] = state
    decision["prepared_at"] = datetime.now(timezone.utc).isoformat()
    if not blockers:
        # Only public product observations. Auth/configuration and headers are
        # not retained. Resume re-runs current DB rules, duplicate and price/
        # stock checks rather than blindly sending this historical payload.
        dry["forced_word_review_cache"] = sanitize_for_output(to_jsonable({
            "asin": dry["asin"], "store_code": dry["store_code"], "review_token": token,
            "prepared_at": decision["prepared_at"], "management_number": dry.get("management_number"),
            "amazon_result": dry.get("amazon_result"), "keepa_result": dry.get("keepa_result"),
            "item_payload": dry.get("item_payload"), "inventory_payload": dry.get("inventory_payload"),
            "image_download_plan": dry.get("image_download_plan"),
        }))
    dry.update(listing_status=state, listing_reason="禁止会社・ブランドの単語一致" if blockers else "要確認語の単語一致：出品せず確認待ち",
               execution_allowed=False, final_status=state, external_actions_performed=False)
    dry["blocking_reasons"] = list(dry.get("blocking_reasons") or []) + [dry["listing_reason"]]
    dry["warnings"] = list(dry.get("warnings") or []) + [dry["listing_reason"]]
    dry["execution_summary"] = {**(dry.get("execution_summary") or {}), "can_execute_listing": False}
    return dry


def restored_observations(cache: dict) -> tuple[AmazonCheckResult, KeepaProductData]:
    def restore(cls, key):
        raw = cache[key]
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: val for key, val in raw.items() if key in allowed})
    return restore(AmazonCheckResult, "amazon_result"), restore(KeepaProductData, "keepa_result")
