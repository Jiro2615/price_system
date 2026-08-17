from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.db_config import connect_db


SENSITIVE_MARKERS = ("医療", "医薬", "薬", "コンドーム", "性", "育毛", "殺菌", "除菌", "アルコール", "治療", "効能", "効果")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register one reviewed store-and-ASIN-specific listing phrase exception.")
    parser.add_argument("--store", required=True)
    parser.add_argument("--asin", required=True)
    parser.add_argument("--forbidden-word", required=True)
    parser.add_argument("--allowed-phrase", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asin, word, phrase = args.asin.strip().upper(), args.forbidden_word.strip(), args.allowed_phrase.strip()
    if len(asin) != 10 or not word or not phrase or word not in phrase:
        raise SystemExit("ASIN must be 10 characters and allowed phrase must include the forbidden word")
    if any(marker in word or marker in phrase for marker in SENSITIVE_MARKERS):
        raise SystemExit("sensitive medical/adult/alcohol phrase cannot be registered by this tool")
    if not args.apply:
        print(f"preview store={args.store} asin={asin} word={word} phrase={phrase}; add --apply to save")
        return 0
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE LOWER(store_code)=LOWER(%s)", (args.store,))
        store = cur.fetchone()
        if not store:
            raise SystemExit("store not found")
        cur.execute(
            """INSERT INTO listing_asin_allowed_phrases (store_id, asin, forbidden_word, allowed_phrase, note)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (store_id, asin, forbidden_word, allowed_phrase)
               DO UPDATE SET enabled=TRUE, note=EXCLUDED.note, updated_at=CURRENT_TIMESTAMP""",
            (store[0], asin, word, phrase, args.note.strip()),
        )
    print(f"saved store={args.store} asin={asin} phrase={phrase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
