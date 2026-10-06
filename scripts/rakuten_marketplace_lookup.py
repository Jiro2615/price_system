"""Read-only product-identity and reference-price lookup. No listing, order, or DB writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.listing.rakuten_marketplace_policy import rakuten_marketplace_evidence
from scripts.listing.rakuten_search_client import RakutenSearchError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jan", default="")
    parser.add_argument("--title", required=True)
    parser.add_argument("--brand", default="")
    parser.add_argument("--manufacturer", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--part-number", default="")
    parser.add_argument("--minimum-shops", type=int, default=1)
    args = parser.parse_args()
    if not args.title.strip() or not 1 <= args.minimum_shops <= 30:
        parser.error("title is required and minimum-shops must be between 1 and 30")
    try:
        result = rakuten_marketplace_evidence(jan_code=args.jan, title=args.title, brand=args.brand,
            manufacturer=args.manufacturer, model=args.model, part_number=args.part_number,
            minimum_shops=args.minimum_shops)
        print(json.dumps({"mode": "read_only", "evidence": result}, ensure_ascii=False), flush=True)
    except RakutenSearchError as exc:
        print(json.dumps({"mode": "read_only", "status": "system_error", "error": str(exc)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
