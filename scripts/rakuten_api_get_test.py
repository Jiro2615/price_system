import argparse
import json
import os
import base64
from pathlib import Path
from urllib.parse import quote

import psycopg
import requests
from dotenv import load_dotenv


BASE_DIR = Path(r"C:\price_system")
ENV_PATH = BASE_DIR / ".env"
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_api"

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "price_system"
DB_USER = "price_app"
DB_PASSWORD = "price_app_2026"  # 自分の price_app パスワードに合わせる


def load_auth_header() -> dict[str, str]:
    load_dotenv(ENV_PATH)

    service_secret = os.getenv("RAKUTEN_SERVICE_SECRET", "").strip()
    license_key = os.getenv("RAKUTEN_LICENSE_KEY", "").strip()

    if not service_secret:
        raise RuntimeError(f"RAKUTEN_SERVICE_SECRET が空です: {ENV_PATH}")

    if not license_key:
        raise RuntimeError(f"RAKUTEN_LICENSE_KEY が空です: {ENV_PATH}")

    token_src = f"{service_secret}:{license_key}".encode("utf-8")
    token = base64.b64encode(token_src).decode("ascii")

    return {
        "Authorization": f"ESA {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def get_store_id(store_code: str) -> int:
    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM stores
                WHERE mall = 'rakuten'
                  AND store_code = %s
                """,
                (store_code,),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"楽天店舗が見つかりません: {store_code}")
            return int(row[0])
    finally:
        conn.close()


def save_snapshot(
    store_id: int,
    mall_item_code: str,
    sku_code: str | None,
    api_name: str,
    request_url: str,
    response_json: dict,
) -> None:
    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rakuten_api_snapshots (
                    store_id,
                    mall_item_code,
                    sku_code,
                    api_name,
                    request_url,
                    response_json
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    store_id,
                    mall_item_code,
                    sku_code,
                    api_name,
                    request_url,
                    json.dumps(response_json, ensure_ascii=False),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def call_get(url: str) -> dict:
    headers = load_auth_header()

    print(f"GET {url}")

    res = requests.get(url, headers=headers, timeout=60)

    print(f"status_code={res.status_code}")

    try:
        data = res.json()
    except Exception:
        data = {
            "_raw_text": res.text,
        }

    if res.status_code < 200 or res.status_code >= 300:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        raise RuntimeError(f"楽天APIエラー status={res.status_code}")

    return data


def get_item(manage_number: str) -> tuple[str, dict]:
    encoded_manage_number = quote(manage_number, safe="")
    url = f"https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/{encoded_manage_number}"
    return url, call_get(url)


def get_inventory_variant(manage_number: str, sku_code: str) -> tuple[str, dict]:
    encoded_manage_number = quote(manage_number, safe="")
    encoded_sku_code = quote(sku_code, safe="")
    url = (
        "https://api.rms.rakuten.co.jp/es/2.1/"
        f"inventories/manage-numbers/{encoded_manage_number}/variants/{encoded_sku_code}"
    )
    return url, call_get(url)


def write_json_file(prefix: str, manage_number: str, sku_code: str | None, data: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_manage = manage_number.replace("/", "_").replace("\\", "_")
    safe_sku = (sku_code or "").replace("/", "_").replace("\\", "_")

    if sku_code:
        path = OUTPUT_DIR / f"{prefix}_{safe_manage}_{safe_sku}.json"
    else:
        path = OUTPUT_DIR / f"{prefix}_{safe_manage}.json"

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天API items.get / inventories.variants.get の読み取りテスト")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--manage-number", required=True, help="楽天商品管理番号")
    parser.add_argument("--sku", default="", help="楽天SKU管理番号。指定時は在庫APIも取得")
    args = parser.parse_args()

    store_id = get_store_id(args.store)
    manage_number = args.manage_number.strip()
    sku_code = args.sku.strip() or None

    item_url, item_data = get_item(manage_number)
    item_path = write_json_file("items_get", manage_number, None, item_data)
    save_snapshot(
        store_id=store_id,
        mall_item_code=manage_number,
        sku_code=None,
        api_name="items.get",
        request_url=item_url,
        response_json=item_data,
    )

    print(f"items.get 保存: {item_path}")

    if sku_code:
        inv_url, inv_data = get_inventory_variant(manage_number, sku_code)
        inv_path = write_json_file("inventories_variants_get", manage_number, sku_code, inv_data)
        save_snapshot(
            store_id=store_id,
            mall_item_code=manage_number,
            sku_code=sku_code,
            api_name="inventories.variants.get",
            request_url=inv_url,
            response_json=inv_data,
        )

        print(f"inventories.variants.get 保存: {inv_path}")

    print("楽天API読み取りテスト完了")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())