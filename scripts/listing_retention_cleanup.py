from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.db_config import connect_db


ROOT_DIR = Path(__file__).resolve().parents[1]
LISTING_OUTPUT_DIR = ROOT_DIR / "output" / "listing"
CATEGORIES = (
    {
        "key": "listing_batches",
        "label": "出品バッチの詳細JSON",
        "root": LISTING_OUTPUT_DIR / "batches",
        "default_days": 30,
    },
    {
        "key": "listing_images",
        "label": "出品用に取得した画像",
        "root": ROOT_DIR / "output" / "listing_images",
        "default_days": 14,
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview or remove expired local listing artifacts.")
    parser.add_argument("--mode", choices=("preview", "execute"), default="preview")
    parser.add_argument("--listing-batches-days", type=int, default=30)
    parser.add_argument("--listing-images-days", type=int, default=14)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--confirm-delete", action="store_true")
    return parser.parse_args()


def active_listing_run_ids() -> set[str]:
    """Fail closed when the shared DB cannot prove which listing runs are inactive."""
    node_code = str(os.getenv("PRICE_SYSTEM_NODE_CODE") or os.getenv("WEB_ORCHESTRATOR_NODE_CODE") or "").strip().lower()
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id
                FROM job_runs
                WHERE job_type IN ('listing_bulk_dry_run', 'listing_bulk_execute', 'listing_retention_preview', 'listing_retention_cleanup')
                  AND (status NOT IN ('succeeded', 'failed', 'cancelled') OR desired_state <> 'stopped')
                  AND (%s = '' OR LOWER(COALESCE(execution_node_code, '')) = %s)
                """,
                (node_code, node_code),
            )
            return {str(row[0]) for row in cur.fetchall() if str(row[0] or "")}
    finally:
        conn.close()


def validate_days(value: int, key: str) -> int:
    if value < 1 or value > 3650:
        raise ValueError(f"{key} must be between 1 and 3650")
    return value


def category_days(args: argparse.Namespace) -> dict[str, int]:
    return {
        "listing_batches": validate_days(args.listing_batches_days, "listing-batches-days"),
        "listing_images": validate_days(args.listing_images_days, "listing-images-days"),
    }


def candidate_run_id(category_key: str, root: Path, candidate: Path) -> str:
    if category_key != "listing_batches":
        return ""
    relative = candidate.relative_to(root)
    return relative.parts[0] if relative.parts else ""


def build_preview(days_by_key: dict[str, int], *, active_run_ids: set[str], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    categories: list[dict[str, Any]] = []
    total_count = 0
    total_bytes = 0
    listing_run_active = bool(active_run_ids)
    for category in CATEGORIES:
        key = str(category["key"])
        root = Path(category["root"])
        cutoff = now - timedelta(days=days_by_key[key])
        candidates: list[Path] = []
        skipped_active = 0
        if root.is_dir():
            for candidate in root.rglob("*"):
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                try:
                    modified_at = datetime.fromtimestamp(candidate.stat().st_mtime, timezone.utc)
                except OSError:
                    continue
                if modified_at > cutoff:
                    continue
                run_id = candidate_run_id(key, root, candidate)
                # A run's raw JSON is required for recovery until its run has
                # reached a terminal status.  Images lack a run-id relation,
                # so keep all expired images while any listing process is live.
                if (run_id and run_id in active_run_ids) or (key == "listing_images" and listing_run_active):
                    skipped_active += 1
                    continue
                candidates.append(candidate)
        byte_count = 0
        samples: list[dict[str, Any]] = []
        for candidate in candidates:
            try:
                size = candidate.stat().st_size
            except OSError:
                continue
            byte_count += size
            if len(samples) < 100:
                samples.append({"path": str(candidate.relative_to(root)), "bytes": size})
        categories.append(
            {
                "key": key,
                "label": category["label"],
                "root": str(root),
                "retention_days": days_by_key[key],
                "candidate_count": len(candidates),
                "candidate_bytes": byte_count,
                "skipped_active_count": skipped_active,
                "sample_files": samples,
            }
        )
        total_count += len(candidates)
        total_bytes += byte_count
    return {
        "scope": "listing_execution_node_local",
        "dry_run": True,
        "active_listing_run_ids": sorted(active_run_ids),
        "candidate_count": total_count,
        "candidate_bytes": total_bytes,
        "categories": categories,
        "note": "execution_history is intentionally retained because it prevents duplicate listings and supports resume after image upload.",
    }


def execute_cleanup(days_by_key: dict[str, int], *, active_run_ids: set[str]) -> dict[str, Any]:
    preview = build_preview(days_by_key, active_run_ids=active_run_ids)
    removed_count = 0
    removed_bytes = 0
    errors: list[dict[str, str]] = []
    by_key = {str(category["key"]): category for category in CATEGORIES}
    now = datetime.now(timezone.utc)
    for category in preview["categories"]:
        key = str(category["key"])
        root = Path(by_key[key]["root"])
        cutoff = now - timedelta(days=days_by_key[key])
        for candidate in root.rglob("*") if root.is_dir() else []:
            if not candidate.is_file() or candidate.is_symlink():
                continue
            try:
                modified_at = datetime.fromtimestamp(candidate.stat().st_mtime, timezone.utc)
                if modified_at > cutoff:
                    continue
                run_id = candidate_run_id(key, root, candidate)
                if (run_id and run_id in active_run_ids) or (key == "listing_images" and active_run_ids):
                    continue
                size = candidate.stat().st_size
                candidate.unlink()
                removed_count += 1
                removed_bytes += size
            except OSError as exc:
                errors.append({"path": str(candidate), "error": str(exc)})
    return {"ok": not errors, "removed_count": removed_count, "removed_bytes": removed_bytes, "errors": errors[:100], "preview": preview}


def main() -> int:
    args = parse_args()
    if args.mode == "execute" and not args.confirm_delete:
        raise ValueError("--confirm-delete is required with --mode execute")
    days_by_key = category_days(args)
    active_run_ids = active_listing_run_ids()
    active_run_ids.discard(str(args.run_id or "").strip())
    result = execute_cleanup(days_by_key, active_run_ids=active_run_ids) if args.mode == "execute" else build_preview(days_by_key, active_run_ids=active_run_ids)
    result["mode"] = args.mode
    stdout_result = json.loads(json.dumps(result))
    for category in stdout_result.get("categories") or []:
        if isinstance(category, dict):
            category["sample_files"] = list(category.get("sample_files") or [])[:10]
    print("LISTING_RETENTION_SUMMARY " + json.dumps(stdout_result, ensure_ascii=False), flush=True)
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
