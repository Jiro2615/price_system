import argparse
import builtins
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from db_config import connect_db
from db_retry import DB_RETRY_EXIT_CODE, is_retryable_db_error
from settings_loader import WORKER_TYPE_AMAZON, load_resolved_worker_settings


BASE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BASE_DIR / "scripts"
CONSOLE_ENCODING = "utf-8"
EMPTY_MARKER = "対象ASINがありません。"
SUMMARY_MARKER = "WORKER_RUN_SUMMARY "
LOG_DIR = BASE_DIR / "output" / "logs" / "amazon_check_worker"
LOG_STREAM: Optional[object] = None
DB_RECOVERY_WAIT_SECONDS = 60

CLI_TO_SETTING_KEY = {
    "limit": "limit",
    "sleep": "loop_sleep_seconds",
    "empty_sleep": "empty_sleep_seconds",
    "page_timeout": "page_timeout_ms",
    "use_stats": "use_stats",
    "log_retention_days": "log_retention_days",
}


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


def open_log_stream(worker_id: str) -> tuple[Path, object]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y%m%d")
    safe_worker_id = sanitize_worker_id_for_filename(worker_id)
    log_path = LOG_DIR / f"{date_prefix}_{safe_worker_id}.log"
    stream = open(log_path, "a", encoding="utf-8", errors="replace")
    return log_path, stream


def script_path(name: str) -> Path:
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise RuntimeError(f"script not found: {path}")
    return path


def py_cmd(script_name: str) -> list[str]:
    return [sys.executable, "-u", str(script_path(script_name))]


def build_cli_overrides(args: argparse.Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for arg_name, setting_key in CLI_TO_SETTING_KEY.items():
        value = getattr(args, arg_name)
        if value is not None:
            overrides[setting_key] = value
    return overrides


def build_child_cmd(
    worker_id: str,
    resolved_settings: dict[str, dict[str, Any]],
    recheck_system_errors: bool = False,
    reason_contains: str = "",
    asin_file: str = "",
    dry_run: bool = False,
    store_code: str = "",
    listed_only: bool = False,
) -> list[str]:
    cmd = [
        *py_cmd("price_check_from_db.py"),
        "--limit",
        str(resolved_settings["limit"]["value"]),
        "--summary",
        "--worker-id",
        worker_id,
        "--page-timeout",
        str(resolved_settings["page_timeout_ms"]["value"]),
    ]
    cmd.append("--no-use-stats" if asin_file else "--use-stats" if resolved_settings["use_stats"]["value"] else "--no-use-stats")
    if recheck_system_errors:
        cmd.append("--system-error-only")
    if reason_contains:
        cmd.extend(["--reason-contains", reason_contains])
    if asin_file:
        cmd.extend(["--asin-file", asin_file])
    if listed_only:
        cmd.extend(["--store-code", store_code, "--listed-only"])
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def print_resolved_config(data: dict[str, Any]) -> None:
    print("")
    print("===== Resolved Worker Settings =====")
    print(f"worker_config_id : {data['worker_config_id']}")
    print(f"worker_id        : {data['worker_id']}")
    print(f"node_code        : {data['node_code']}")
    print(f"hostname         : {data['hostname']}")
    print(f"worker_number    : {data['worker_number']}")
    print(f"revision         : {data['revision']}")
    print(f"enabled          : {data['enabled']}")
    print(f"desired_state    : {data['desired_state']}")
    print("resolved_settings:")
    for key, item in data["resolved_settings"].items():
        print(f"  {key}: value={item['value']} source={item['source']}")
    print("")


def print_generated_command(cmd: list[str]) -> None:
    print("generated_command:")
    print(f"  {' '.join(cmd)}")
    print("")


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


def get_last_error_line(output_lines: list[str]) -> str:
    for line in reversed(output_lines):
        text = line.strip()
        if not text:
            continue
        if "error" in text.casefold():
            return text
    return output_lines[-1].strip() if output_lines else ""


def check_db_connection_once() -> None:
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        conn.close()


def wait_for_db_recovery(wait_seconds: int = DB_RECOVERY_WAIT_SECONDS) -> None:
    while True:
        try:
            check_db_connection_once()
            print("DB connection check: OK")
            return
        except Exception as error:
            if not is_retryable_db_error(error):
                raise
            print(
                "DB connection check failed: "
                f"wait_seconds={wait_seconds} error={error.__class__.__name__}: {error}"
            )
            time.sleep(wait_seconds)


def run_child_once(
    loop_index: int,
    cmd: list[str],
    should_stop_requested: Callable[[], bool] | None = None,
) -> tuple[int, float, bool, dict[str, str], str, bool]:
    started = time.perf_counter()
    started_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    print("")
    print("============================================================")
    print(f"LOOP {loop_index} START")
    print(f"started_at : {started_at}")
    print("command    :", " ".join(cmd))
    print("============================================================")
    print("")

    proc = subprocess.Popen(
        cmd,
        cwd=str(SCRIPTS_DIR),
        env={
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=CONSOLE_ENCODING,
        errors="replace",
        bufsize=1,
    )

    assert proc.stdout is not None
    output_lines: list[str] = []
    output_queue: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        try:
            for line in proc.stdout:
                output_queue.put(line)
        finally:
            output_queue.put(None)

    threading.Thread(target=read_output, name=f"amazon-worker-output-{loop_index}", daemon=True).start()
    stop_requested = False
    output_closed = False
    while not output_closed:
        try:
            line = output_queue.get(timeout=1)
        except queue.Empty:
            if not stop_requested and should_stop_requested is not None:
                try:
                    stop_requested = bool(should_stop_requested())
                except Exception as error:
                    print(f"stop-state check failed: {error}", flush=True)
                if stop_requested and proc.poll() is None:
                    print("desired_state=stopped detected during child run. Terminating child process tree.", flush=True)
                    try:
                        if os.name == "nt":
                            subprocess.run(
                                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                check=False,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=15,
                            )
                        else:
                            proc.terminate()
                    except (OSError, subprocess.SubprocessError) as error:
                        print(f"child stop dispatch failed: {error}", flush=True)
            continue
        if line is None:
            output_closed = True
            continue
        print(line, end="", flush=True)
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
    print(f"LOOP {loop_index} END")
    print(f"finished_at: {finished_at}")
    print(f"returncode : {returncode}")
    print(f"elapsed    : {elapsed:.1f}s")
    print(f"empty_run  : {'YES' if empty_result else 'NO'}")
    if worker_summary:
        print("worker_summary:")
        for key in [
            "worker_id",
            "claimed_count",
            "checked_count",
            "success_count",
            "system_error_count",
            "business_ng_count",
            "changed_count",
            "stable_count",
            "page_reset_count",
            "elapsed_seconds",
            "avg_seconds_per_item",
            "started_at",
            "finished_at",
            "returncode",
        ]:
            print(f"  {key}: {worker_summary.get(key, '')}")
    print(f"stop_requested: {'YES' if stop_requested else 'NO'}")
    print(f"result     : {'SUCCESS' if returncode == 0 or stop_requested else 'FAILED'}")
    print("------------------------------------------------------------")

    return returncode, elapsed, empty_result, worker_summary, get_last_error_line(output_lines), stop_requested


def add_bool_override(
    parser: argparse.ArgumentParser,
    name: str,
    dest: str,
    help_true: str,
    help_false: str,
) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(name, dest=dest, action="store_true", help=help_true)
    group.add_argument(f"--no-{name[2:]}", dest=dest, action="store_false", help=help_false)
    parser.set_defaults(**{dest: None})


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Amazon check worker loop using DB-managed worker configuration."
    )
    parser.add_argument("--worker-number", type=int, required=True, help="worker_configs.worker_number")
    parser.add_argument("--node-code", default="", help="override worker_nodes.node_code for config lookup")
    parser.add_argument("--worker-id", default="", help="optional explicit worker_id override")
    parser.add_argument("--limit", type=int, default=None, help="override limit")
    parser.add_argument("--sleep", type=int, default=None, help="override loop_sleep_seconds")
    parser.add_argument("--empty-sleep", type=int, default=None, help="override empty_sleep_seconds")
    parser.add_argument("--page-timeout", type=int, default=None, help="override page_timeout_ms")
    add_bool_override(parser, "--use-stats", "use_stats", "override use_stats", "override no use_stats")
    parser.add_argument("--log-retention-days", type=int, default=None, help="override log_retention_days")
    parser.add_argument("--max-loops", type=int, default=0, help="maximum loop count. 0 means unlimited")
    parser.add_argument("--stop-after-empty", action="store_true", help="stop when the child reports no target ASINs")
    parser.add_argument("--once", action="store_true", help="run one loop only")
    parser.add_argument("--recheck-system-errors", action="store_true", help="recheck amazon_products.system_error = TRUE only")
    parser.add_argument("--reason-contains", default="", help="filter system error recheck by ng_reason partial match")
    parser.add_argument("--asin-file", default="", help="explicit ASIN target file for direct checks")
    parser.add_argument("--store-code", default="", help="Rakuten store_code used with --listed-only")
    parser.add_argument("--listed-only", action="store_true", help="only active listed products mapped to --store-code")
    parser.add_argument("--dry-run", action="store_true", help="show target ASINs only without browser start or DB updates")
    parser.add_argument("--resolve-only", action="store_true", help="resolve settings and print child command without running it")
    args = parser.parse_args()

    if args.worker_number <= 0:
        raise RuntimeError("--worker-number must be 1 or greater")
    if args.max_loops < 0:
        raise RuntimeError("--max-loops must be 0 or greater")
    if args.reason_contains and not args.recheck_system_errors:
        raise RuntimeError("--reason-contains requires --recheck-system-errors")
    if args.listed_only and not args.store_code.strip():
        raise RuntimeError("--listed-only requires --store-code")

    cli_overrides = build_cli_overrides(args)

    def resolve_worker() -> dict[str, Any]:
        return load_resolved_worker_settings(
            worker_type=WORKER_TYPE_AMAZON,
            worker_number=args.worker_number,
            node_code=args.node_code.strip() or None,
            explicit_worker_id=args.worker_id.strip() or None,
            cli_overrides=cli_overrides,
        )

    resolved_worker = resolve_worker()
    resolved_settings = resolved_worker["resolved_settings"]
    loop_sleep_seconds = int(resolved_settings["loop_sleep_seconds"]["value"])
    empty_sleep_seconds = int(resolved_settings["empty_sleep_seconds"]["value"])
    log_retention_days = int(resolved_settings["log_retention_days"]["value"])
    child_cmd = build_child_cmd(
        resolved_worker["worker_id"],
        resolved_settings,
        recheck_system_errors=args.recheck_system_errors,
        reason_contains=args.reason_contains,
        asin_file=args.asin_file.strip(),
        store_code=args.store_code.strip(),
        listed_only=args.listed_only,
        dry_run=args.dry_run,
    )

    removed_logs = cleanup_old_logs(log_retention_days)

    global LOG_STREAM
    log_path, LOG_STREAM = open_log_stream(resolved_worker["worker_id"])

    try:
        print("")
        print("===== Amazon Check Worker Loop =====")
        print(f"worker_number      : {args.worker_number}")
        print(f"once               : {args.once}")
        print(f"max_loops          : {args.max_loops}")
        print(f"stop_after_empty   : {args.stop_after_empty}")
        print(f"recheck_system_errors : {args.recheck_system_errors}")
        print(f"reason_contains    : {args.reason_contains}")
        print(f"asin_file          : {args.asin_file}")
        print(f"dry_run            : {args.dry_run}")
        print(f"resolve_only       : {args.resolve_only}")
        print(f"encoding           : {CONSOLE_ENCODING}")
        print(f"log_path           : {log_path}")
        print(f"log_retention_days : {log_retention_days}")
        print(f"removed_old_logs   : {removed_logs}")
        print_resolved_config(resolved_worker)
        print_generated_command(child_cmd)

        if args.resolve_only:
            print("resolve_only is set. Exiting without starting child worker.")
            return 0

        loop_index = 0
        consecutive_db_failures = 0
        last_db_error = ""

        while True:
            resolved_worker = resolve_worker()
            if str(resolved_worker.get("desired_state", "")).strip().lower() == "stopped":
                print("")
                print("desired_state=stopped detected. Exiting worker loop.")
                return 0

            resolved_settings = resolved_worker["resolved_settings"]
            loop_sleep_seconds = int(resolved_settings["loop_sleep_seconds"]["value"])
            empty_sleep_seconds = int(resolved_settings["empty_sleep_seconds"]["value"])
            child_cmd = build_child_cmd(
                resolved_worker["worker_id"],
                resolved_settings,
                recheck_system_errors=args.recheck_system_errors,
                reason_contains=args.reason_contains,
                asin_file=args.asin_file.strip(),
                store_code=args.store_code.strip(),
                listed_only=args.listed_only,
                dry_run=args.dry_run,
            )
            loop_index += 1
            returncode, _elapsed, empty_result, worker_summary, child_error_line, child_stop_requested = run_child_once(
                loop_index,
                child_cmd,
                should_stop_requested=lambda: str(resolve_worker().get("desired_state", "")).strip().lower() == "stopped",
            )

            if child_stop_requested:
                print("desired_state=stopped detected during child run. Exiting worker loop.")
                return 0

            if returncode != 0:
                if returncode == DB_RETRY_EXIT_CODE:
                    consecutive_db_failures += 1
                    last_db_error = child_error_line or f"child_returncode={returncode}"
                    print("")
                    print("===== Amazon Check Worker Loop DB Retry =====")
                    print(f"failed_loop              : {loop_index}")
                    print(f"consecutive_db_failures  : {consecutive_db_failures}")
                    print(f"last_db_error            : {last_db_error}")
                    wait_for_db_recovery(DB_RECOVERY_WAIT_SECONDS)
                    consecutive_db_failures = 0
                    last_db_error = ""
                    continue

                print("")
                print("===== Amazon Check Worker Loop Error =====")
                print(f"failed_loop : {loop_index}")
                print(f"returncode  : {returncode}")
                if worker_summary:
                    print(f"worker_id   : {worker_summary.get('worker_id', '')}")
                    print(f"claimed     : {worker_summary.get('claimed_count', '')}")
                    print(f"checked     : {worker_summary.get('checked_count', '')}")
                return returncode

            if args.once:
                print("")
                print("once is set. Exiting after one loop.")
                return 0

            if args.max_loops and loop_index >= args.max_loops:
                print("")
                print(f"--max-loops={args.max_loops} reached. Exiting.")
                return 0

            if empty_result and args.stop_after_empty:
                print("")
                print("--stop-after-empty is set. Exiting after empty loop.")
                return 0

            wait_seconds = empty_sleep_seconds if empty_result else loop_sleep_seconds
            print("")
            print(f"Sleeping {wait_seconds} seconds before next loop.")
            time.sleep(wait_seconds)
    except KeyboardInterrupt:
        print("")
        print("KeyboardInterrupt received. Exiting worker loop.")
        return 130
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
