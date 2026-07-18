import base64
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_DIR / ".env"

TARGET_FOLDER_PATH = "listing_test"
ENDPOINT = "https://api.rms.rakuten.co.jp/es/1.0/cabinet/folders/get"


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
    raw = f"{service_secret}:{license_key}".encode("utf-8")
    token = base64.b64encode(raw).decode("ascii")
    return f"ESA {token}"


def fetch_xml(offset: int, limit: int, authorization: str) -> ET.Element:
    query = urlencode({"offset": offset, "limit": limit})
    url = f"{ENDPOINT}?{query}"

    req = Request(
        url,
        method="GET",
        headers={
            "Authorization": authorization,
            "Accept": "text/xml",
            "User-Agent": "price-system-listing-cabinet-check/1.0",
        },
    )

    try:
        with urlopen(req, timeout=30) as res:
            body = res.read()
            return ET.fromstring(body)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"URL error: {e}") from e
    except ET.ParseError as e:
        raise RuntimeError(f"XML parse error: {e}") from e


def text_or_empty(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    found = node.find(tag)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def normalize_folder_path(value: str) -> str:
    return value.strip().strip("/")


def extract_folders(root: ET.Element) -> list[dict]:
    folders = []
    for folder in root.findall(".//folder"):
        folders.append({
            "FolderId": text_or_empty(folder, "FolderId"),
            "FolderName": text_or_empty(folder, "FolderName"),
            "FolderNode": text_or_empty(folder, "FolderNode"),
            "FolderPath": text_or_empty(folder, "FolderPath"),
            "FileCount": text_or_empty(folder, "FileCount"),
            "FileSize": text_or_empty(folder, "FileSize"),
            "TimeStamp": text_or_empty(folder, "TimeStamp"),
        })
    return folders


def main() -> int:
    load_dotenv(ENV_PATH)

    service_secret = get_env_any([
        "RAKUTEN_SERVICE_SECRET",
        "RAKUTEN_ITEM_SERVICE_SECRET",
        "RAKUTEN_API_SERVICE_SECRET",
        "RAKUTEN_RMS_SERVICE_SECRET",
        "RAKUTEN_IMAGE_SERVICE_SECRET",
    ])
    license_key = get_env_any([
        "RAKUTEN_LICENSE_KEY",
        "RAKUTEN_ITEM_LICENSE_KEY",
        "RAKUTEN_API_LICENSE_KEY",
        "RAKUTEN_RMS_LICENSE_KEY",
        "RAKUTEN_IMAGE_LICENSE_KEY",
    ])

    if not service_secret or not license_key:
        print("ERROR: .env から serviceSecret / licenseKey を取得できませんでした。", file=sys.stderr)
        print("確認候補:", file=sys.stderr)
        print("  RAKUTEN_SERVICE_SECRET / RAKUTEN_LICENSE_KEY", file=sys.stderr)
        print("  RAKUTEN_ITEM_SERVICE_SECRET / RAKUTEN_ITEM_LICENSE_KEY", file=sys.stderr)
        print("  RAKUTEN_API_SERVICE_SECRET / RAKUTEN_API_LICENSE_KEY", file=sys.stderr)
        print("  RAKUTEN_RMS_SERVICE_SECRET / RAKUTEN_RMS_LICENSE_KEY", file=sys.stderr)
        print("  RAKUTEN_IMAGE_SERVICE_SECRET / RAKUTEN_IMAGE_LICENSE_KEY", file=sys.stderr)
        return 1

    authorization = build_authorization(service_secret, license_key)

    limit = 100
    offset = 1
    target_norm = normalize_folder_path(TARGET_FOLDER_PATH)

    all_matches = []
    total_seen = 0

    while True:
        root = fetch_xml(offset=offset, limit=limit, authorization=authorization)

        result_code = root.findtext(".//cabinetFoldersGetResult/resultCode")
        folder_all_count = root.findtext(".//cabinetFoldersGetResult/folderAllCount")
        folder_count = root.findtext(".//cabinetFoldersGetResult/folderCount")

        folders = extract_folders(root)
        total_seen += len(folders)

        for folder in folders:
            path_norm = normalize_folder_path(folder.get("FolderPath", ""))
            name_norm = normalize_folder_path(folder.get("FolderName", ""))

            if path_norm == target_norm or name_norm == target_norm:
                all_matches.append(folder)

        print(
            f"offset={offset} resultCode={result_code} "
            f"folderCount={folder_count} folderAllCount={folder_all_count}"
        )

        try:
            all_count_int = int(folder_all_count or "0")
        except ValueError:
            all_count_int = 0

        if len(folders) == 0:
            break
        if total_seen >= all_count_int:
            break
        if offset >= 1000:
            raise RuntimeError("Too many pages. Stop for safety.")

        offset += 1

    print()
    print(f"target_folder_path: {TARGET_FOLDER_PATH}")
    print(f"matches: {len(all_matches)}")

    if not all_matches:
        print("NOT_FOUND")
        print("RMSで listing_test フォルダが存在するか、FolderPathが listing_test か確認してください。")
        return 2

    for i, folder in enumerate(all_matches, start=1):
        print()
        print(f"[MATCH {i}]")
        print(f"FolderId   : {folder.get('FolderId')}")
        print(f"FolderName : {folder.get('FolderName')}")
        print(f"FolderPath : {folder.get('FolderPath')}")
        print(f"FolderNode : {folder.get('FolderNode')}")
        print(f"FileCount  : {folder.get('FileCount')}")
        print(f"FileSize   : {folder.get('FileSize')}")
        print(f"TimeStamp  : {folder.get('TimeStamp')}")

        folder_path = normalize_folder_path(folder.get("FolderPath", ""))
        example_file = "b0cn39x1fc_01.jpg"
        item_location = f"/{folder_path}/{example_file}"
        full_url = f"https://image.rakuten.co.jp/ecprime500/cabinet/{folder_path}/{example_file}"

        print(f"Example item location: {item_location}")
        print(f"Example full URL     : {full_url}")

    if len(all_matches) > 1:
        print()
        print("WARNING: listing_test に一致するフォルダが複数あります。RMS上でどれを使うか確認してください。")
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())