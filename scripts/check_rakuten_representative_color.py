import base64
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_DIR / ".env"
GENRE_ID = "213661"
TARGET_ATTRIBUTE_NAME = "代表カラー"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def get_env_any(names: list[str]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def build_authorization(service_secret: str, license_key: str) -> str:
    token = base64.b64encode(f"{service_secret}:{license_key}".encode("utf-8")).decode("ascii")
    return f"ESA {token}"


def fetch_json(url: str, authorization: str) -> dict:
    req = Request(
        url,
        method="GET",
        headers={
            "Authorization": authorization,
            "Accept": "application/json",
            "User-Agent": "price-system-listing-check/1.0",
        },
    )

    try:
        with urlopen(req, timeout=30) as res:
            body = res.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"URL error: {e}") from e


def main() -> int:
    load_dotenv(ENV_PATH)

    service_secret = get_env_any([
        "RAKUTEN_SERVICE_SECRET",
        "RAKUTEN_ITEM_SERVICE_SECRET",
        "RAKUTEN_API_SERVICE_SECRET",
        "RAKUTEN_RMS_SERVICE_SECRET",
    ])
    license_key = get_env_any([
        "RAKUTEN_LICENSE_KEY",
        "RAKUTEN_ITEM_LICENSE_KEY",
        "RAKUTEN_API_LICENSE_KEY",
        "RAKUTEN_RMS_LICENSE_KEY",
    ])

    if not service_secret or not license_key:
        print("ERROR: .env から serviceSecret / licenseKey を取得できませんでした。", file=sys.stderr)
        print("確認候補:", file=sys.stderr)
        print("  RAKUTEN_SERVICE_SECRET / RAKUTEN_LICENSE_KEY", file=sys.stderr)
        print("  RAKUTEN_ITEM_SERVICE_SECRET / RAKUTEN_ITEM_LICENSE_KEY", file=sys.stderr)
        print("  RAKUTEN_API_SERVICE_SECRET / RAKUTEN_API_LICENSE_KEY", file=sys.stderr)
        print("  RAKUTEN_RMS_SERVICE_SECRET / RAKUTEN_RMS_LICENSE_KEY", file=sys.stderr)
        return 1

    authorization = build_authorization(service_secret, license_key)
    url = f"https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/{GENRE_ID}/attributes/-/dictionaryValues"

    data = fetch_json(url, authorization)

    attributes = (
        data.get("genre", {})
        .get("attributes", [])
    )

    matches = [
        attr for attr in attributes
        if attr.get("nameJa") == TARGET_ATTRIBUTE_NAME
    ]

    output_dir = PROJECT_DIR / "output" / "listing"
    output_dir.mkdir(parents=True, exist_ok=True)

    full_output_path = output_dir / f"genre_{GENRE_ID}_attributes_dictionary_values.json"
    color_output_path = output_dir / f"genre_{GENRE_ID}_representative_color.json"

    full_output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = {
        "genreId": GENRE_ID,
        "target_attribute_name": TARGET_ATTRIBUTE_NAME,
        "match_count": len(matches),
        "matches": matches,
        "source_url": url,
    }

    color_output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    print(f"saved_full: {full_output_path}")
    print(f"saved_color_only: {color_output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())