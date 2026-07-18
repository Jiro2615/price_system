from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.listing.master_loader import read_text_auto


DEFAULT_CSV_FILES = (
    Path("input/legacy_item/dl-normal-item_20260713160155-1.csv"),
    Path("input/legacy_item/dl-normal-item_20260713160155-2.csv"),
)
DEFAULT_MASTER_DIR = Path("reference/legacy_listing")

TOKEN_RE = re.compile(r"[A-Za-z0-9#.+-]+|[ぁ-んァ-ヶ一-龠々ー]+")

GENERIC_TOKENS = {
    "シンプル",
    "デザイン",
    "コンパクト",
    "サイズ",
    "セット",
    "タイプ",
    "シリーズ",
    "効果",
    "最強",
    "主張",
}

DOMAIN_KEYWORD_EXPANSIONS = {
    "コバエ": {"虫除け", "殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "バルサン": {"虫除け", "殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "殺虫": {"殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "虫類": {"殺虫剤", "虫除け・殺虫剤", "日用消耗品"},
    "カイガラムシ": {"園芸薬剤", "植物活性剤", "殺虫剤", "花・ガーデン・DIY"},
    "エアゾール": {"殺虫スプレー", "スプレー", "虫除け・殺虫剤"},
    "園芸": {"園芸薬剤", "植物活性剤", "花・ガーデン・DIY"},
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON must be an object: {path}")
    return payload


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in TOKEN_RE.finditer(str(text or "").lower()):
        token = match.group(0).strip()
        if len(token) >= 2:
            tokens.add(token)
        if re.fullmatch(r"[ぁ-んァ-ヶ一-龠々ー]+", token):
            max_len = min(8, len(token))
            for size in range(2, max_len + 1):
                for index in range(0, len(token) - size + 1):
                    tokens.add(token[index : index + size])
    return tokens


def extract_priority_terms(text: str) -> set[str]:
    priority_terms: set[str] = set()
    normalized = str(text or "")
    for source, expansions in DOMAIN_KEYWORD_EXPANSIONS.items():
        if source in normalized:
            priority_terms.add(source)
            priority_terms.update(expansions)
    return priority_terms


def query_text_from_dry_run(payload: dict[str, Any]) -> str:
    amazon = payload.get("amazon_result") if isinstance(payload.get("amazon_result"), dict) else {}
    keepa = payload.get("keepa_result") if isinstance(payload.get("keepa_result"), dict) else {}
    parts: list[str] = [
        str(amazon.get("title") or ""),
        str(keepa.get("title") or ""),
        str(keepa.get("brand") or ""),
        str(keepa.get("manufacturer") or ""),
        str(keepa.get("model") or ""),
        str(keepa.get("part_number") or ""),
        str(keepa.get("color") or ""),
        str(keepa.get("style") or ""),
        str(keepa.get("size") or ""),
        str(keepa.get("description") or ""),
    ]
    features = keepa.get("features")
    if isinstance(features, list):
        parts.extend(str(item or "") for item in features)
    category_tree = keepa.get("category_tree") or (keepa.get("raw_summary") or {}).get("category_tree")
    if isinstance(category_tree, list):
        for node in category_tree:
            if isinstance(node, dict):
                parts.append(str(node.get("name") or ""))
    return "\n".join(part for part in parts if part)


def load_attribute_definitions(master_dir: Path) -> dict[int, dict[str, Any]]:
    path = master_dir / "属性定義書.txt"
    if not path.exists():
        return {}
    result: dict[int, dict[str, Any]] = {}
    for raw_line in read_text_auto(path).splitlines():
        parts = [part.strip() for part in raw_line.split("\t") if part.strip()]
        if len(parts) < 2:
            continue
        try:
            genre_id = int(parts[0])
        except ValueError:
            continue
        result[genre_id] = {
            "genre_path": parts[1],
            "required_attributes": parts[2:],
        }
    return result


def iter_product_rows(csv_files: list[Path]):
    for path in csv_files:
        with path.open("r", encoding="cp932", newline="") as file:
            reader = csv.reader(file)
            header = next(reader)
            for row in reader:
                if len(row) <= 20:
                    continue
                management_number = row[0]
                item_number = row[1]
                title = row[2]
                genre_id = row[20]
                if not management_number or not item_number or not title or not genre_id:
                    continue
                try:
                    yield {
                        "source_file": str(path),
                        "management_number": management_number,
                        "title": title,
                        "genre_id": int(genre_id),
                    }
                except ValueError:
                    continue


def build_document_frequency(csv_files: list[Path], *, limit_rows: int = 0) -> tuple[Counter[str], int]:
    document_frequency: Counter[str] = Counter()
    total = 0
    for row in iter_product_rows(csv_files):
        total += 1
        if limit_rows and total > limit_rows:
            break
        document_frequency.update(tokenize(str(row["title"])))
    return document_frequency, total


def _token_weight(token: str, document_frequency: Counter[str], total_documents: int) -> float:
    frequency = int(document_frequency.get(token, 0))
    if total_documents <= 0 or frequency <= 0:
        return 0.0
    document_ratio = frequency / total_documents
    if document_ratio > 0.03:
        return 0.0
    if len(token) <= 2 and document_ratio > 0.003:
        return 0.0
    return math.log((total_documents + 1) / (frequency + 1)) * min(len(token), 10)


def score_candidates(
    query_tokens: set[str],
    csv_files: list[Path],
    *,
    document_frequency: Counter[str],
    total_documents: int,
    limit_rows: int = 0,
) -> dict[int, dict[str, Any]]:
    by_genre: dict[int, dict[str, Any]] = {}
    scanned = 0
    weighted_query_tokens = {
        token
        for token in query_tokens
        if _token_weight(token, document_frequency, total_documents) > 0
    }
    for row in iter_product_rows(csv_files):
        scanned += 1
        if limit_rows and scanned > limit_rows:
            break
        row_tokens = tokenize(str(row["title"]))
        overlap = weighted_query_tokens & row_tokens
        if not overlap:
            continue
        score = sum(_token_weight(token, document_frequency, total_documents) for token in overlap)
        score = score * (1.0 + math.log1p(len(overlap)) / 4.0)
        genre_id = int(row["genre_id"])
        entry = by_genre.setdefault(
            genre_id,
            {
                "genre_id": genre_id,
                "score": 0.0,
                "match_count": 0,
                "matched_tokens": Counter(),
                "examples": [],
            },
        )
        entry["score"] += score
        entry["match_count"] += 1
        entry["matched_tokens"].update(overlap)
        if len(entry["examples"]) < 5:
            entry["examples"].append(
                {
                    "management_number": row["management_number"],
                    "title": row["title"],
                    "matched_tokens": sorted(overlap, key=lambda item: (-len(item), item))[:12],
                }
            )
    return by_genre


def score_genre_path_candidates(
    query_tokens: set[str],
    attribute_definitions: dict[int, dict[str, Any]],
    *,
    priority_terms: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    weighted_tokens = {
        token
        for token in query_tokens
        if len(token) >= 3 and token not in GENERIC_TOKENS
    }
    for genre_id, info in attribute_definitions.items():
        genre_path = str(info.get("genre_path") or "")
        if not genre_path:
            continue
        path_tokens = tokenize(genre_path)
        overlap = weighted_tokens & path_tokens
        priority_overlap = {term for term in priority_terms if term and term in genre_path}
        if not overlap and not priority_overlap:
            continue
        score = 0.0
        for token in overlap:
            score += min(len(token), 12) * (2.0 if token in genre_path else 1.0)
        for term in priority_overlap:
            score += 80.0 + min(len(term), 12) * 5.0
        leaf_name = genre_path.split(">")[-1] if ">" in genre_path else genre_path
        leaf_overlap = weighted_tokens & tokenize(leaf_name)
        leaf_priority_overlap = {term for term in priority_terms if term and term in leaf_name}
        if leaf_overlap:
            score *= 1.5
        if leaf_priority_overlap:
            score += 60.0
        candidates.append(
            {
                "genre_id": int(genre_id),
                "score": round(score, 3),
                "genre_path": genre_path,
                "required_attributes": info.get("required_attributes", []),
                "matched_tokens": sorted(overlap | priority_overlap, key=lambda item: (-len(item), item))[:30],
                "leaf_matched_tokens": sorted(leaf_overlap, key=lambda item: (-len(item), item))[:30],
                "priority_terms": sorted(priority_overlap, key=lambda item: (-len(item), item))[:30],
            }
        )
    return sorted(candidates, key=lambda item: (-float(item["score"]), int(item["genre_id"])))


def select_genre_candidate(
    genre_path_candidates: list[dict[str, Any]],
    *,
    priority_terms: set[str],
) -> dict[str, Any] | None:
    if not genre_path_candidates:
        return None

    def find_by_leaf(needle: str) -> dict[str, Any] | None:
        for candidate in genre_path_candidates:
            leaf_name = str(candidate.get("genre_path") or "").split(">")[-1]
            if needle in leaf_name:
                return candidate
        return None

    def find_by_leaf_without_country(needle: str) -> dict[str, Any] | None:
        for candidate in genre_path_candidates:
            leaf_name = str(candidate.get("genre_path") or "").split(">")[-1]
            required = set(candidate.get("required_attributes") or [])
            if needle in leaf_name and "原産国／製造国" not in required:
                return candidate
        return None

    selected = None
    reason = "ジャンル一覧のスコア最上位を暫定選択"
    confidence = "low"
    if {"カイガラムシ", "園芸"} & priority_terms:
        selected = find_by_leaf("殺虫剤")
        reason = "園芸・カイガラムシ系の語があり、園芸薬剤の殺虫剤ジャンルを優先"
        confidence = "medium"
    elif {"コバエ", "バルサン"} & priority_terms:
        selected = find_by_leaf_without_country("殺虫剤") or find_by_leaf("虫除け器具") or find_by_leaf("虫除け芳香剤")
        reason = "コバエ・バルサン系の語があり、登録を止めにくい近似ジャンルを仮選択"
        confidence = "low"
    elif {"エアゾール", "スプレー"} & priority_terms:
        selected = find_by_leaf("殺虫スプレー") or find_by_leaf("虫除けスプレー")
        reason = "エアゾール・スプレー系の語があり、スプレー系ジャンルを優先"
        confidence = "medium"

    selected = selected or genre_path_candidates[0]
    return {
        "genre_id": selected.get("genre_id"),
        "genre_path": selected.get("genre_path"),
        "required_attributes": selected.get("required_attributes", []),
        "confidence": confidence,
        "selection_source": "rakuten_genre_path_similarity",
        "reason": reason,
        "review_required": True,
    }


def build_report(dry_run_json: Path, csv_files: list[Path], master_dir: Path, *, top: int) -> dict[str, Any]:
    payload = load_json(dry_run_json)
    keepa = payload.get("keepa_result") if isinstance(payload.get("keepa_result"), dict) else {}
    query_text = query_text_from_dry_run(payload)
    query_tokens = tokenize(query_text)
    priority_terms = extract_priority_terms(query_text)
    attribute_definitions = load_attribute_definitions(master_dir)
    genre_path_candidates = score_genre_path_candidates(
        query_tokens,
        attribute_definitions,
        priority_terms=priority_terms,
    )
    selected_candidate = select_genre_candidate(
        genre_path_candidates,
        priority_terms=priority_terms,
    )
    document_frequency, total_documents = build_document_frequency(csv_files)
    candidates = score_candidates(
        query_tokens,
        csv_files,
        document_frequency=document_frequency,
        total_documents=total_documents,
    )
    ranked = sorted(candidates.values(), key=lambda item: (-float(item["score"]), -int(item["match_count"]), int(item["genre_id"])))
    formatted = []
    for item in ranked[:top]:
        genre_id = int(item["genre_id"])
        attr_info = attribute_definitions.get(genre_id, {})
        formatted.append(
            {
                "genre_id": genre_id,
                "score": round(float(item["score"]), 3),
                "match_count": int(item["match_count"]),
                "genre_path": attr_info.get("genre_path", ""),
                "required_attributes": attr_info.get("required_attributes", []),
                "top_matched_tokens": [
                    {"token": token, "count": count}
                    for token, count in item["matched_tokens"].most_common(20)
                ],
                "examples": item["examples"],
            }
        )
    return {
        "dry_run_json": str(dry_run_json),
        "asin": payload.get("asin"),
        "unknown_category_id": keepa.get("category_id"),
        "keepa_category_tree": keepa.get("category_tree") or (keepa.get("raw_summary") or {}).get("category_tree") or [],
        "title": (payload.get("amazon_result") or {}).get("title") or keepa.get("title"),
        "candidate_source": "legacy RMS normal-item CSV title similarity",
        "csv_files": [str(path) for path in csv_files],
        "query_token_count": len(query_tokens),
        "priority_terms": sorted(priority_terms, key=lambda item: (-len(item), item)),
        "legacy_product_row_count": total_documents,
        "selected_candidate": selected_candidate,
        "genre_path_candidates": genre_path_candidates[:top],
        "candidates": formatted,
        "notes": [
            "This is a review aid only; do not add catlist_rakuten mapping automatically.",
            "Prefer confirming genreId with RMS/NavigationAPI before production use.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Suggest Rakuten genreId candidates for an unknown Keepa category.")
    parser.add_argument("--dry-run-json", required=True)
    parser.add_argument("--csv", action="append", default=[])
    parser.add_argument("--master-dir", default=str(DEFAULT_MASTER_DIR))
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--output-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_files = [Path(item) for item in args.csv] if args.csv else [Path(item) for item in DEFAULT_CSV_FILES]
    report = build_report(Path(args.dry_run_json), csv_files, Path(args.master_dir), top=max(1, int(args.top)))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
