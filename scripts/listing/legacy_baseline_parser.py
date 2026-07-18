from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any


TARGETS_MARKER = "処理対象"
NG_MARKER = "NGリスト"
ASIN_TOKEN_RE = re.compile(r"^[A-Z0-9]+$")
FORBIDDEN_REASON_RE = re.compile(r"^禁止キーワード\((.+)\)$")


def _extract_section_tokens(text: str, start_marker: str, end_marker: str | None = None) -> list[str]:
    start = text.find(start_marker)
    if start < 0:
        return []
    start += len(start_marker)
    end = text.find(end_marker, start) if end_marker else -1
    section = text[start:end if end >= 0 else None]
    return [token.strip() for token in section.split() if token.strip()]


def parse_processing_targets(text: str) -> dict[str, Any]:
    tokens = _extract_section_tokens(text, TARGETS_MARKER, NG_MARKER)
    accepted = [token for token in tokens if ASIN_TOKEN_RE.fullmatch(token)]
    counter = Counter(accepted)
    duplicates = sorted([asin for asin, count in counter.items() if count > 1])
    return {
        "targets": accepted,
        "duplicate_targets": duplicates,
        "invalid_tokens": [token for token in tokens if not ASIN_TOKEN_RE.fullmatch(token)],
    }


def _parse_api_error_payload(raw_reason: str) -> dict[str, Any]:
    payload = json.loads(raw_reason)
    errors = payload.get("errors") or []
    parsed_errors: list[dict[str, Any]] = []
    property_paths: list[str] = []
    codes: list[str] = []
    messages: list[str] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        code = error.get("code")
        message = error.get("message")
        metadata = error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
        property_path = metadata.get("propertyPath")
        parsed_errors.append(
            {
                "code": code,
                "message": message,
                "propertyPath": property_path,
            }
        )
        if isinstance(code, str) and code not in codes:
            codes.append(code)
        if isinstance(message, str) and message not in messages:
            messages.append(message)
        if isinstance(property_path, str) and property_path not in property_paths:
            property_paths.append(property_path)
    return {
        "legacy_status": "api_rejected",
        "legacy_reason_type": "rakuten_api_error",
        "legacy_api_errors": parsed_errors,
        "legacy_error_codes": codes,
        "legacy_error_messages": messages,
        "legacy_property_paths": property_paths,
    }


def classify_legacy_ng_reason(raw_reason: str) -> dict[str, Any]:
    reason = raw_reason.strip()
    if reason == "FBA在庫切れ":
        return {
            "legacy_status": "business_ng",
            "legacy_reason_type": "fba_out_of_stock",
        }
    forbidden_match = FORBIDDEN_REASON_RE.match(reason)
    if forbidden_match:
        return {
            "legacy_status": "business_ng",
            "legacy_reason_type": "prohibited_word",
            "legacy_forbidden_word": forbidden_match.group(1),
        }
    if reason.startswith("{") and reason.endswith("}"):
        try:
            return _parse_api_error_payload(reason)
        except json.JSONDecodeError:
            pass
    return {
        "legacy_status": "other_error",
        "legacy_reason_type": "other_error",
    }


def parse_ng_list(text: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    duplicate_ng_entries: list[str] = []
    parse_errors: list[dict[str, str]] = []
    seen: Counter[str] = Counter()

    start = text.find(NG_MARKER)
    if start < 0:
        return {
            "entries": [],
            "duplicate_ng_entries": [],
            "parse_errors": [],
        }
    section = text[start + len(NG_MARKER) :].strip()
    pattern = re.compile(
        r"([A-Z0-9]+)\s+"
        r"(FBA在庫切れ|禁止キーワード\([^)]*\)|\{.*?\})"
        r"(?=\s+[A-Z0-9]+\s+(?:FBA在庫切れ|禁止キーワード\(|\{)|\s*$)",
        re.DOTALL,
    )

    for match in pattern.finditer(section):
        asin = match.group(1)
        raw_reason = match.group(2).strip()
        seen[asin] += 1
        if seen[asin] > 1:
            duplicate_ng_entries.append(asin)
        classified = classify_legacy_ng_reason(raw_reason)
        entries.append(
            {
                "asin": asin,
                "legacy_reason": raw_reason,
                "legacy_listing_completed": False,
                **classified,
            }
        )

    unmatched = pattern.sub(" ", section)
    for token in unmatched.split():
        if token not in {NG_MARKER}:
            parse_errors.append({"asin": token, "reason": "unparsed_ng_fragment"})

    return {
        "entries": entries,
        "duplicate_ng_entries": sorted(set(duplicate_ng_entries)),
        "parse_errors": parse_errors,
    }


def build_legacy_baseline(target_text: str, ng_text: str, *, source: str = "legacy_system_actual_run") -> dict[str, Any]:
    targets_info = parse_processing_targets(target_text)
    ng_info = parse_ng_list(ng_text)

    ng_by_asin = {entry["asin"]: entry for entry in ng_info["entries"]}
    target_counter = Counter(targets_info["targets"])

    targets: list[dict[str, Any]] = []
    for asin in targets_info["targets"]:
        ng_entry = ng_by_asin.get(asin)
        if ng_entry is None:
            targets.append(
                {
                    "asin": asin,
                    "legacy_status": "listed_success",
                    "legacy_reason_type": None,
                    "legacy_reason": None,
                    "legacy_listing_completed": True,
                }
            )
            continue
        targets.append(
            {
                "asin": asin,
                "legacy_status": ng_entry["legacy_status"],
                "legacy_reason_type": ng_entry["legacy_reason_type"],
                "legacy_reason": ng_entry["legacy_reason"],
                "legacy_listing_completed": False,
                **{
                    key: value
                    for key, value in ng_entry.items()
                    if key
                    not in {
                        "asin",
                        "legacy_status",
                        "legacy_reason_type",
                        "legacy_reason",
                        "legacy_listing_completed",
                    }
                },
            }
        )

    target_set = set(target_counter)
    ng_set = {entry["asin"] for entry in ng_info["entries"]}
    ng_only_asins = sorted(ng_set - target_set)
    listed_success_count = sum(1 for entry in targets if entry["legacy_listing_completed"])
    failed_count = len(targets) - listed_success_count
    success_rate = (listed_success_count / len(targets)) if targets else 0.0

    return {
        "meta": {
            "source": source,
            "description": "旧システム実処理結果 baseline",
            "version": 1,
        },
        "targets": targets,
        "summary": {
            "target_count": len(targets_info["targets"]),
            "unique_target_count": len(target_set),
            "ng_count": len(ng_info["entries"]),
            "legacy_listed_success_count": listed_success_count,
            "legacy_failed_count": failed_count,
            "listing_success_rate": success_rate,
        },
        "diagnostics": {
            "duplicate_targets": targets_info["duplicate_targets"],
            "duplicate_ng_entries": ng_info["duplicate_ng_entries"],
            "invalid_target_tokens": targets_info["invalid_tokens"],
            "ng_parse_errors": ng_info["parse_errors"],
            "ng_only_asins": ng_only_asins,
        },
    }
