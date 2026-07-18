from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from scripts.listing.legacy_baseline_parser import build_legacy_baseline

def load_legacy_baseline(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_legacy_text = payload.get("raw_legacy_text")
    if isinstance(raw_legacy_text, str) and raw_legacy_text.strip():
        source = str((payload.get("meta") or {}).get("source") or "legacy_system_actual_run")
        return build_legacy_baseline(raw_legacy_text, raw_legacy_text, source=source)
    return payload


def load_saved_dry_run_result(saved_dir: Path, asin: str) -> dict[str, Any] | None:
    path = Path(saved_dir) / f"{asin}_dry_run.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_new_reason_type(result: dict[str, Any]) -> str | None:
    listing_status = str(result.get("listing_status") or "")
    listing_reason = str(result.get("listing_reason") or "")
    matched_forbidden_words = result.get("matched_forbidden_words") or []
    seller_eval = result.get("seller_count_evaluation") or {}

    if listing_status == "eligible":
        return "eligible"
    if listing_status == "system_error":
        return "system_error"
    if matched_forbidden_words or "prohibited word matched" in listing_reason:
        return "prohibited_word"
    if seller_eval and seller_eval.get("passed") is False:
        return "seller_count_threshold"
    if listing_status == "missing_required_data":
        return "missing_required_data"
    if listing_status == "already_listed":
        return "already_listed"
    if listing_status == "business_ng" and "Amazon" in listing_reason:
        return "amazon_business_rule"
    if listing_status == "business_ng":
        return "business_ng"
    return listing_status or None


def _is_new_completed(result: dict[str, Any]) -> bool:
    execute_status = str(result.get("execute_status") or "")
    return execute_status == "completed" or str(result.get("listing_status") or "") == "listed_success"


def _build_review_notes(legacy_entry: dict[str, Any], new_result: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    new_status = str(new_result.get("listing_status") or "")
    listing_reason = str(new_result.get("listing_reason") or "")
    seller_eval = new_result.get("seller_count_evaluation") or {}

    if legacy_entry.get("legacy_listing_completed") and new_status == "business_ng":
        notes.append("旧システムでは出品完了。新システムでNGになったため review が必要です。")
        notes.append("新たに安全上必要な判定か、新システムの過剰判定かを確認してください。")
    if seller_eval and seller_eval.get("passed") is False:
        notes.append("seller count 条件差または保存済み入力の時点差の可能性があります。")
    if "カテゴリ" in listing_reason or "属性不足" in listing_reason:
        notes.append("マスター差または属性解決ルール差の可能性があります。")
    if not notes and legacy_entry.get("legacy_listing_completed") and new_status != "eligible":
        notes.append("旧成功実績との差分理由を確認してください。")
    return notes


def _comparison_status(legacy_entry: dict[str, Any], new_result: dict[str, Any] | None) -> str:
    if new_result is None:
        return "missing_saved_input"
    new_status = str(new_result.get("listing_status") or "")
    if new_status == "system_error":
        return "system_error"

    legacy_completed = bool(legacy_entry.get("legacy_listing_completed"))
    if legacy_completed:
        if _is_new_completed(new_result):
            return "matched_listed_success"
        if new_status == "eligible":
            return "legacy_listed_success_new_eligible"
        return "legacy_listed_success_new_ng"

    if new_status == "eligible" or _is_new_completed(new_result):
        return "legacy_failed_new_eligible"
    if legacy_entry.get("legacy_reason_type") == _extract_new_reason_type(new_result):
        return "legacy_failed_new_ng_same_reason"
    return "legacy_failed_new_ng_different_reason"


def compare_with_saved_results(
    baseline: dict[str, Any],
    *,
    result_loader: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for legacy_entry in baseline.get("targets") or []:
        asin = str(legacy_entry.get("asin") or "")
        new_result = result_loader(asin)
        comparison_status = _comparison_status(legacy_entry, new_result)
        counts[comparison_status] = counts.get(comparison_status, 0) + 1

        if new_result is None:
            comparisons.append(
                {
                    "asin": asin,
                    "legacy_status": legacy_entry.get("legacy_status"),
                    "legacy_reason_type": legacy_entry.get("legacy_reason_type"),
                    "legacy_reason": legacy_entry.get("legacy_reason"),
                    "legacy_forbidden_word": legacy_entry.get("legacy_forbidden_word"),
                    "legacy_listing_completed": legacy_entry.get("legacy_listing_completed"),
                    "new_listing_status": "not_evaluated",
                    "new_listing_reason": None,
                    "new_reason_type": None,
                    "new_matched_forbidden_words": [],
                    "new_allowed_phrase_matches": [],
                    "new_legacy_spacing_reviews": [],
                    "new_blocking_reasons": [],
                    "comparison_status": comparison_status,
                    "review_required": False,
                    "notes": [],
                }
            )
            continue

        review_required = comparison_status in {
            "legacy_listed_success_new_ng",
            "legacy_failed_new_eligible",
            "system_error",
        }
        if legacy_entry.get("legacy_listing_completed") and str(new_result.get("listing_status") or "") == "business_ng":
            review_required = True

        comparisons.append(
            {
                "asin": asin,
                "legacy_status": legacy_entry.get("legacy_status"),
                "legacy_reason_type": legacy_entry.get("legacy_reason_type"),
                "legacy_reason": legacy_entry.get("legacy_reason"),
                "legacy_forbidden_word": legacy_entry.get("legacy_forbidden_word"),
                "legacy_listing_completed": legacy_entry.get("legacy_listing_completed"),
                "new_listing_status": new_result.get("listing_status"),
                "new_listing_reason": new_result.get("listing_reason"),
                "new_reason_type": _extract_new_reason_type(new_result),
                "new_matched_forbidden_words": new_result.get("matched_forbidden_words") or [],
                "new_allowed_phrase_matches": new_result.get("allowed_phrase_matches") or [],
                "new_legacy_spacing_reviews": new_result.get("legacy_spacing_reviews") or [],
                "new_blocking_reasons": new_result.get("blocking_reasons") or [],
                "comparison_status": comparison_status,
                "review_required": review_required,
                "notes": _build_review_notes(legacy_entry, new_result),
            }
        )

    return {
        "meta": {
            "source": "saved_dry_run_results",
            "baseline_source": baseline.get("meta", {}).get("source"),
        },
        "summary": {
            **(baseline.get("summary") or {}),
            "comparison_counts": counts,
            "inconsistency_count": len((baseline.get("diagnostics") or {}).get("ng_only_asins") or []),
        },
        "diagnostics": baseline.get("diagnostics") or {},
        "comparisons": comparisons,
    }
