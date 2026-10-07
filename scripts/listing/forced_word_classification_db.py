"""Fresh, read-only classification overrides. Missing/unreadable data fails closed."""
from scripts.db_config import connect_db


class ForcedWordClassificationReadError(RuntimeError):
    pass


def read_active_words(store):
    try:
        with connect_db(options="-c default_transaction_read_only=on -c statement_timeout=15000", connect_timeout=10) as conn, conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT p.keyword FROM prohibited_keywords p
                LEFT JOIN stores s ON s.id=p.store_id
                WHERE p.enabled=TRUE AND p.match_mode='contains' AND p.severity='block'
                  AND p.listing_rule_set='rakuten' AND (p.scope='global' OR LOWER(s.store_code)=LOWER(%s))
                ORDER BY p.keyword""", (store,))
            return [str(row[0]) for row in cur.fetchall()]
    except Exception as exc:
        raise ForcedWordClassificationReadError("送信直前の禁止語を取得できません。出品せず停止しました: " + type(exc).__name__) from exc


def read_overrides():
    try:
        with connect_db(options="-c default_transaction_read_only=on -c statement_timeout=15000", connect_timeout=10) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.forced_word_classifications')")
            if cur.fetchone()[0] is None:
                raise ForcedWordClassificationReadError("分類保存用のDBテーブルが未準備です。出品せず停止しました。編集機能のDB初期化を確認してください")
            cur.execute("SELECT keyword_key,group_name FROM forced_word_classifications WHERE enabled=TRUE ORDER BY keyword_key")
            rows = cur.fetchall()
    except ForcedWordClassificationReadError:
        raise
    except Exception as exc:
        raise ForcedWordClassificationReadError(
            "会社・ブランド／要確認語の最新分類をDBから取得できません。古い分類で出品せず停止しました: " + type(exc).__name__
        ) from exc
    if any(group not in {"block", "review", "ignore"} for _, group in rows):
        raise ForcedWordClassificationReadError("分類DBに不正な区分があります。出品せず停止しました")
    return {str(key): str(group) for key, group in rows}
