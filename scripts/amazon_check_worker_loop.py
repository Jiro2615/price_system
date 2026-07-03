import argparse
import locale
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import builtins
import os
from typing import Optional


BASE_DIR = Path(r"C:\price_system")
SCRIPTS_DIR = BASE_DIR / "scripts"
CONSOLE_ENCODING = "utf-8"
EMPTY_MARKER = "対象ASINがありません。"
SUMMARY_MARKER = "WORKER_RUN_SUMMARY "
LOG_DIR = BASE_DIR / "output" / "logs" / "amazon_check_worker"
LOG_STREAM: Optional[object] = None


def configure_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def safe_print(*args, **kwargs) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    flush = kwargs.get("flush", False)
    text = sep.join(str(arg) for arg in args)

    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        encoding = getattr(file, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        builtins.print(safe_text, end=end, file=file, flush=flush)

    if LOG_STREAM is not None:
        try:
            LOG_STREAM.write(text + end)
            if flush:
                LOG_STREAM.flush()
        except Exception:
            pass


configure_output()
print = safe_print


def sanitize_worker_id_for_filename(worker_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in worker_id.strip())
    return safe or "worker"


def cleanup_old_logs(retention_days: int) -> int:
    if retention_days < 0:
        return 0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cutoff_ts = time.time() - (retention_days * 86400)
    removed = 0

    for path in LOG_DIR.glob("*.log"):
        try:
            if path.stat().st_mtime < cutoff_ts:
                path.unlink()
                removed += 1
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return removed


def open_log_stream(worker_id: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y%m%d")
    safe_worker_id = sanitize_worker_id_for_filename(worker_id)
    log_path = LOG_DIR / f"{date_prefix}_{safe_worker_id}.log"
    stream = open(log_path, "a", encoding="utf-8", errors="replace")
    return log_path, stream


def script_path(name: str) -> Path:
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise RuntimeError(f"スクリプトが見つかりません: {path}")
    return path


def py_cmd(script_name: str) -> list[str]:
    return [sys.executable, "-u", str(script_path(script_name))]


def build_child_cmd(worker_id: str, limit: int, page_timeout: int) -> list[str]:
    return [
        *py_cmd("price_check_from_db.py"),
        "--limit",
        str(limit),
        "--summary",
        "--use-stats",
        "--worker-id",
        worker_id,
        "--page-timeout",
        str(page_timeout),
    ]


def parse_worker_run_summary(output_lines: list[str]) -> dict[str, str]:
    for line in output_lines:
        text = line.strip()
        if not text.startswith(SUMMARY_MARKER):
            continue

        summary: dict[str, str] = {}
        for part in text[len(SUMMARY_MARKER):].split():
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            summary[key] = value
        return summary

    return {}


def run_child_once(loop_index: int, cmd: list[str]) -> tuple[int, float, bool, dict[str, str]]:
    started = time.perf_counter()
    started_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    print("")
    print("============================================================")
    print(f"LOOP {loop_index} 開始")
    print(f"開始時刻 : {started_at}")
    print("コマンド:", " ".join(cmd))
    print("============================================================")
    print("")

    proc = subprocess.Popen(
        cmd,
        cwd=str(SCRIPTS_DIR),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=CONSOLE_ENCODING,
        errors="replace",
        bufsize=1,
    )

    output_lines: list[str] = []

    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
        output_lines.append(line)

    proc.wait()
    returncode = int(proc.returncode or 0)
    elapsed = time.perf_counter() - started
    finished_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    output_text = "".join(output_lines)
    empty_result = EMPTY_MARKER in output_text
    worker_summary = parse_worker_run_summary(output_lines)

    print("")
    print("------------------------------------------------------------")
    print(f"LOOP {loop_index} 終了")
    print(f"終了時刻 : {finished_at}")
    print(f"returncode: {returncode}")
    print(f"所要秒数  : {elapsed:.1f}s")
    print(f"対象0件   : {'YES' if empty_result else 'NO'}")
    if worker_summary:
        print("worker summary:")
        print(f"  worker_id           : {worker_summary.get('worker_id', '')}")
        print(f"  claimed_count       : {worker_summary.get('claimed_count', '')}")
        print(f"  checked_count       : {worker_summary.get('checked_count', '')}")
        print(f"  success_count       : {worker_summary.get('success_count', '')}")
        print(f"  system_error_count  : {worker_summary.get('system_error_count', '')}")
        print(f"  business_ng_count   : {worker_summary.get('business_ng_count', '')}")
        print(f"  changed_count       : {worker_summary.get('changed_count', '')}")
        print(f"  stable_count        : {worker_summary.get('stable_count', '')}")
        print(f"  page_reset_count    : {worker_summary.get('page_reset_count', '')}")
        print(f"  elapsed_seconds     : {worker_summary.get('elapsed_seconds', '')}")
        print(f"  avg_seconds_per_item: {worker_summary.get('avg_seconds_per_item', '')}")
        print(f"  started_at          : {worker_summary.get('started_at', '')}")
        print(f"  finished_at         : {worker_summary.get('finished_at', '')}")
        print(f"  returncode          : {worker_summary.get('returncode', '')}")
    print(f"結果      : {'SUCCESS' if returncode == 0 else 'FAILED'}")
    print("------------------------------------------------------------")

    return returncode, elapsed, empty_result, worker_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="price_check_from_db.py --use-stats を一定間隔で繰り返し呼ぶ Amazon チェックワーカーループ"
    )
    parser.add_argument("--worker-id", required=True, help="ワーカーID")
    parser.add_argument("--limit", type=int, default=300, help="1ループあたりの最大チェック件数")
    parser.add_argument("--sleep", type=int, default=10, help="通常時の待機秒数")
    parser.add_argument("--page-timeout", type=int, default=60000, help="price_check_from_db.py に渡す page.goto timeout(ms)")
    parser.add_argument("--max-loops", type=int, default=0, help="最大ループ回数。0なら無制限")
    parser.add_argument("--stop-after-empty", action="store_true", help="対象0件ならその場で終了する")
    parser.add_argument("--empty-sleep", type=int, default=60, help="対象0件だった時の待機秒数")
    parser.add_argument("--once", action="store_true", help="1回だけ実行して終了する")
    parser.add_argument("--log-retention-days", type=int, default=14, help="保持日数を過ぎた古いログを起動時に削除する")
    args = parser.parse_args()

    if args.limit <= 0:
        raise RuntimeError("--limit は 1 以上にしてください。")
    if args.sleep < 0:
        raise RuntimeError("--sleep は 0 以上にしてください。")
    if args.page_timeout <= 0:
        raise RuntimeError("--page-timeout は 1 以上にしてください。")
    if args.empty_sleep < 0:
        raise RuntimeError("--empty-sleep は 0 以上にしてください。")
    if args.max_loops < 0:
        raise RuntimeError("--max-loops は 0 以上にしてください。")
    if args.log_retention_days < 0:
        raise RuntimeError("--log-retention-days は 0 以上にしてください。")

    removed_logs = cleanup_old_logs(args.log_retention_days)

    global LOG_STREAM
    log_path, LOG_STREAM = open_log_stream(args.worker_id)

    try:
        print("")
        print("===== Amazonチェックワーカーループ開始 =====")
        print(f"worker_id         : {args.worker_id}")
        print(f"limit             : {args.limit}")
        print(f"sleep             : {args.sleep}")
        print(f"page_timeout      : {args.page_timeout}")
        print(f"empty_sleep       : {args.empty_sleep}")
        print(f"max_loops         : {args.max_loops}")
        print(f"stop_after_empty  : {args.stop_after_empty}")
        print(f"once              : {args.once}")
        print(f"encoding          : {CONSOLE_ENCODING}")
        print(f"log_path          : {log_path}")
        print(f"log_retention_days: {args.log_retention_days}")
        print(f"removed_old_logs  : {removed_logs}")

        loop_index = 0

        while True:
            loop_index += 1
            cmd = build_child_cmd(args.worker_id, args.limit, args.page_timeout)
            returncode, _elapsed, empty_result, worker_summary = run_child_once(loop_index, cmd)

            if returncode != 0:
                print("")
                print("===== Amazonチェックワーカーループ異常終了 =====")
                print(f"失敗ループ : {loop_index}")
                print(f"returncode: {returncode}")
                if worker_summary:
                    print(f"worker_id : {worker_summary.get('worker_id', '')}")
                    print(f"claimed   : {worker_summary.get('claimed_count', '')}")
                    print(f"checked   : {worker_summary.get('checked_count', '')}")
                return returncode

            if args.once:
                print("")
                print("once指定のため終了します。")
                return 0

            if args.max_loops and loop_index >= args.max_loops:
                print("")
                print(f"--max-loops={args.max_loops} に達したため終了します。")
                return 0

            if empty_result and args.stop_after_empty:
                print("")
                print("--stop-after-empty 指定のため、対象0件で終了します。")
                return 0

            wait_seconds = args.empty_sleep if empty_result else args.sleep
            print("")
            print(f"次ループまで {wait_seconds} 秒待機します。")
            time.sleep(wait_seconds)
    finally:
        if LOG_STREAM is not None:
            try:
                LOG_STREAM.flush()
                LOG_STREAM.close()
            except Exception:
                pass
            LOG_STREAM = None


if __name__ == "__main__":
    raise SystemExit(main())
