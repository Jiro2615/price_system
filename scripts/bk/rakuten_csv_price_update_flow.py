import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


BASE_DIR = Path(r"C:\price_system")
SCRIPTS_DIR = BASE_DIR / "scripts"
OUTPUT_DIR = BASE_DIR / "output" / "rakuten_csv"


def run_live(cmd: list[str], *, cwd: Path, allow_error: bool = False) -> tuple[int, str]:
    """
    子プロセスの標準出力を画面に流しつつ、後で判定できるよう文字列としても返す。
    """
    print("")
    print("============================================================")
    print("実行:", " ".join(cmd))
    print("============================================================")
    print("")

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    output_lines: list[str] = []

    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
        output_lines.append(line)

    proc.wait()
    out = "".join(output_lines)

    if proc.returncode != 0 and not allow_error:
        raise RuntimeError(f"コマンドが失敗しました returncode={proc.returncode}: {' '.join(cmd)}")

    return int(proc.returncode or 0), out


def script_path(name: str) -> Path:
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise RuntimeError(f"必要なスクリプトが見つかりません: {path}")
    return path


def extract_log_path(watcher_output: str) -> Optional[Path]:
    """
    rakuten_csv_winscp_upload_and_watch.py の出力から
      ログ検出: C:\\...
    を拾う。
    """
    patterns = [
        r"ログ検出:\s*(.+)",
        r"ログ保存:\s*(.+)",
    ]

    for pat in patterns:
        m = re.search(pat, watcher_output)
        if m:
            p = Path(m.group(1).strip().strip('"'))
            if p.exists():
                return p

    # 念のため、output/rakuten_csv_logs にある最新の同名系ログを拾う処理は
    # 呼び出し側で実装する。
    return None


def find_latest_matching_log(csv_path: Path) -> Optional[Path]:
    log_dir = BASE_DIR / "output" / "rakuten_csv_logs"
    if not log_dir.exists():
        return None

    stem = csv_path.stem
    candidates = []
    for p in log_dir.iterdir():
        if not p.is_file():
            continue
        if stem in p.name:
            candidates.append(p)

    if not candidates:
        return None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def build_export_args(args, output_csv: Path, check_csv: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(script_path("export_rakuten_normal_item_price_csv.py")),
        "--store",
        args.store,
        "--limit",
        str(args.limit),
        "--output",
        str(output_csv),
        "--check-output",
        str(check_csv),
    ]

    if args.include_stock:
        cmd.append("--include-stock")

    if args.include_stock_only:
        cmd.append("--include-stock-only")

    if args.allow_large_change:
        cmd.append("--allow-large-change")

    if args.include_blocked:
        cmd.append("--include-blocked")

    if args.dry_run:
        cmd.append("--dry-run")

    return cmd


def apply_success(csv_path: Path, args) -> None:
    cmd = [
        sys.executable,
        str(script_path("apply_rakuten_csv_success_to_db.py")),
        "--csv",
        str(csv_path),
        "--execute",
    ]

    if args.include_stock:
        cmd.append("--include-stock")

    run_live(cmd, cwd=SCRIPTS_DIR)


def apply_result(csv_path: Path, log_path: Path, args) -> None:
    cmd = [
        sys.executable,
        str(script_path("apply_rakuten_csv_result_to_db.py")),
        "--csv",
        str(csv_path),
        "--log",
        str(log_path),
        "--execute",
    ]

    if args.include_stock:
        cmd.append("--include-stock")

    run_live(cmd, cwd=SCRIPTS_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="楽天価格更新CSVの一連処理を自動実行します。calc → CSV出力 → SFTPアップロード → 成功/エラーDB反映。"
    )
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--limit", type=int, default=50000, help="CSV出力する最大SKU件数")
    parser.add_argument("--timeout", type=int, default=7200, help="SFTP監視タイムアウト秒")
    parser.add_argument("--settle-wait", type=int, default=600, help="batchからCSVが消えた後、ログなし成功判定まで待つ秒数")
    parser.add_argument("--poll-interval", type=int, default=15, help="監視間隔秒")
    parser.add_argument("--include-stock", action="store_true", help="在庫数もCSVに含め、成功時DBにも反映する")
    parser.add_argument("--include-stock-only", action="store_true", help="--include-stock 時、在庫差分だけの商品もCSV対象に含める")
    parser.add_argument("--include-blocked", action="store_true", help="CSV blocked商品もCSV対象に含める。通常は使わない")
    parser.add_argument("--allow-large-change", action="store_true", help="価格変更率が大きくてもCSV対象に含める")
    parser.add_argument("--skip-calc", action="store_true", help="calc_store_targets.py を実行しない")
    parser.add_argument("--skip-show", action="store_true", help="最後の show_update_targets.py を実行しない")
    parser.add_argument("--dry-run", action="store_true", help="アップロードもDB更新もせず、計算dry-runとCSV対象確認だけ行う")
    parser.add_argument("--execute", action="store_true", help="実際にCSV生成・アップロード・DB反映する")
    args = parser.parse_args()

    if args.include_stock_only and not args.include_stock:
        raise RuntimeError("--include-stock-only は --include-stock と一緒に指定してください。")

    if args.dry_run and args.execute:
        raise RuntimeError("--dry-run と --execute は同時に指定できません。")

    # 誤実行防止。--executeなしならdry-run扱い。
    if not args.execute:
        args.dry_run = True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_csv = OUTPUT_DIR / f"normal-item_price_{timestamp}.csv"
    check_csv = OUTPUT_DIR / f"normal-item_price_check_{timestamp}.csv"

    print("")
    print("===== 楽天CSV価格更新フロー開始 =====")
    print(f"mode        : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"store       : {args.store}")
    print(f"limit       : {args.limit}")
    print(f"output_csv  : {output_csv}")
    print(f"check_csv   : {check_csv}")
    print(f"settle_wait : {args.settle_wait}s")
    print("")

    # 1. 価格・在庫ターゲット計算
    if not args.skip_calc:
        calc_cmd = [
            sys.executable,
            str(script_path("calc_store_targets.py")),
            "--store",
            args.store,
        ]
        if args.dry_run:
            calc_cmd.append("--dry-run")
        run_live(calc_cmd, cwd=SCRIPTS_DIR)
    else:
        print("calc_store_targets.py はスキップします。")

    # 2. CSV生成
    export_cmd = build_export_args(args, output_csv, check_csv)
    run_live(export_cmd, cwd=SCRIPTS_DIR)

    if args.dry_run:
        print("")
        print("dry-run完了。実行する場合は --execute を付けてください。")
        return 0

    if not output_csv.exists():
        print("")
        print("CSVが作成されていません。更新対象がない可能性があります。")
        return 0

    # 3. SFTPアップロード＆監視
    watch_cmd = [
        sys.executable,
        str(script_path("rakuten_csv_winscp_upload_and_watch.py")),
        "--csv",
        str(output_csv),
        "--timeout",
        str(args.timeout),
        "--settle-wait",
        str(args.settle_wait),
        "--poll-interval",
        str(args.poll_interval),
    ]

    # watcher側ではDB反映させず、ここで成功/エラーをまとめて判定する
    rc, watch_output = run_live(watch_cmd, cwd=SCRIPTS_DIR, allow_error=True)

    # watcher の戻り値想定:
    # 0 = 成功扱い
    # 4 = エラーログあり
    # 3 = タイムアウト等
    if rc == 0:
        print("")
        print("SFTP監視結果: 成功扱い。DBへ成功反映します。")
        apply_success(output_csv, args)

    elif rc == 4:
        print("")
        print("SFTP監視結果: エラーログあり。成功分反映 + エラー商品blocked化を行います。")

        log_path = extract_log_path(watch_output)
        if log_path is None:
            log_path = find_latest_matching_log(output_csv)

        if log_path is None or not log_path.exists():
            raise RuntimeError(
                "エラーログのパスを特定できませんでした。"
                " C:\\price_system\\output\\rakuten_csv_logs を確認してください。"
            )

        print(f"使用するエラーログ: {log_path}")
        apply_result(output_csv, log_path, args)

    else:
        raise RuntimeError(
            f"SFTP監視が成功判定できませんでした returncode={rc}。"
            "楽天RMS画面、/ritem/batch、/ritem/logs を確認してください。"
        )

    # 4. 最終確認
    if not args.skip_show:
        show_cmd = [
            sys.executable,
            str(script_path("show_update_targets.py")),
            "--mall",
            "rakuten",
            "--limit",
            "50",
        ]
        run_live(show_cmd, cwd=SCRIPTS_DIR, allow_error=True)

    print("")
    print("===== 楽天CSV価格更新フロー完了 =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
