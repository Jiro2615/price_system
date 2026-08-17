import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from db_config import connect_db
from rakuten_auth import build_rakuten_auth_header

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR.parent / ".env"
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_api"


def load_auth_header() -> dict[str, str]:
    load_dotenv(ENV_PATH)

    service_secret = os.getenv("RAKUTEN_1_SERVICE_SECRET", "").strip()
    license_key = os.getenv("RAKUTEN_1_LICENSE_KEY", "").strip()

    if not service_secret:
        raise RuntimeError(f"RAKUTEN_SERVICE_SECRET 驍ｵ・ｺ隶呵ｶ｣・ｽ・ｩ繝ｻ・ｺ驍ｵ・ｺ繝ｻ・ｧ驍ｵ・ｺ郢晢ｽｻ {ENV_PATH}")

    if not license_key:
        raise RuntimeError(f"RAKUTEN_LICENSE_KEY 驍ｵ・ｺ隶呵ｶ｣・ｽ・ｩ繝ｻ・ｺ驍ｵ・ｺ繝ｻ・ｧ驍ｵ・ｺ郢晢ｽｻ {ENV_PATH}")

    token_src = f"{service_secret}:{license_key}".encode("utf-8")
    token = base64.b64encode(token_src).decode("ascii")

    return {
        "Authorization": f"ESA {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def call_get(url: str, store_code: str) -> dict:
    headers = build_rakuten_auth_header(store_code)

    print(f"GET {url}")
    res = requests.get(url, headers=headers, timeout=60)
    print(f"status_code={res.status_code}")

    try:
        data = res.json()
    except Exception:
        data = {"_raw_text": res.text}

    if not (200 <= res.status_code < 300):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        raise RuntimeError(f"髫ｶ魃会ｽｽ・ｽ髯樊ｻゑｽｽ・ｩAPI驛｢・ｧ繝ｻ・ｨ驛｢譎｢・ｽ・ｩ驛｢譎｢・ｽ・ｼ status={res.status_code}")

    return data


def get_item(manage_number: str, store_code: str) -> tuple[str, dict]:
    encoded = quote(manage_number, safe="")
    url = f"https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/{encoded}"
    return url, call_get(url, store_code)


def get_inventory_variant(manage_number: str, sku_code: str, store_code: str) -> tuple[str, dict]:
    encoded_manage = quote(manage_number, safe="")
    encoded_sku = quote(sku_code, safe="")
    url = (
        "https://api.rms.rakuten.co.jp/es/2.1/"
        f"inventories/manage-numbers/{encoded_manage}/variants/{encoded_sku}"
    )
    return url, call_get(url, store_code)


def get_store_id(cur, store_code: str) -> int:
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
        raise RuntimeError(f"髫ｶ魃会ｽｽ・ｽ髯樊ｻゑｽｽ・ｩ髯滓焔謖咏ｹ晢ｽｻ驍ｵ・ｺ霑ｹ螟ｲ・ｽ・ｦ闕ｵ譏ｶ蜻ｽ驍ｵ・ｺ闕ｵ譎｢・ｽ鬘費ｽｸ・ｺ繝ｻ・ｾ驍ｵ・ｺ陝ｶ蜻ｻ・ｽ繝ｻ {store_code}")
    return int(row[0])


def save_snapshot(
    cur,
    store_id: int,
    manage_number: str,
    sku_code: str | None,
    api_name: str,
    request_url: str,
    response_json: dict,
) -> None:
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
            manage_number,
            sku_code,
            api_name,
            request_url,
            json.dumps(response_json, ensure_ascii=False),
        ),
    )


def extract_standard_price(item_data: dict, sku_code: str) -> int | None:
    variants = item_data.get("variants") or {}
    variant = variants.get(sku_code)

    if not variant:
        return None

    value = variant.get("standardPrice")
    if value is None or value == "":
        return None

    return int(float(str(value)))


def extract_item_name(item_data: dict) -> str:
    return str(item_data.get("title") or "")


def extract_quantity(inv_data: dict) -> int | None:
    value = inv_data.get("quantity")
    if value is None or value == "":
        return None
    return int(float(str(value)))


def update_store_product(
    cur,
    store_id: int,
    manage_number: str,
    sku_code: str,
    item_name: str,
    current_price: int | None,
    current_stock: int | None,
) -> int:
    cur.execute(
        """
        UPDATE store_products
        SET
            item_name = %s,
            current_price = COALESCE(%s, current_price),
            current_stock = COALESCE(%s, current_stock),
            current_status = 'synced',
            api_last_synced_at = CURRENT_TIMESTAMP,
            api_last_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE store_id = %s
          AND mall_item_code = %s
          AND COALESCE(sku_code, '') = COALESCE(%s, '')
        """,
        (
            item_name,
            current_price,
            current_stock,
            store_id,
            manage_number,
            sku_code,
        ),
    )
    return cur.rowcount


def mark_sync_error(
    cur,
    store_id: int,
    manage_number: str,
    sku_code: str,
    error_message: str,
) -> None:
    cur.execute(
        """
        UPDATE store_products
        SET
            api_last_error = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE store_id = %s
          AND mall_item_code = %s
          AND COALESCE(sku_code, '') = COALESCE(%s, '')
        """,
        (
            error_message,
            store_id,
            manage_number,
            sku_code,
        ),
    )


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
    parser = argparse.ArgumentParser(description="Rakuten APIから1商品/SKUの現在価格・在庫を取得してDBへ反映します。")
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--manage-number", required=True, help="楽天商品管理番号")
    parser.add_argument("--sku", required=True, help="楽天SKU管理番号")
    args = parser.parse_args()

    store_code = args.store.strip()
    manage_number = args.manage_number.strip()
    sku_code = args.sku.strip()

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            store_id = get_store_id(cur, store_code)

        try:
            item_url, item_data = get_item(manage_number, store_code)
            inv_url, inv_data = get_inventory_variant(manage_number, sku_code, store_code)

            item_path = write_json_file("items_get", manage_number, None, item_data)
            inv_path = write_json_file("inventories_variants_get", manage_number, sku_code, inv_data)

            item_name = extract_item_name(item_data)
            current_price = extract_standard_price(item_data, sku_code)
            current_stock = extract_quantity(inv_data)

            print("")
            print("髯ｷ・ｿ鬮｢ﾂ繝ｻ・ｾ隲､諷環繝ｻ・､:")
            print(f"  髯懶｣ｰ郢晢ｽｻ陋ｻﾂ髯ｷ・ｷ郢晢ｽｻ     : {item_name}")
            print(f"  髴托ｽｴ繝ｻ・ｾ髯懶ｽｨ繝ｻ・ｨ髣憺屮・ｽ・｡髫ｴ・ｬ繝ｻ・ｼ    : {current_price}")
            print(f"  髴托ｽｴ繝ｻ・ｾ髯懶ｽｨ繝ｻ・ｨ髯懶ｽｨ繝ｻ・ｨ髯溯ｶ｣・ｽ・ｫ    : {current_stock}")
            print(f"  item JSON   : {item_path}")
            print(f"  stock JSON  : {inv_path}")
            print("")

            with conn.cursor() as cur:
                save_snapshot(
                    cur,
                    store_id,
                    manage_number,
                    None,
                    "items.get",
                    item_url,
                    item_data,
                )
                save_snapshot(
                    cur,
                    store_id,
                    manage_number,
                    sku_code,
                    "inventories.variants.get",
                    inv_url,
                    inv_data,
                )

                updated_count = update_store_product(
                    cur,
                    store_id=store_id,
                    manage_number=manage_number,
                    sku_code=sku_code,
                    item_name=item_name,
                    current_price=current_price,
                    current_stock=current_stock,
                )

            conn.commit()

            if updated_count == 0:
                print("注意: store_products に該当行がありませんでした。")
                print("先に store_products へ manage_number / sku / ASIN の対応を登録してください。")
            else:
                print(f"DB更新完了: store_products updated={updated_count}")

        except Exception as e:
            with conn.cursor() as cur:
                store_id = get_store_id(cur, store_code)
                mark_sync_error(cur, store_id, manage_number, sku_code, str(e))
            conn.commit()
            raise

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
