import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import paramiko
except ImportError as e:
    raise SystemExit(
        "paramiko が入っていません。\n"
        "先に実行してください:\n"
        "  py -m pip install paramiko python-dotenv\n"
    ) from e

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(r"C:\price_system")
ENV_PATH = BASE_DIR / ".env"
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_csv_logs"


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
    "警告",
    "文字コード",
]

SUCCESS_KEYWORDS = [
    "正常",
    "成功",
    "完了",
    "エラーはありません",
]


def load_settings() -> dict:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH)

    host = os.getenv("RAKUTEN_SFTP_HOST", DEFAULT_HOST).strip()
    port = int(os.getenv("RAKUTEN_SFTP_PORT", str(DEFAULT_PORT)).strip() or DEFAULT_PORT)
    user = os.getenv("RAKUTEN_SFTP_USER", "").strip()
    password = os.getenv("RAKUTEN_SFTP_PASSWORD", "").strip()
    batch_dir = os.getenv("RAKUTEN_SFTP_BATCH_DIR", DEFAULT_BATCH_DIR).strip() or DEFAULT_BATCH_DIR
    log_dir = os.getenv("RAKUTEN_SFTP_LOG_DIR", DEFAULT_LOG_DIR).strip() or DEFAULT_LOG_DIR

    if not user:
        raise RuntimeError(f"RAKUTEN_SFTP_USER が空です: {ENV_PATH}")

    if not password:
        raise RuntimeError(f"RAKUTEN_SFTP_PASSWORD が空です: {ENV_PATH}")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "batch_dir": batch_dir,
        "log_dir": log_dir,
    }


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


def connect_sftp(settings: dict):
    """
    楽天SFTP側が古いホスト鍵方式だけを提示する環境向けに、
    通常接続 → legacy host key優先接続 の順で試す。

    ParamikoのSecurityOptions.key_typesは、接続開始前に変更する必要がある。
    """
    attempts = [
        ("default", None),
        (
            "legacy_host_key",
            [
                "ssh-rsa",
                "ssh-dss",
                "rsa-sha2-512",
                "rsa-sha2-256",
                "ecdsa-sha2-nistp256",
                "ecdsa-sha2-nistp384",
                "ecdsa-sha2-nistp521",
                "ssh-ed25519",
            ],
        ),
    ]

    last_error = None

    for label, preferred_key_types in attempts:
        transport = None
        try:
            transport = paramiko.Transport((settings["host"], settings["port"]))

            if preferred_key_types:
                opts = transport.get_security_options()
                supported = set(opts.key_types)
                key_types = tuple(k for k in preferred_key_types if k in supported)

                if key_types:
                    opts.key_types = key_types
                    print(f"SFTP host key mode: {label} / key_types={key_types}")
                else:
                    print(f"SFTP host key mode: {label} / 利用可能なlegacy key_typesなし")

            transport.connect(username=settings["user"], password=settings["password"])
            sftp = paramiko.SFTPClient.from_transport(transport)
            return transport, sftp

        except Exception as e:
            last_error = e
            try:
                if transport is not None:
                    transport.close()
            except Exception:
                pass

            print(f"SFTP接続失敗: mode={label} / {e}")

    raise last_error


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


def find_matching_logs(sftp, log_dir: str, original_filename: str, upload_started: float) -> list[tuple[str, float, int]]:
    """
    楽天のログは以下のような名前で出ることがある:
      normal-item_price_20260630_192709.20260630193118037.csv

    元ファイル:
      normal-item_price_20260630_192709.csv

    そのため、stem + "." で始まるログも対象にする。
    """
    original = Path(original_filename)
    stem = original.stem

    matches = []

    try:
        attrs = sftp.listdir_attr(log_dir)
    except FileNotFoundError:
        return matches

    for attr in attrs:
        name = attr.filename

        if not (
            name == original_filename
            or name.startswith(original_filename + ".")
            or name.startswith(stem + ".")
            or name.startswith(stem + "_")
            or stem in name
        ):
            continue

        # 古いログを拾いにくくする。サーバ時刻差も考えて少し余裕を見る。
        if attr.st_mtime and attr.st_mtime < upload_started - 120:
            continue

        matches.append((name, float(attr.st_mtime or 0), int(attr.st_size or 0)))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def download_remote_file(sftp, remote_path: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    sftp.get(remote_path, str(local_path))


def judge_log(log_text: str) -> tuple[str, str]:
    """
    戻り値:
      success / failed / unknown, message

    楽天ログの形式は店舗設定や処理内容で変わる可能性があるため、
    エラー語句を優先して判定する。
    """
    text = log_text or ""

    error_hits = [kw for kw in ERROR_KEYWORDS if kw in text]

    # 「エラーはありません」は成功扱いに寄せる。
    if "エラーはありません" in text:
        return "success", "ログに「エラーはありません」を確認"

    if error_hits:
        return "failed", f"エラーらしき文言を検出: {', '.join(error_hits[:5])}"

    success_hits = [kw for kw in SUCCESS_KEYWORDS if kw in text]
    if success_hits:
        return "success", f"成功らしき文言を検出: {', '.join(success_hits[:5])}"

    # ログが空でなければ、エラー文言なしとして一旦成功寄せ。
    # ただし不安ならRMS画面でも確認する。
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


def upload_and_watch(
    *,
    local_csv: Path,
    remote_name: str,
    timeout: int,
    poll_interval: int,
    apply_db: bool,
    include_stock: bool,
    dry_run: bool,
) -> int:
    settings = load_settings()

    if not local_csv.exists():
        raise RuntimeError(f"CSVが見つかりません: {local_csv}")

    if not remote_name:
        remote_name = local_csv.name

    if not remote_name.startswith("normal-item"):
        raise RuntimeError(f"楽天商品CSVのファイル名は normal-item で始めてください: {remote_name}")

    print("楽天SFTP設定")
    print(f"  host     : {settings['host']}")
    print(f"  port     : {settings['port']}")
    print(f"  user     : {settings['user']}")
    print(f"  batch_dir: {settings['batch_dir']}")
    print(f"  log_dir  : {settings['log_dir']}")
    print("")
    print(f"local_csv : {local_csv}")
    print(f"remote    : {remote_join(settings['batch_dir'], remote_name)}")
    print("")

    if dry_run:
        print("dry-run のためアップロードしません。")
        return 0

    upload_started = time.time()
    transport = None
    sftp = None

    try:
        transport, sftp = connect_sftp(settings)

        remote_path = remote_join(settings["batch_dir"], remote_name)

        print("アップロード開始")
        sftp.put(str(local_csv), remote_path)
        print("アップロード完了")
        print("")

        print(f"ログ監視開始: timeout={timeout}s, interval={poll_interval}s")
        deadline = time.time() + timeout

        downloaded_log: Optional[Path] = None
        status = "unknown"
        message = "ログ未検出"

        while time.time() < deadline:
            matches = find_matching_logs(
                sftp=sftp,
                log_dir=settings["log_dir"],
                original_filename=remote_name,
                upload_started=upload_started,
            )

            if matches:
                log_name, mtime, size = matches[0]
                remote_log_path = remote_join(settings["log_dir"], log_name)
                local_log_path = OUTPUT_DIR / log_name

                print(f"ログ検出: {remote_log_path} size={size}")
                download_remote_file(sftp, remote_log_path, local_log_path)

                log_text, enc = read_text_fallback(local_log_path)
                status, message = judge_log(log_text)
                downloaded_log = local_log_path

                print(f"ログ保存: {local_log_path}")
                print(f"ログ文字コード: {enc}")
                print(f"判定: {status} / {message}")
                break

            print("ログ待機中...")
            time.sleep(poll_interval)

        if downloaded_log is None:
            print("ログが見つかりませんでした。RMS画面または /ritem/logs を確認してください。")
            return 3

        if status != "success":
            print("CSV処理は成功扱いにしません。DB反映もしません。")
            return 4

        print("")
        print("CSV処理は成功扱いです。")

        if apply_db:
            return run_apply_db(local_csv, include_stock=include_stock)

        print("DB反映は未実行です。反映する場合は --apply-db を付けてください。")
        return 0

    finally:
        try:
            if sftp is not None:
                sftp.close()
        finally:
            if transport is not None:
                transport.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="楽天 normal-item.csv をSFTPアップロードし、/ritem/logs を監視します。")
    parser.add_argument("--csv", required=True, help="アップロードする normal-item CSV")
    parser.add_argument("--remote-name", default="", help="SFTP上のファイル名。未指定ならローカルファイル名")
    parser.add_argument("--timeout", type=int, default=300, help="ログ待機タイムアウト秒")
    parser.add_argument("--poll-interval", type=int, default=10, help="ログ確認間隔秒")
    parser.add_argument("--apply-db", action="store_true", help="成功判定後にDBへ current_price/current_stock を反映する")
    parser.add_argument("--include-stock", action="store_true", help="DB反映時にCSVの在庫数も current_stock へ反映する")
    parser.add_argument("--dry-run", action="store_true", help="SFTP接続やアップロードをせず内容確認のみ")
    args = parser.parse_args()

    return upload_and_watch(
        local_csv=Path(args.csv),
        remote_name=args.remote_name.strip(),
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        apply_db=args.apply_db,
        include_stock=args.include_stock,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
