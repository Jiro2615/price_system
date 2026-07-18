from __future__ import annotations

from collections import Counter
from typing import Any


GROUP_LISTED_SUCCESS = "legacy_listed_success"
GROUP_FALSE_POSITIVE = "likely_false_positive"
GROUP_REGULATORY = "regulatory_or_safety"
GROUP_IE0270 = "rakuten_api_error_ie0270"
GROUP_FBA = "fba_out_of_stock"

FALSE_POSITIVE_WORDS = [
    "帝",
    "CS",
    "SM",
    "Title",
    "クリス",
    "インナー",
    "グルメ",
    "グローバル",
    "ユニーク",
    "レシピ",
    "中学生",
    "公式",
    "登録",
    "謎解き",
    "レベルアップ",
]

REGULATORY_WORDS = [
    "医療",
    "医療機器",
    "治療",
    "性的",
    "武器",
    "銃",
    "刀",
    "剣",
    "盗撮",
    "パルスオキシメータ",
    "食品",
]


def _entry_with_reason(entry: dict[str, Any], group: str, selection_reason: str) -> dict[str, Any]:
    return {
        "asin": entry["asin"],
        "group": group,
        "legacy_status": entry.get("legacy_status"),
        "legacy_reason_type": entry.get("legacy_reason_type"),
        "legacy_reason": entry.get("legacy_reason"),
        "legacy_forbidden_word": entry.get("legacy_forbidden_word"),
        "legacy_listing_completed": bool(entry.get("legacy_listing_completed")),
        "selection_reason": selection_reason,
    }


def select_legacy_comparison_samples(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    entries = list(baseline.get("targets") or [])
    selected: list[dict[str, Any]] = []
    used_asins: set[str] = set()

    def pick(predicate, group: str, limit: int, reason_builder) -> None:
        nonlocal selected
        for entry in entries:
            asin = str(entry.get("asin") or "")
            if asin in used_asins or not predicate(entry):
                continue
            selected.append(_entry_with_reason(entry, group, reason_builder(entry)))
            used_asins.add(asin)
            if sum(1 for item in selected if item["group"] == group) >= limit:
                return

    pick(
        lambda entry: bool(entry.get("legacy_listing_completed")),
        GROUP_LISTED_SUCCESS,
        10,
        lambda entry: "旧システムで出品完了した成功実績サンプル",
    )

    for word in FALSE_POSITIVE_WORDS:
        pick(
            lambda entry, target=word: entry.get("legacy_forbidden_word") == target,
            GROUP_FALSE_POSITIVE,
            sum(1 for item in selected if item["group"] == GROUP_FALSE_POSITIVE) + 1,
            lambda entry, target=word: f"旧禁止語 {target} の誤検知候補を代表抽出",
        )
        if sum(1 for item in selected if item["group"] == GROUP_FALSE_POSITIVE) >= 10:
            break

    for word in REGULATORY_WORDS:
        pick(
            lambda entry, target=word: entry.get("legacy_forbidden_word") == target,
            GROUP_REGULATORY,
            sum(1 for item in selected if item["group"] == GROUP_REGULATORY) + 1,
            lambda entry, target=word: f"安全・規制系禁止語 {target} の代表サンプル",
        )
        if sum(1 for item in selected if item["group"] == GROUP_REGULATORY) >= 8:
            break

    pick(
        lambda entry: entry.get("legacy_reason_type") == "rakuten_api_error",
        GROUP_IE0270,
        3,
        lambda entry: "旧システムでIE0270になった楽天API reject サンプル",
    )
    pick(
        lambda entry: entry.get("legacy_reason_type") == "fba_out_of_stock",
        GROUP_FBA,
        1,
        lambda entry: "旧システムでFBA在庫切れになった代表サンプル",
    )

    return selected


def summarize_selected_samples(samples: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(item.get("group") or "") for item in samples))
