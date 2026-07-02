import argparse
import locale
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(r"C:\price_system")
SCRIPTS_DIR = BASE_DIR / "scripts"
CONSOLE_ENCODING = locale.getpreferredencoding(False) or "cp932"
EMPTY_MARKER = "対象ASINがありません。"


def script_path(name: str) -> Path:
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise RuntimeError(f"必要なスクリプトが見つかりません: {path}")
    return path


def py_cmd(script_name: str) -> list[str]:
    return [sys.executable, "-u", str(script_path(script_name))]


def build_child_cmd(worker_id: str, limit: int) -> list[str]:
    return [
        *py_cmd("price_check_from_db.py"),
        "--limit",
        str(limit),
        "--summary",
        "--use-stats",
        "--worker-id",
        worker_id,
    ]


def run_child_once(loop_index: int, cmd: list[str]) -> tuple[int, float, bool]:
    started = time.perf_counter()
    started_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    print("")
    print("============================================================")
    print(f"LOOP {loop_index} 開始")
    print(f"開始時刻 : {started_at}")
    print("コマンド :", " ".join(cmd))
    print("============================================================")
    print("")

    proc = subprocess.Popen(
        cmd,
        cwd=str(SCRIPTS_DIR),
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

    print("")
    print("------------------------------------------------------------")
    print(f"LOOP {loop_index} 終了")
    print(f"終了時刻 : {finished_at}")
    print(f"returncode: {returncode}")
    print(f"所要秒数  : {elapsed:.1f}s")
    print(f"対象0件   : {'YES' if empty_result else 'NO'}")
    print(f"結果      : {'SUCCESS' if returncode == 0 else 'FAILED'}")
    print("------------------------------------------------------------")

    return returncode, elapsed, empty_result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="price_check_from_db.py --use-stats を一定間隔で繰り返し実行するAmazonチェックワーカーループ"
    )
    parser.add_argument("--worker-id", required=True, help="ワーカーID")
    parser.add_argument("--limit", type=int, default=300, help="1ループあたりの最大チェック件数")
    parser.add_argument("--sleep", type=int, default=10, help="通常時の待機秒数")
    parser.add_argument("--max-loops", type=int, default=0, help="最大ループ回数。0なら無制限")
    parser.add_argument("--stop-after-empty", action="store_true", help="対象0件ならその時点で終了する")
    parser.add_argument("--empty-sleep", type=int, default=60, help="対象0件だった時の待機秒数")
    parser.add_argument("--once", action="store_true", help="1回だけ実行して終了する")
    args = parser.parse_args()

    if args.limit <= 0:
        raise RuntimeError("--limit は 1以上にしてください。")
    if args.sleep < 0:
        raise RuntimeError("--sleep は 0以上にしてください。")
    if args.empty_sleep < 0:
        raise RuntimeError("--empty-sleep は 0以上にしてください。")
    if args.max_loops < 0:
        raise RuntimeError("--max-loops は 0以上にしてください。")

    print("")
    print("===== Amazonチェックワーカーループ開始 =====")
    print(f"worker_id       : {args.worker_id}")
    print(f"limit           : {args.limit}")
    print(f"sleep           : {args.sleep}")
    print(f"empty_sleep     : {args.empty_sleep}")
    print(f"max_loops       : {args.max_loops}")
    print(f"stop_after_empty: {args.stop_after_empty}")
    print(f"once            : {args.once}")
    print(f"encoding        : {CONSOLE_ENCODING}")

    loop_index = 0

    while True:
        loop_index += 1
        cmd = build_child_cmd(args.worker_id, args.limit)
        returncode, _elapsed, empty_result = run_child_once(loop_index, cmd)

        if returncode != 0:
            print("")
            print("===== Amazonチェックワーカーループ中断 =====")
            print(f"失敗ループ: {loop_index}")
            print(f"returncode: {returncode}")
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


if __name__ == "__main__":
    raise SystemExit(main())
