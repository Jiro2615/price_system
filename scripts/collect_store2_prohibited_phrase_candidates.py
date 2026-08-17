from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.keepa_product_client import KeepaClient, load_keepa_api_key
from scripts.listing.listing_evaluator import _build_descriptions, apply_cleanup_replacements
from scripts.listing.master_loader import apply_store_allowed_phrase_overrides, load_master_data
from scripts.listing.prohibited_word_masking import analyze_prohibited_word_issues
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_DIR = BASE_DIR / "reference" / "legacy_listing"
DEFAULT_OUTPUT_JSONL = BASE_DIR / "output" / "diagnostics" / "store2_prohibited_phrase_probe.jsonl"
ASIN_PATTERN = re.compile(r"\bB[0-9A-Z]{9}\b")
SECRET_QUERY_PATTERN = re.compile(r"([?&]key=)[^&\s]+", re.IGNORECASE)

# These are review labels only. They never alter the store's allow-list.
EXCLUDE_USER_POLICY_WORDS = {
    "性感", "並行", "輸入", "代理", "代理店", "コーセー", "シャネル",
    "医療", "医療機器", "商標", "登録", "医薬部外品", "部外品",
}
EXCLUDE_BRAND_WORDS = {
    "BAND-AID", "BREE", "BREEZE", "CHANEL", "ETVOS", "KOSE", "ORBIS",
    "SHIRORU", "アルビオン", "エトヴォス", "オルビス", "コスメア", "ソフィ",
    "デルガード", "ネクスケア", "バイオペースト", "バンドエイド", "ペリカン石鹸",
    "メディプラス", "小林製薬", "白十字",
}
SENSITIVE_REVIEW_WORDS = {
    "アンチエイジング", "ガン", "コンドーム", "快感", "管理医療機器",
    "医療用", "育毛", "育毛剤", "下着", "男性用", "検査", "高圧ガス",
    "膣", "膣洗浄器", "恋するおしり", "特許", "農薬", "肌荒れを防ぐ", "シワ",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Rakuten store 2 prohibited-word contexts from ASINs. This only runs listing dry-runs."
    )
    parser.add_argument("--asin-file", required=True, help="Text file containing ASINs in any layout.")
    parser.add_argument("--max-items", type=int, default=25, help="Maximum new ASINs to inspect in this run (default: 25).")
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_JSONL))
    parser.add_argument("--summary-json", default="", help="Defaults beside --output-jsonl.")
    parser.add_argument("--master-dir", default=str(DEFAULT_MASTER_DIR))
    parser.add_argument("--page-timeout", type=int, default=15000)
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=3,
        help="Stop the batch after this many consecutive failed ASINs (default: 3).",
    )
    parser.add_argument(
        "--scan-mode",
        choices=("keepa", "full-listing"),
        default="keepa",
        help="keepa scans title and description only; full-listing also runs the Amazon eligibility check.",
    )
    parser.add_argument(
        "--allow-missing-master",
        action="store_true",
        help="Continue when a nonessential legacy master file is absent. The result retains the missing-file warning.",
    )
    parser.add_argument("--retry-errors", action="store_true", help="Retry records that previously ended in an error.")
    parser.add_argument("--summary-only", action="store_true", help="Rebuild the classification summary without calling Keepa.")
    parser.add_argument("--redact-existing-errors", action="store_true", help="Mask API keys from previously saved error messages.")
    return parser.parse_args()


def read_unique_asins(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    seen: set[str] = set()
    values: list[str] = []
    for match in ASIN_PATTERN.finditer(text.upper()):
        asin = match.group(0)
        if asin not in seen:
            seen.add(asin)
            values.append(asin)
    return values


def read_completed_asins(path: Path, *, retry_errors: bool) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        asin = record.get("asin")
        if not isinstance(asin, str):
            continue
        if retry_errors and record.get("result_kind") == "error":
            continue
        completed.add(asin)
    return completed


def result_title(result: dict[str, object]) -> str:
    for key in ("amazon_result", "keepa_result"):
        value = result.get(key)
        title = getattr(value, "title", "")
        if isinstance(title, str) and title:
            return title
    return ""


def serialize_matches(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def sanitize_error_message(value: object) -> str:
    return SECRET_QUERY_PATTERN.sub(r"\1[REDACTED]", str(value))


def redact_existing_errors(path: Path) -> int:
    if not path.exists():
        return 0
    updated_lines: list[str] = []
    changed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            updated_lines.append(line)
            continue
        if isinstance(record, dict) and "error" in record:
            sanitized = sanitize_error_message(record["error"])
            if record["error"] != sanitized:
                record["error"] = sanitized
                changed += 1
        updated_lines.append(json.dumps(record, ensure_ascii=False))
    if changed:
        path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return changed


def build_record(asin: str, result: dict[str, object]) -> dict[str, object]:
    return {
        "asin": asin,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "result_kind": "result",
        "listing_status": str(result.get("listing_status") or ""),
        "listing_reason": str(result.get("listing_reason") or ""),
        "title": result_title(result),
        "matched_forbidden_words": serialize_matches(result.get("matched_forbidden_words")),
        "allowed_phrase_matches": serialize_matches(result.get("allowed_phrase_matches")),
    }


def build_keepa_record(asin: str, master_data: Any, keepa_client: KeepaClient) -> dict[str, object]:
    keepa_result = keepa_client.fetch_product(asin)
    title, _title_replacements = apply_cleanup_replacements(keepa_result.title, master_data.cleanup_replacements)
    description_pc, description_sp = _build_descriptions(title, keepa_result)
    description_pc, _pc_replacements = apply_cleanup_replacements(description_pc, master_data.cleanup_replacements)
    description_sp, _sp_replacements = apply_cleanup_replacements(description_sp, master_data.cleanup_replacements)
    analysis = analyze_prohibited_word_issues(
        {
            "title": title,
            "description_pc": description_pc,
            "description_sp": description_sp,
        },
        list(master_data.prohibited_words_rakuten) + list(master_data.prohibited_words_other),
        master_data.allowed_phrase_rules,
        separate_check_rules=master_data.allowed_phrase_separate_checks,
    )
    return {
        "asin": asin,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "result_kind": "result",
        "scan_mode": "keepa",
        "listing_status": "content_scanned",
        "listing_reason": "",
        "title": title,
        "matched_forbidden_words": serialize_matches(analysis["matched_forbidden_words"]),
        "allowed_phrase_matches": serialize_matches(analysis["allowed_phrase_matches"]),
    }


def write_summary(path: Path, records: list[dict[str, Any]], total_asins: int) -> None:
    word_counts: Counter[str] = Counter()
    contexts: dict[str, list[dict[str, str]]] = defaultdict(list)
    status_counts: Counter[str] = Counter()
    for record in records:
        if record.get("result_kind") == "result":
            status_counts[str(record.get("listing_status") or "unknown")] += 1
        for match in record.get("matched_forbidden_words") or []:
            if not isinstance(match, dict):
                continue
            word = str(match.get("word") or "")
            if not word:
                continue
            word_counts[word] += 1
            sample = {
                "asin": str(record.get("asin") or ""),
                "title": str(record.get("title") or ""),
                "field": str(match.get("field") or ""),
                "context": str(match.get("context") or ""),
            }
            if sample not in contexts[word] and len(contexts[word]) < 30:
                contexts[word].append(sample)

    payload = {
        "scope": "rakuten_2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_asin_count": total_asins,
        "completed_count": len(records),
        "result_status_counts": dict(sorted(status_counts.items())),
        "forbidden_word_counts": dict(word_counts.most_common()),
        "review_contexts_by_forbidden_word": dict(sorted(contexts.items())),
        "classification_by_forbidden_word": {
            word: {
                "classification": classify_forbidden_word(word),
                "occurrences": word_counts[word],
                "samples": contexts[word],
            }
            for word in sorted(word_counts)
        },
        "note": "Contexts are evidence for a manual allow-phrase decision. Add only curated ingredient or neutral exact phrases; never add brands, medical or efficacy claims, adult terms, regulated goods, or shipping/sales expressions automatically.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def classify_forbidden_word(word: str) -> str:
    if word in EXCLUDE_USER_POLICY_WORDS:
        return "exclude_user_policy"
    if word in EXCLUDE_BRAND_WORDS:
        return "exclude_brand_name"
    if word in SENSITIVE_REVIEW_WORDS:
        return "review_sensitive_or_claim"
    return "phrase_context_review"


def read_latest_records(path: Path) -> list[dict[str, Any]]:
    latest_by_asin: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        asin = item.get("asin") if isinstance(item, dict) else None
        if isinstance(asin, str):
            latest_by_asin[asin] = item
    return list(latest_by_asin.values())


def main() -> int:
    args = parse_args()
    if args.max_items <= 0 or args.max_consecutive_errors <= 0:
        print("--max-items and --max-consecutive-errors must be greater than 0", file=sys.stderr)
        return 2

    asin_file = Path(args.asin_file)
    output_path = Path(args.output_jsonl)
    summary_path = Path(args.summary_json) if args.summary_json else output_path.with_name(output_path.stem + "_summary.json")
    asins = read_unique_asins(asin_file)
    if args.redact_existing_errors:
        changed = redact_existing_errors(output_path)
        print(f"Redacted saved error records: {changed}")
        write_summary(summary_path, read_latest_records(output_path), len(asins))
        return 0
    if args.summary_only:
        write_summary(summary_path, read_latest_records(output_path), len(asins))
        print(f"Rebuilt review summary: {summary_path}")
        return 0
    completed = read_completed_asins(output_path, retry_errors=args.retry_errors)
    pending = [asin for asin in asins if asin not in completed]
    selected = pending[: args.max_items]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    master_data = None
    keepa_client = None
    if args.scan_mode == "keepa":
        try:
            master_data = load_master_data(Path(args.master_dir), allow_missing=args.allow_missing_master)
            master_data = apply_store_allowed_phrase_overrides(master_data, Path(args.master_dir), "rakuten_2")
            keepa_client = KeepaClient(api_key=load_keepa_api_key())
        except Exception as exc:
            print(f"initialization error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

    print(
        f"ASINs: total={len(asins)} completed={len(completed)} pending={len(pending)} "
        f"selected={len(selected)} mode={args.scan_mode}"
    )
    consecutive_errors = 0
    with output_path.open("a", encoding="utf-8", newline="\n") as handle:
        for position, asin in enumerate(selected, start=1):
            try:
                if args.scan_mode == "keepa":
                    if master_data is None or keepa_client is None:
                        raise RuntimeError("Keepa scan was not initialized")
                    record = build_keepa_record(asin, master_data, keepa_client)
                else:
                    result = prepare_listing(
                        PrepareListingRequest(
                            asin=asin,
                            store_code="rakuten_2",
                            master_dir=Path(args.master_dir),
                            dry_run=True,
                            allow_missing_master=args.allow_missing_master,
                            page_timeout_ms=args.page_timeout,
                        )
                    )
                    record = build_record(asin, result)
                    record["scan_mode"] = "full-listing"
            except Exception as exc:
                record = {
                    "asin": asin,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "result_kind": "error",
                    "error": sanitize_error_message(f"{type(exc).__name__}: {exc}"),
                    "matched_forbidden_words": [],
                    "allowed_phrase_matches": [],
                }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"[{position}/{len(selected)}] {asin}: {record.get('listing_status') or record.get('result_kind')}")
            if record.get("result_kind") == "error":
                consecutive_errors += 1
                if consecutive_errors >= args.max_consecutive_errors:
                    print(f"Stopping after {consecutive_errors} consecutive errors. Retry later with --retry-errors.")
                    break
            else:
                consecutive_errors = 0

    write_summary(summary_path, read_latest_records(output_path), len(asins))
    print(f"Saved probe results: {output_path}")
    print(f"Saved review summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
