"""Append verified cosmetic disclosures to existing Rakuten listings.

Only candidates with a saved listing dry-run, an exact-JAN Rakuten evidence
match, and a live RMS item/SKU are changed.  The default is read-only plan
generation; ``--execute`` sends the reviewed JSON PATCH payloads.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
PRICE_SYSTEM_ROOT = ROOT.parent / "price_system"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PRICE_SYSTEM_ROOT / "scripts"))

from scripts.db_config import connect_db
from scripts.listing.listing_evaluator import append_regulated_product_disclosure
from scripts.listing.rakuten_marketplace_policy import is_cosmetics_category
from scripts.listing.quasi_drug_compliance import lookup_japanese_regulated_product_evidence
from rakuten_auth import build_rakuten_auth_header


OUTPUT_DIR = ROOT / "output" / "compliance_updates"
ITEM_API_BASE = "https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers"
ATTRIBUTE_EVIDENCE_MAP = {
    "シリーズ名": "series_name",
    "ブランド名": "brand",
    "原産国／製造国": "country_of_origin",
}


def item_url(manage_number: str) -> str:
    return f"{ITEM_API_BASE}/{quote(manage_number, safe='')}"


def latest_saved_sources() -> dict[str, dict[str, Any]]:
    sources: dict[str, tuple[float, dict[str, Any]]] = {}
    for path in (ROOT / "output" / "listing" / "batches").glob("*/*/dry_run.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("store_code") or "") != "rakuten_2":
            continue
        asin = str(data.get("asin") or "").strip().upper()
        keepa = data.get("keepa_result") or {}
        if not asin or not isinstance(keepa, dict) or not is_cosmetics_category(keepa.get("category_tree")):
            continue
        modified = path.stat().st_mtime
        if asin not in sources or modified > sources[asin][0]:
            sources[asin] = (modified, {"path": str(path), "keepa": keepa})
    return {asin: source for asin, (_modified, source) in sources.items()}


def listed_products() -> list[dict[str, str]]:
    conn = connect_db(options="-c default_transaction_read_only=on")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.asin, sp.mall_item_code, COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code)
                FROM store_products sp
                JOIN stores s ON s.id = sp.store_id
                WHERE s.store_code = 'rakuten_2'
                  AND s.mall = 'rakuten'
                  AND sp.enabled = TRUE
                  AND COALESCE(sp.current_status, '') NOT IN ('deleted', 'delete_pending')
                  AND COALESCE(sp.mall_item_code, '') <> ''
                  AND COALESCE(sp.asin, '') <> ''
                ORDER BY sp.id
                """
            )
            return [
                {"asin": str(asin).strip().upper(), "manage_number": str(manage).strip(), "sku": str(sku).strip()}
                for asin, manage, sku in cur.fetchall()
            ]
    finally:
        conn.close()


def get_live_item(manage_number: str) -> dict[str, Any]:
    response = requests.get(item_url(manage_number), headers=build_rakuten_auth_header("rakuten_2"), timeout=45)
    response.raise_for_status()
    return response.json()


def normalized_attributes(variant: dict[str, Any]) -> list[dict[str, Any]]:
    attributes: list[dict[str, Any]] = []
    for item in list(variant.get("attributes") or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        values = [str(value).strip() for value in list(item.get("values") or []) if str(value).strip()]
        if name and values:
            attributes.append({"name": name, "values": values})
    return attributes


def merge_attributes(current: list[dict[str, Any]], evidence: dict[str, str]) -> list[dict[str, Any]]:
    merged = copy.deepcopy(current)
    by_name = {str(item.get("name") or ""): item for item in merged}
    for attr_name, evidence_key in ATTRIBUTE_EVIDENCE_MAP.items():
        value = str(evidence.get(evidence_key) or "").strip()
        if not value or value == "-":
            continue
        if attr_name in by_name:
            by_name[attr_name]["values"] = [value]
        else:
            entry = {"name": attr_name, "values": [value]}
            merged.append(entry)
            by_name[attr_name] = entry
    return merged


def build_patch(live_item: dict[str, Any], sku: str, evidence: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    variants = live_item.get("variants") or {}
    variant = variants.get(sku)
    if not isinstance(variant, dict):
        raise ValueError(f"RMS SKUが見つかりません: {sku}")
    description = live_item.get("productDescription") or {}
    pc = append_regulated_product_disclosure(str(description.get("pc") or ""), evidence)
    sp = append_regulated_product_disclosure(str(description.get("sp") or ""), evidence)
    current_attributes = normalized_attributes(variant)
    next_attributes = merge_attributes(current_attributes, evidence)
    changes: list[str] = []
    if pc != str(description.get("pc") or "") or sp != str(description.get("sp") or ""):
        changes.append("商品説明末尾に法定表示を追記")
    if next_attributes != current_attributes:
        changes.append("商品仕様のシリーズ名・ブランド名・原産国／製造国を修正")
    return {
        "productDescription": {"pc": pc, "sp": sp},
        "variants": {sku: {"attributes": next_attributes}},
    }, changes


def main() -> int:
    parser = argparse.ArgumentParser(description="店舗2の既存化粧品へ確認済み法定表示を追記する")
    parser.add_argument("--limit", type=int, default=0, help="対象上限。0は全件")
    parser.add_argument("--asin", default="", help="確認用に特定ASIN（カンマ区切り可）だけへ絞る")
    parser.add_argument("--execute", action="store_true", help="RMSへPATCHを送信する")
    parser.add_argument(
        "--search-api-only",
        action="store_true",
        help="商品ページを開かず楽天検索API本文だけで照合する（--execute時はRMSへ反映）",
    )
    parser.add_argument(
        "--audit-existing",
        action="store_true",
        help="RMSは読み取りだけで、広告文責の追記が必要な既存商品を一覧化する（--executeとは併用不可）",
    )
    parser.add_argument("--api-interval", type=float, default=1.5, help="RMS PATCH間隔（秒）")
    parser.add_argument("--lookup-interval", type=float, default=1.1, help="楽天検索・商品仕様照会の間隔（秒）")
    args = parser.parse_args()
    if args.limit < 0:
        raise SystemExit("--limit は0以上です")
    if args.audit_existing and args.execute:
        raise SystemExit("--audit-existing と --execute は併用できません")

    source_by_asin = latest_saved_sources()
    products = [product for product in listed_products() if product["asin"] in source_by_asin]
    requested_asins = {asin.strip().upper() for asin in str(args.asin or "").split(",") if asin.strip()}
    if requested_asins:
        products = [product for product in products if product["asin"] in requested_asins]
    if args.limit:
        products = products[:args.limit]
    plan: list[dict[str, Any]] = []
    for product in products:
        source = source_by_asin[product["asin"]]
        keepa = source["keepa"]
        source_text = " ".join(str(keepa.get(key) or "") for key in ("title", "description"))
        category = "医薬部外品" if "医薬部外品" in source_text else "化粧品"
        evidence = lookup_japanese_regulated_product_evidence(
            jan_code=str(keepa.get("ean") or ""),
            manufacturer=str(keepa.get("manufacturer") or ""),
            store_code="rakuten_2",
            category=category,
            fetch_product_spec=not args.search_api_only,
        ) or {}
        if not evidence:
            continue
        entry: dict[str, Any] = {**product, "source_dry_run": source["path"], "evidence": evidence}
        if args.search_api_only and not args.execute and not args.audit_existing:
            entry.update({"status": "search_api_matched"})
            plan.append(entry)
            time.sleep(max(args.lookup_interval, 0.0))
            continue
        try:
            live_item = get_live_item(product["manage_number"])
            payload, changes = build_patch(live_item, product["sku"], evidence)
            description_change = "商品説明末尾に法定表示を追記" in changes
            if args.audit_existing:
                # Do not retain a full patch body in the audit output: it is
                # enough for the operator to know precisely which fields are
                # missing, while avoiding a file full of existing descriptions.
                status = "disclosure_missing" if description_change else ("attribute_missing" if changes else "unchanged")
                entry.update(
                    {
                        "status": status,
                        "changes": changes,
                        "advertiser_disclosure_missing": description_change,
                    }
                )
            else:
                entry.update({"status": "ready" if changes else "unchanged", "changes": changes, "request_json": payload})
        except (requests.RequestException, ValueError) as exc:
            entry.update({"status": "error", "error": str(exc)})
        plan.append(entry)
        time.sleep(max(args.lookup_interval, 0.0))

    if args.execute:
        for entry in plan:
            if entry.get("status") != "ready":
                continue
            response = requests.patch(
                item_url(str(entry["manage_number"])),
                headers=build_rakuten_auth_header("rakuten_2"),
                json=entry["request_json"],
                timeout=60,
            )
            entry["response_status"] = response.status_code
            entry["status"] = "updated" if response.ok else "failed"
            if not response.ok:
                entry["response_body"] = response.text[:2000]
                # Some legacy listings contain an attribute name that RMS no
                # longer accepts.  Do not delete that merchant data merely to
                # append a disclosure: safely retry the description alone.
                if response.status_code == 400 and "IE1002" in response.text:
                    fallback = requests.patch(
                        item_url(str(entry["manage_number"])),
                        headers=build_rakuten_auth_header("rakuten_2"),
                        json={"productDescription": entry["request_json"]["productDescription"]},
                        timeout=60,
                    )
                    entry["fallback_response_status"] = fallback.status_code
                    if fallback.ok:
                        entry["status"] = "updated_description_only"
                        entry["attribute_update_skipped"] = "RMS rejected an existing legacy attribute name (IE1002)"
                    else:
                        entry["fallback_response_body"] = fallback.text[:2000]
            time.sleep(max(args.api_interval, 0.0))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"cosmetic_compliance_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps({"execute": args.execute, "search_api_only": args.search_api_only, "entries": plan}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved_sources": len(source_by_asin), "listed_candidates": len(products), "search_api_matched": sum(entry.get("status") == "search_api_matched" for entry in plan), "disclosure_missing": sum(entry.get("status") == "disclosure_missing" for entry in plan), "attribute_missing": sum(entry.get("status") == "attribute_missing" for entry in plan), "ready": sum(entry.get("status") == "ready" for entry in plan), "updated": sum(entry.get("status") == "updated" for entry in plan), "output": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
