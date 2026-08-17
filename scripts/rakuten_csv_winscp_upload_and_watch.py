import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR.parent / ".env"
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_csv_logs"
TEMP_DIR = BASE_DIR / "temp" / "winscp"

DEFAULT_HOST = "upload.rakuten.ne.jp"
DEFAULT_PORT = 22
DEFAULT_BATCH_DIR = "/ritem/batch"
DEFAULT_LOG_DIR = "/ritem/logs"

ERROR_KEYWORDS = [
    "エラー",
    "ERROR",
    "Error",
    "error",
    "失敗",
    "不正",
    "存在しません",
    "登録できません",
    "更新できません",
    "必須",
    "文字コード",
]

SUCCESS_KEYWORDS = [
    "正常",
    "成功",
    "完了",
    "エラーはありません",
]


def normalize_store_env_prefix(store_code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(store_code or "").strip()).strip("_").upper()


def first_store_env(store_code: str, suffix: str, default: str = "") -> str:
    prefix = normalize_store_env_prefix(store_code) or "RAKUTEN_1"
    value = os.getenv(f"{prefix}_{suffix}")
    if value is not None and str(value).strip():
        return str(value).strip()
    return default


def load_settings(store_code: str = "") -> dict:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH)

    host = first_store_env(store_code, "SFTP_HOST", DEFAULT_HOST)
    port = int(first_store_env(store_code, "SFTP_PORT", str(DEFAULT_PORT)) or DEFAULT_PORT)
    user = first_store_env(store_code, "SFTP_USER")
    password = first_store_env(store_code, "SFTP_PASSWORD")
    batch_dir = first_store_env(store_code, "SFTP_BATCH_DIR", DEFAULT_BATCH_DIR) or DEFAULT_BATCH_DIR
    log_dir = first_store_env(store_code, "SFTP_LOG_DIR", DEFAULT_LOG_DIR) or DEFAULT_LOG_DIR
    hostkey = first_store_env(store_code, "SFTP_HOSTKEY", "*") or "*"
    winscp_com = os.getenv("WINSCP_COM", "").strip()

    if not user:
        raise RuntimeError(f"RAKUTEN_1_SFTP_USER または店舗別SFTPユーザーが空です: {ENV_PATH}")

    if not password:
        raise RuntimeError(f"RAKUTEN_1_SFTP_PASSWORD または店舗別SFTPパスワードが空です: {ENV_PATH}")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "batch_dir": batch_dir,
        "log_dir": log_dir,
        "hostkey": hostkey,
        "winscp_com": winscp_com,
    }


def find_winscp_com(settings: dict) -> Path:
    candidates = []

    if settings.get("winscp_com"):
        candidates.append(Path(settings["winscp_com"]))

    candidates.extend([
        Path(r"C:\Program Files (x86)\WinSCP\WinSCP.com"),
        Path(r"C:\Program Files\WinSCP\WinSCP.com"),
    ])

    for p in candidates:
        if p.exists():
            return p

    raise RuntimeError(
        "WinSCP.com が見つかりません。\n"
        "WinSCPをインストールするか、.env に WINSCP_COM=C:\\path\\to\\WinSCP.com を追加してください。\n"
        "例:\n"
        "  WINSCP_COM=C:\\Program Files (x86)\\WinSCP\\WinSCP.com"
    )


def remote_join(*parts: str) -> str:
    cleaned = []
    for part in parts:
        if part is None:
            continue
        s = str(part).replace("\\", "/")
        if not s:
            continue
        cleaned.append(s.strip("/"))

    if not cleaned:
        return "/"

    if str(parts[0]).startswith("/"):
        return "/" + "/".join(cleaned)

    return "/".join(cleaned)


def make_open_command(settings: dict) -> str:
    user = quote(settings["user"], safe="")
    password = quote(settings["password"], safe="")
    host = settings["host"]
    port = settings["port"]
    hostkey = settings["hostkey"]

    # hostkey="*" は初回検証向け。運用時は実際のフィンガープリント指定を推奨。
    return f'open sftp://{user}:{password}@{host}:{port}/ -hostkey="{hostkey}"'


def write_winscp_script(commands: list[str], prefix: str) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = TEMP_DIR / f"{prefix}_{timestamp}.txt"

    lines = [
        "option batch abort",
        "option confirm off",
        *commands,
        "exit",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def mask_secret(text: str, settings: dict) -> str:
    masked = text
    if settings.get("password"):
        masked = masked.replace(settings["password"], "********")
        masked = masked.replace(quote(settings["password"], safe=""), "********")
    return masked


def run_winscp(settings: dict, commands: list[str], prefix: str, allow_fail: bool = False) -> subprocess.CompletedProcess:
    winscp = find_winscp_com(settings)
    script_path = write_winscp_script(commands, prefix=prefix)

    log_path = TEMP_DIR / f"{script_path.stem}.log"

    cmd = [
        str(winscp),
        "/ini=nul",
        f"/script={script_path}",
        f"/log={log_path}",
        "/loglevel=0",
    ]

    print("")
    print(f"WinSCP実行: {prefix}")
    print(mask_secret(" ".join(cmd), settings))
    print(f"script: {script_path}")
    print(f"log   : {log_path}")

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    if result.stdout.strip():
        print("----- WinSCP stdout -----")
        print(mask_secret(result.stdout, settings).strip())

    if result.stderr.strip():
        print("----- WinSCP stderr -----")
        print(mask_secret(result.stderr, settings).strip())

    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(
            f"WinSCPエラー returncode={result.returncode}\n"
            f"script={script_path}\n"
            f"log={log_path}"
        )

    return result


def read_text_fallback(path: Path) -> tuple[str, str]:
    encodings = ["cp932", "utf-8-sig", "utf-8"]
    last_error = None

    for enc in encodings:
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError as e:
            last_error = e
            continue

    raise RuntimeError(f"ログを読めませんでした: {path} / {last_error}")


def judge_log(log_text: str) -> tuple[str, str]:
    text = log_text or ""

    if "エラーはありません" in text:
        return "success", "ログに「エラーはありません」を確認"

    error_hits = [kw for kw in ERROR_KEYWORDS if kw in text]
    if error_hits:
        return "failed", f"エラーらしき文言を検出: {', '.join(error_hits[:5])}"

    success_hits = [kw for kw in SUCCESS_KEYWORDS if kw in text]
    if success_hits:
        return "success", f"成功らしき文言を検出: {', '.join(success_hits[:5])}"

    if text.strip():
        return "success", "ログにエラー文言なし"

    return "unknown", "ログが空のため判定不能"


def run_apply_db(csv_path: Path, include_stock: bool) -> int:
    script_path = Path(__file__).resolve().parent / "apply_rakuten_csv_success_to_db.py"
    if not script_path.exists():
        print(f"DB反映スクリプトが見つかりません: {script_path}")
        return 2

    cmd = [
        sys.executable,
        str(script_path),
        "--csv",
        str(csv_path),
        "--execute",
    ]

    if include_stock:
        cmd.append("--include-stock")

    print("")
    print("DB反映を実行します:")
    print(" ".join(cmd))
    print("")

    result = subprocess.run(cmd, text=True)
    return int(result.returncode or 0)


def download_matching_logs(settings: dict, remote_pattern: str) -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # WinSCP get のローカルパス末尾に \ を付けるとフォルダ保存扱い。
    local_dir = str(OUTPUT_DIR) + "\\"

    commands = [
        make_open_command(settings),
        f'get "{remote_pattern}" "{local_dir}"',
    ]

    result = run_winscp(settings, commands, prefix="get_logs", allow_fail=True)

    downloaded = []

    # getが成功してもreturncodeが0。ファイルがない場合は1になりやすい。
    # ローカル側で対象ファイルを探す。
    pattern_name = Path(remote_pattern.replace("\\", "/")).name
    stem = pattern_name.replace("*", "")

    for p in OUTPUT_DIR.iterdir():
        if not p.is_file():
            continue
        if stem and stem in p.name:
            downloaded.append(p)

    downloaded.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return downloaded




def remote_file_exists(settings: dict, remote_path: str) -> bool:
    """
    /ritem/batch 上にアップロードしたCSVがまだ残っているか確認する。

    WinSCPの `ls "/ritem/batch/file.csv"` は、環境によって
    「file.csvをディレクトリとして一覧取得しようとして Not a directory」
    になることがあるため、親ディレクトリをlsしてファイル名の有無で判定する。
    """
    rp = remote_path.replace("\\", "/").rstrip("/")
    parent = rp.rsplit("/", 1)[0] or "/"
    filename = rp.rsplit("/", 1)[-1]

    commands = [
        make_open_command(settings),
        f'ls "{parent}"',
    ]

    result = run_winscp(settings, commands, prefix="check_remote_file", allow_fail=True)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")

    if result.returncode != 0:
        missing_words = [
            "No file",
            "No such file",
            "not found",
            "Can't get attributes",
            "File or folder",
            "一致するファイルがありません",
            "見つかりません",
        ]

        if any(w in combined for w in missing_words):
            return False

        # 親ディレクトリのls自体に失敗した場合は、安全側で「まだある」扱い。
        print("注意: batchディレクトリ確認に失敗したため、CSVはまだ残っている扱いにします。")
        return True

    return filename in combined

def upload_and_watch(
    *,
    local_csv: Path,
    remote_name: str,
    timeout: int,
    poll_interval: int,
    settle_wait: int,
    require_log: bool,
    watch_only: bool,
    apply_db: bool,
    include_stock: bool,
    dry_run: bool,
    store_code: str = "",
) -> int:
    settings = load_settings(store_code)

    if not local_csv.exists():
        raise RuntimeError(f"CSVが見つかりません: {local_csv}")

    if not remote_name:
        remote_name = local_csv.name

    if not remote_name.startswith("normal-item"):
        raise RuntimeError(f"楽天商品CSVのファイル名は normal-item で始めてください: {remote_name}")

    if settings["hostkey"] == "*":
        print("注意: RAKUTEN_SFTP_HOSTKEY='*' で接続します。")
        print("      まずは動作確認用として使えますが、運用ではWinSCPで表示されるホスト鍵フィンガープリント指定を推奨します。")
        print("")

    winscp_path = find_winscp_com(settings)

    print("楽天SFTP設定")
    print(f"  host     : {settings['host']}")
    print(f"  port     : {settings['port']}")
    print(f"  user     : {settings['user']}")
    print(f"  batch_dir: {settings['batch_dir']}")
    print(f"  log_dir  : {settings['log_dir']}")
    print(f"  winscp   : {winscp_path}")
    print("")
    print(f"local_csv : {local_csv}")
    print(f"remote    : {remote_join(settings['batch_dir'], remote_name)}")
    print("")

    if dry_run:
        print("dry-run のためアップロードしません。")
        return 0

    upload_started = time.time()

    remote_csv_path = remote_join(settings["batch_dir"], remote_name)

    if watch_only:
        print("watch-only のためアップロードせず、既存のbatch/logs状態だけ監視します。")
    else:
        commands = [
            make_open_command(settings),
            f'put "{local_csv}" "{remote_csv_path}"',
        ]

        run_winscp(settings, commands, prefix="upload_csv")

        print("")
        print("アップロード完了。楽天ログを監視します。")

    print(f"timeout={timeout}s, interval={poll_interval}s")

    original = Path(remote_name)
    stem = original.stem
    # 例: /ritem/logs/normal-item_price_20260630_193801*
    remote_log_pattern = remote_join(settings["log_dir"], f"{stem}*")

    deadline = time.time() + timeout
    last_seen_log: Optional[Path] = None

    batch_disappeared_at: Optional[float] = None

    while time.time() < deadline:
        logs = download_matching_logs(settings, remote_log_pattern)

        # 今回のアップロード前からあった古いログを拾いにくくする
        fresh_logs = []
        for p in logs:
            try:
                if p.stat().st_mtime >= upload_started - 120:
                    fresh_logs.append(p)
            except Exception:
                pass

        if fresh_logs:
            log_path = fresh_logs[0]
            last_seen_log = log_path

            log_text, enc = read_text_fallback(log_path)
            status, message = judge_log(log_text)

            print("")
            print(f"ログ検出: {log_path}")
            print(f"ログ文字コード: {enc}")
            print(f"判定: {status} / {message}")

            if status != "success":
                print("CSV処理は成功扱いにしません。DB反映もしません。")
                return 4

            print("CSV処理は成功扱いです。")

            if apply_db:
                return run_apply_db(local_csv, include_stock=include_stock)

            print("DB反映は未実行です。反映する場合は --apply-db を付けてください。")
            return 0

        # いったんbatchから消えた後は、再度batch確認しない。
        # エラーログの発生だけをsettle_wait秒監視する。
        if batch_disappeared_at is not None:
            elapsed = time.time() - batch_disappeared_at
            remaining = max(0, int(settle_wait - elapsed))

            if not require_log and elapsed >= settle_wait:
                print("")
                print("batchからCSVが消えた後、エラーログが出ませんでした。")
                print("CSV処理は成功扱いにします。")

                if apply_db:
                    return run_apply_db(local_csv, include_stock=include_stock)

                print("DB反映は未実行です。反映する場合は --apply-db を付けてください。")
                return 0

            print(f"エラーログ待機中... batch消失後 {int(elapsed)}s 経過 / 残り約 {remaining}s")
            time.sleep(poll_interval)
            continue

        exists_in_batch = remote_file_exists(settings, remote_csv_path)

        if exists_in_batch:
            print("ログ待機中... batch上にCSVはまだ残っています。")
            time.sleep(poll_interval)
            continue

        batch_disappeared_at = time.time()
        print("")
        print("batch上のCSVが消えました。楽天側が処理した可能性があります。")
        if require_log:
            print("--require-log 指定中のため、ログが出るまで待機します。")
        else:
            print(f"成功時ログなし運用に備え、ここから {settle_wait}s だけエラーログ発生を待ちます。")

        time.sleep(poll_interval)

    print("")
    if require_log:
        print("ログが見つかりませんでした。--require-log 指定中のため成功扱いにしません。")
    else:
        print("タイムアウトしました。batchから消えていない、または成功判定待ちが完了しませんでした。")
    print("RMS画面または /ritem/logs を確認してください。")
    if last_seen_log:
        print(f"最後に見えたログ: {last_seen_log}")
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description="WinSCP.comで楽天 normal-item.csv をSFTPアップロードし、/ritem/logs を監視します。")
    parser.add_argument("--csv", required=True, help="アップロードする normal-item CSV")
    parser.add_argument("--remote-name", default="", help="SFTP上のファイル名。未指定ならローカルファイル名")
    parser.add_argument("--timeout", type=int, default=300, help="ログ待機タイムアウト秒")
    parser.add_argument("--poll-interval", type=int, default=15, help="ログ確認間隔秒")
    parser.add_argument("--settle-wait", type=int, default=60, help="batchからCSVが消えた後、ログなし成功判定まで待つ秒数")
    parser.add_argument("--require-log", action="store_true", help="ログが出ない場合は成功扱いにしない")
    parser.add_argument("--watch-only", action="store_true", help="アップロードせず、既にアップ済みのCSVについてbatch/logsだけ監視する")
    parser.add_argument("--apply-db", action="store_true", help="成功判定後にDBへ current_price/current_stock を反映する")
    parser.add_argument("--include-stock", action="store_true", help="DB反映時にCSVの在庫数も current_stock へ反映する")
    parser.add_argument("--dry-run", action="store_true", help="SFTP接続やアップロードをせず内容確認のみ")
    parser.add_argument("--store", default="", help="stores.store_code. Uses RAKUTEN_1_SFTP_* by default and the matching store-scoped keys when provided.")
    args = parser.parse_args()

    return upload_and_watch(
        local_csv=Path(args.csv),
        remote_name=args.remote_name.strip(),
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        settle_wait=args.settle_wait,
        require_log=args.require_log,
        watch_only=args.watch_only,
        apply_db=args.apply_db,
        include_stock=args.include_stock,
        dry_run=args.dry_run,
        store_code=args.store,
    )


if __name__ == "__main__":
    raise SystemExit(main())
