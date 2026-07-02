from datetime import datetime

from db_config import connect_db

TEST_ASIN = "B000TEST01"


def main():
    print("DB接続テスト開始")

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user;")
            db_name, user_name = cur.fetchone()
            print(f"接続OK: database={db_name}, user={user_name}")

            cur.execute(
                """
                INSERT INTO amazon_products (
                    asin,
                    title,
                    amazon_price,
                    amazon_point,
                    available_qty,
                    gift_available,
                    shipping_status,
                    business_ng,
                    system_error,
                    ng_reason,
                    checked_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (asin) DO UPDATE SET
                    title = EXCLUDED.title,
                    amazon_price = EXCLUDED.amazon_price,
                    amazon_point = EXCLUDED.amazon_point,
                    available_qty = EXCLUDED.available_qty,
                    gift_available = EXCLUDED.gift_available,
                    shipping_status = EXCLUDED.shipping_status,
                    business_ng = EXCLUDED.business_ng,
                    system_error = EXCLUDED.system_error,
                    ng_reason = EXCLUDED.ng_reason,
                    checked_at = EXCLUDED.checked_at,
                    updated_at = CURRENT_TIMESTAMP
                ;
                """,
                (
                    TEST_ASIN,
                    "DB接続テスト商品",
                    1980,
                    0,
                    4,
                    True,
                    "OK",
                    False,
                    False,
                    "",
                    datetime.now(),
                ),
            )

            conn.commit()
            print("amazon_products への書き込みOK")

            cur.execute(
                """
                SELECT asin, title, amazon_price, checked_at
                FROM amazon_products
                WHERE asin = %s
                """,
                (TEST_ASIN,),
            )
            row = cur.fetchone()
            print("読み取り結果:", row)

        print("DB接続テスト成功")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
