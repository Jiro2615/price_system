from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = BASE_DIR / "output" / "diagnostics" / "store2_amazon_chrome_phrase_probe.jsonl"
DEFAULT_CSV = BASE_DIR / "output" / "diagnostics" / "store2_cosmetic_permission_candidates.csv"
DEFAULT_JSON = BASE_DIR / "output" / "diagnostics" / "store2_cosmetic_permission_candidates.json"
COSMETIC_WORDS = ("化粧", "美容", "クリーム", "ローション", "乳液", "リップ", "クレンジング", "洗顔", "スキン", "ボディケア")
SENSITIVE_WORDS = ("医療", "医薬", "薬", "コンドーム", "性", "育毛", "殺菌", "除菌", "アルコール", "治療", "効能", "効果")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review-only list of cosmetic candidates blocked by listing words.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--limit", type=int, default=200)
    return parser.parse_args()


def risk_level(words: list[str]) -> str:
    return "high" if any(any(marker in word for marker in SENSITIVE_WORDS) for word in words) else "review"


def build_records(path: Path) -> list[dict[str, object]]:
    latest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("result_kind") == "result" and row.get("asin"):
                latest[str(row["asin"])] = row

    records: list[dict[str, object]] = []
    for asin, row in latest.items():
        title = str(row.get("title") or "")
        amazon = dict(row.get("amazon_check") or {})
        matches = list(row.get("matched_forbidden_words") or [])
        words = sorted({str(match.get("word") or "") for match in matches if str(match.get("word") or "")})
        if not any(word in title for word in COSMETIC_WORDS):
            continue
        if not words or amazon.get("system_error") or not amazon.get("amazon_price") or not amazon.get("available_qty"):
            continue
        records.append({
            "asin": asin,
            "title": title,
            "amazon_price": amazon.get("amazon_price"),
            "available_qty": amazon.get("available_qty"),
            "shipping_status": str(amazon.get("shipping_status") or ""),
            "blocked_words": " / ".join(words),
            "blocked_word_count": len(words),
            "risk": risk_level(words),
            "next_step": "個別許可の可否を確認後に、最新の完全ドライランを再実行",
            "scanned_at": row.get("checked_at"),
        })
    return sorted(records, key=lambda item: (item["risk"] == "high", item["blocked_word_count"], -int(item["amazon_price"])))


def main() -> int:
    args = parse_args()
    records = build_records(args.input)[: args.limit]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]) if records else ["asin", "title", "amazon_price", "available_qty", "shipping_status", "blocked_words", "blocked_word_count", "risk", "next_step", "scanned_at"])
        writer.writeheader()
        writer.writerows(records)
    args.output_json.write_text(json.dumps({"mode": "review_only", "record_count": len(records), "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"records={len(records)} csv={args.output_csv} json={args.output_json}")
    for record in records[:20]:
        line = f"{record['risk']}\t{record['asin']}\t{record['amazon_price']}\t{record['blocked_words']}\t{record['title']}"
        print(line.encode("cp932", errors="replace").decode("cp932"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
