from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.listing.models import sanitize_for_output, to_jsonable
from scripts.listing.rakuten_transport import rakuten_auth_env_status
from scripts.listing.store_config import get_store_cabinet_config, get_store_settings


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_DIR = BASE_DIR / "reference" / "legacy_listing"
DEFAULT_OUTPUT_JSON = BASE_DIR / "output" / "listing" / "store_readiness.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check store-scoped Rakuten listing readiness without API or DB writes.")
    parser.add_argument("--store", required=True, help="stores.store_code, such as rakuten_2")
    parser.add_argument("--master-dir", default=str(DEFAULT_MASTER_DIR))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    return parser.parse_args()


def check_store_settings(store_code: str) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    try:
        settings = get_store_settings(store_code)
    except Exception as exc:
        return {"configured": False, "error": str(exc)}, [f"store settings are not loadable: {exc}"]

    summary = {
        "configured": True,
        "store_code": settings.store_code,
        "store_id": settings.store_id,
        "store_name": settings.store_name,
        "max_stock": settings.max_stock,
        "fee_rate": settings.fee_rate,
        "profit_mode": settings.profit_mode,
        "profit_rate": settings.profit_rate,
        "profit_amount": settings.profit_amount,
        "fixed_cost": settings.fixed_cost,
        "rounding_unit": settings.rounding_unit,
        "ship_from_ids": settings.ship_from_ids,
        "listing_image_limit": settings.listing_image_limit,
    }
    if settings.max_stock < 0:
        reasons.append("max_stock must be zero or greater")
    if not settings.ship_from_ids:
        reasons.append("ship_from_ids is empty")
    if settings.rounding_unit < 1:
        reasons.append("rounding_unit must be one or greater")
    return summary, reasons


def check_master_dir(master_dir: Path) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    existing = master_dir.exists() and master_dir.is_dir()
    summary = {
        "path": str(master_dir),
        "exists": existing,
    }
    if not existing:
        reasons.append(f"master_dir does not exist: {master_dir}")
    return summary, reasons


def build_readiness(store_code: str, master_dir: Path) -> dict[str, Any]:
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    auth = rakuten_auth_env_status(store_code)
    if not auth.get("configured"):
        blocking_reasons.append("store-scoped Rakuten API credentials are missing")

    cabinet = get_store_cabinet_config(store_code)
    if not cabinet:
        blocking_reasons.append("store-scoped Cabinet config is missing")

    store_settings, setting_reasons = check_store_settings(store_code)
    blocking_reasons.extend(setting_reasons)

    master_summary, master_reasons = check_master_dir(master_dir)
    warnings.extend(master_reasons)

    result = {
        "store_code": store_code,
        "readiness_status": "ready" if not blocking_reasons else "blocked",
        "ready_for_listing_prepare": not blocking_reasons,
        "ready_for_real_listing_execute": not blocking_reasons and master_summary["exists"],
        "api_write_performed": False,
        "db_write_performed": False,
        "checks": {
            "auth": auth,
            "cabinet": {
                "configured": bool(cabinet),
                "folder_id": cabinet.get("folder_id") if cabinet else None,
                "folder_name": cabinet.get("folder_name") if cabinet else "",
                "folder_path": cabinet.get("folder_path") if cabinet else "",
                "shop_url": cabinet.get("shop_url") if cabinet else "",
                "folder_node": cabinet.get("folder_node") if cabinet else None,
            },
            "store_settings": store_settings,
            "master_dir": master_summary,
        },
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
    }
    return sanitize_for_output(result)


def main() -> int:
    args = parse_args()
    result = build_readiness(args.store.strip(), Path(args.master_dir))
    text = json.dumps(to_jsonable(result), ensure_ascii=False, indent=2)
    print(text)
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
