"""Local advertiser configuration check; no API/DB calls, no configuration writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.listing.quasi_drug_compliance import ENV_PATH, _configured
from scripts.listing.compliance_text import ComplianceTextError


def main() -> int:
    parser = argparse.ArgumentParser(description="広告文責の会社名と文字化けだけを確認（電話番号・認証情報は出力しません）")
    parser.add_argument("--store", default="rakuten_2")
    args = parser.parse_args()
    inherited_name = os.getenv(f"{args.store.strip().upper()}_COMPLIANCE_ADVERTISER_NAME", "")
    try:
        config = _configured(args.store)
    except ComplianceTextError as exc:
        print(json.dumps({"diagnostic_version": 1, "status": "invalid_configuration",
                          "store": args.store, "env_path": str(ENV_PATH), "error": str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps({"diagnostic_version": 1, "status": "configured" if config else "missing_configuration",
                      "store": args.store, "env_path": str(ENV_PATH),
                      "advertiser_name": config["advertiser_name"] if config else "",
                      "phone_present": bool(config and config["advertiser_phone"]),
                      "inherited_name_present": bool(inherited_name),
                      "inherited_name_matches_effective": (inherited_name == config["advertiser_name"]
                                                           if config and inherited_name else None)}, ensure_ascii=True))
    return 0 if config else 2


if __name__ == "__main__":
    raise SystemExit(main())
