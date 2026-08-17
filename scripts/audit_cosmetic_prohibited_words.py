"""Report cosmetic false-positive candidates without modifying allow-lists."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.listing.master_loader import load_replacements, load_word_list
from scripts.listing.prohibited_word_masking import load_allowed_phrase_rules


# These are review candidates only. They are never added to an allow-list automatically.
COSMETIC_CANDIDATES: dict[str, list[str]] = {
    "イラ": [
        "アイライン",
        "アイライナー",
        "アイラッシュ",
        "アイラッシュカーラー",
        "アイラッシュグルー",
        "アイラッシュセラム",
        "アイラッシュブラシ",
        "アイラッシュ美容液",
        "イランイラン",
        "カラーアイライナー",
        "ジェルアイライナー",
        "ペンシルアイライナー",
        "ライラック",
        "ライナー",
        "リキッドアイライナー",
    ],
    "マカ": ["マカデミア", "マカデミア種子油"],
    "セラ": ["ミセラー", "セラミド", "セラム"],
    "コル": ["アスコルビル", "アスコルビン酸", "コラーゲン", "コルネオサイト"],
    "スキン": [
        "スキンケア",
        "スキンタイプ",
        "スキントーン",
        "スキンプロテクト",
        "スキンコンディショナー",
        "スキンローション",
    ],
    "アルコール": [
        "アルコールフリー",
        "エチルアルコール",
        "ステアリルアルコール",
        "セテアリルアルコール",
        "ベヘニルアルコール",
        "変性アルコール",
    ],
    "アルギニン": ["アルギニン", "ココイルアルギニン", "アルギニンエチルPCA"],
}


def is_spacing_only(source: str, target: str) -> bool:
    return bool(source and target and source != target and "".join(source.split()) == "".join(target.split()))


def load_store_rules(master_dir: Path, store_code: str) -> dict[str, list[str]]:
    path = master_dir / f"allowed_phrases_rakuten.{store_code}.json"
    if not path.exists():
        return {}
    return dict(load_allowed_phrase_rules(path)["rules"])


def build_report(master_dir: Path) -> dict[str, Any]:
    prohibited_words = set(load_word_list(master_dir / "kinsiword_rakuten.txt"))
    common_rules = dict(load_allowed_phrase_rules(master_dir / "allowed_phrases_rakuten.json")["rules"])
    store_2_rules = load_store_rules(master_dir, "rakuten_2")
    legacy_matches: dict[str, set[str]] = defaultdict(set)

    for source, target in load_replacements(master_dir / "replacelist_rakuten.txt"):
        if not is_spacing_only(source, target):
            continue
        for forbidden_word in COSMETIC_CANDIDATES:
            if forbidden_word in prohibited_words and forbidden_word in source:
                legacy_matches[forbidden_word].add(source)

    entries: list[dict[str, Any]] = []
    for forbidden_word, phrases in COSMETIC_CANDIDATES.items():
        if forbidden_word not in prohibited_words:
            continue
        common = set(common_rules.get(forbidden_word, []))
        store_2 = set(store_2_rules.get(forbidden_word, []))
        phrase_rows = []
        for phrase in phrases:
            common_match = next((allowed for allowed in common if allowed in phrase), None)
            store_2_match = next((allowed for allowed in store_2 if allowed in phrase), None)
            phrase_rows.append(
                {
                    "phrase": phrase,
                    "common_allowed": common_match is not None,
                    "rakuten_2_allowed": store_2_match is not None,
                    "matched_common_phrase": common_match,
                    "matched_rakuten_2_phrase": store_2_match,
                    "status": "common" if common_match else "rakuten_2" if store_2_match else "review",
                }
            )
        entries.append(
            {
                "forbidden_word": forbidden_word,
                "forbidden_word_length": len(forbidden_word),
                "legacy_spacing_evidence": sorted(legacy_matches[forbidden_word]),
                "phrases": phrase_rows,
            }
        )

    return {
        "purpose": "Review cosmetic false-positive candidates. This report does not modify allow-lists.",
        "master_dir": str(master_dir),
        "store_specific_overlay": "allowed_phrases_rakuten.rakuten_2.json",
        "candidate_count": sum(len(entry["phrases"]) for entry in entries),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-dir", type=Path, default=Path("reference/legacy_listing"))
    parser.add_argument("--output", type=Path, default=Path("output/diagnostics/cosmetic_prohibited_word_candidates.json"))
    args = parser.parse_args()

    report = build_report(args.master_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({report['candidate_count']} candidate phrases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
