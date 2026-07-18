import argparse
import builtins
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from settings_loader import WORKER_TYPE_RAKUTEN, load_resolved_worker_settings


BASE_DIR = Path(r"C:\price_system")
SCRIPTS_DIR = BASE_DIR / "scripts"
CONSOLE_ENCODING = "utf-8"

CLI_TO_SETTING_KEY = {
    "price_limit": "price_limit",
    "stock_limit": "stock_limit",
    "blocked_limit": "blocked_limit",
    "empty_sleep": "empty_sleep_seconds",
    "error_sleep": "error_sleep_seconds",
    "verify": "verify",
    "api_interval": "api_interval_seconds",
    "verify_wait": "verify_wait_seconds",
    "retry_count": "retry_count",
    "retry_wait": "retry_wait_seconds",
    "max_change_rate": "max_change_rate",
    "inventory_batch_size": "inventory_batch_size",
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
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        file = kwargs.get("file", sys.stdout)
        flush = kwargs.get("flush", False)
        text = sep.join(str(arg) for arg in args)
        encoding = getattr(file, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        builtins.print(safe_text, end=end, file=file, flush=flush)


configure_output()
print = safe_print


def script_path(name: str) -> Path:
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise RuntimeError(f"script not found: {path}")
    return path


def py_cmd(script_name: str) -> list[str]:
    return [sys.executable, "-u", str(script_path(script_name))]


def run_live_step(loop_index: int, step_name: str, cmd: list[str]) -> tuple[int, float, str]:
    started = time.perf_counter()
    started_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    print("")
    print("============================================================")
    print(f"LOOP {loop_index} START {step_name}")
    print(f"started_at : {started_at}")
    print("command    :", " ".join(cmd))
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
        print(line, end="", flush=True)
        output_lines.append(line)

    proc.wait()
    returncode = int(proc.returncode or 0)
    elapsed = time.perf_counter() - started
    finished_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    print("")
    print("------------------------------------------------------------")
    print(f"LOOP {loop_index} END {step_name}")
    print(f"finished_at: {finished_at}")
    print(f"returncode : {returncode}")
    print(f"elapsed    : {elapsed:.1f}s")
    print(f"result     : {'SUCCESS' if returncode == 0 else 'FAILED'}")
    print("------------------------------------------------------------")

    return returncode, elapsed, "".join(output_lines)


def parse_count(output: str, labels: list[str]) -> int | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*:\s*(\d+)"
        match = re.search(pattern, output)
        if match:
            return int(match.group(1))
    return None


def analyze_step_output(step_name: str, output: str, step_limit: int) -> dict[str, Any]:
    target_count = parse_count(output, ["楽天在庫更新対象件数", "楽天価格更新対象件数", "API更新対象件数"])
    success_count = parse_count(output, ["成功件数"])
    failed_count = parse_count(output, ["失敗件数"])
    skipped_count = parse_count(output, ["スキップ件数"])

    had_targets = bool(target_count and target_count > 0)
    hit_limit = bool(target_count is not None and step_limit > 0 and target_count >= step_limit)

    return {
        "step_name": step_name,
        "target_count": target_count,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "had_targets": had_targets,
        "hit_limit": hit_limit,
    }


def log_next_action(action: str, reason: str, seconds: int | float | None = None) -> None:
    if seconds is None:
        print(f"next_action={action} reason={reason}")
    else:
        print(f"next_action={action} seconds={seconds} reason={reason}")


def build_inventory_cmd(args, resolved_settings: dict[str, dict[str, Any]]) -> list[str]:
    cmd = [
        *py_cmd("rakuten_inventory_bulk_upsert.py"),
        "--store",
        args.store,
        "--limit",
        str(resolved_settings["stock_limit"]["value"]),
        "--batch-size",
        str(resolved_settings["inventory_batch_size"]["value"]),
    ]
    if args.execute:
        cmd.append("--execute")
    return cmd


def build_price_cmd(args, resolved_settings: dict[str, dict[str, Any]]) -> list[str]:
    cmd = [
        *py_cmd("rakuten_price_patch.py"),
        "--store",
        args.store,
        "--limit",
        str(resolved_settings["price_limit"]["value"]),
        "--api-interval",
        str(resolved_settings["api_interval_seconds"]["value"]),
        "--verify-wait",
        str(resolved_settings["verify_wait_seconds"]["value"]),
        "--retry-count",
        str(resolved_settings["retry_count"]["value"]),
        "--retry-wait",
        str(resolved_settings["retry_wait_seconds"]["value"]),
        "--max-change-rate",
        str(resolved_settings["max_change_rate"]["value"]),
    ]
    cmd.append("--verify" if resolved_settings["verify"]["value"] else "--no-verify")
    if args.execute:
        cmd.append("--execute")
    return cmd


def build_blocked_cmd(args, resolved_settings: dict[str, dict[str, Any]]) -> list[str]:
    cmd = [
        *py_cmd("rakuten_price_patch.py"),
        "--store",
        args.store,
        "--blocked-only",
        "--limit",
        str(resolved_settings["blocked_limit"]["value"]),
        "--api-interval",
        str(resolved_settings["api_interval_seconds"]["value"]),
        "--verify-wait",
        str(resolved_settings["verify_wait_seconds"]["value"]),
        "--retry-count",
        str(resolved_settings["retry_count"]["value"]),
        "--retry-wait",
        str(resolved_settings["retry_wait_seconds"]["value"]),
        "--max-change-rate",
        str(resolved_settings["max_change_rate"]["value"]),
    ]
    cmd.append("--verify" if resolved_settings["verify"]["value"] else "--no-verify")
    if args.execute:
        cmd.append("--execute")
    return cmd


def build_steps(args, resolved_settings: dict[str, dict[str, Any]]) -> list[tuple[str, list[str], int]]:
    stock_limit = int(resolved_settings["stock_limit"]["value"])
    price_limit = int(resolved_settings["price_limit"]["value"])
    blocked_limit = int(resolved_settings["blocked_limit"]["value"])
    steps: list[tuple[str, list[str], int]] = [
        ("inventory update", build_inventory_cmd(args, resolved_settings), stock_limit),
        ("price update", build_price_cmd(args, resolved_settings), price_limit),
    ]

    if blocked_limit > 0:
        steps.append(("blocked fallback", build_blocked_cmd(args, resolved_settings), blocked_limit))

    return steps


def build_cli_overrides(args) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for arg_name, setting_key in CLI_TO_SETTING_KEY.items():
        value = getattr(args, arg_name)
        if value is not None:
            overrides[setting_key] = value
    return overrides


def print_resolved_config(data: dict[str, Any]) -> None:
    print("")
    print("===== Resolved Worker Settings =====")
    print(f"worker_config_id : {data['worker_config_id']}")
    print(f"worker_id        : {data['worker_id']}")
    print(f"node_code        : {data['node_code']}")
    print(f"hostname         : {data['hostname']}")
    print(f"store_code       : {data['store_code']}")
    print(f"revision         : {data['revision']}")
    print(f"enabled          : {data['enabled']}")
    print(f"desired_state    : {data['desired_state']}")
    print("resolved_settings:")
    for key, item in data["resolved_settings"].items():
        print(f"  {key}: value={item['value']} source={item['source']}")
    print("")


def print_generated_commands(steps: list[tuple[str, list[str], int]]) -> None:
    print("generated_commands:")
    for step_name, cmd, _step_limit in steps:
        print(f"  {step_name}: {' '.join(cmd)}")
    print("")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rakuten update worker loop. Calls inventory and price update scripts repeatedly without CSV or Amazon checks."
    )
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--node-code", default="", help="override worker_nodes.node_code for config lookup")
    parser.add_argument("--worker-id", default="", help="optional explicit worker_id override")
    parser.add_argument("--price-limit", type=int, default=None, help="override price_limit")
    parser.add_argument("--stock-limit", type=int, default=None, help="override stock_limit")
    parser.add_argument("--blocked-limit", type=int, default=None, help="override blocked_limit")
    parser.add_argument("--empty-sleep", type=int, default=None, help="override empty_sleep_seconds")
    parser.add_argument("--error-sleep", type=int, default=None, help="override error_sleep_seconds")
    parser.add_argument("--verify", action=argparse.BooleanOptionalAction, default=None, help="override verify")
    parser.add_argument("--api-interval", type=float, default=None, help="override api_interval_seconds")
    parser.add_argument("--verify-wait", type=float, default=None, help="override verify_wait_seconds")
    parser.add_argument("--retry-count", type=int, default=None, help="override retry_count")
    parser.add_argument("--retry-wait", type=float, default=None, help="override retry_wait_seconds")
    parser.add_argument("--max-change-rate", type=float, default=None, help="override max_change_rate")
    parser.add_argument("--inventory-batch-size", type=int, default=None, help="override inventory_batch_size")
    parser.add_argument("--execute", action="store_true", help="actually call Rakuten APIs")
    parser.add_argument("--once", action="store_true", help="run one loop only")
    parser.add_argument("--max-loops", type=int, default=0, help="maximum loop count. 0 means unlimited")
    parser.add_argument("--stop-on-error", action="store_true", help="stop immediately when a child step fails")
    args = parser.parse_args()

    if args.max_loops < 0:
        raise RuntimeError("--max-loops must be 0 or greater")

    cli_overrides = build_cli_overrides(args)
    resolved_worker = load_resolved_worker_settings(
        worker_type=WORKER_TYPE_RAKUTEN,
        store_code=args.store,
        node_code=args.node_code.strip() or None,
        explicit_worker_id=args.worker_id.strip() or None,
        cli_overrides=cli_overrides,
    )
    resolved_settings = resolved_worker["resolved_settings"]
    steps = build_steps(args, resolved_settings)
    empty_sleep_seconds = int(resolved_settings["empty_sleep_seconds"]["value"])
    error_sleep_seconds = int(resolved_settings["error_sleep_seconds"]["value"])

    print("")
    print("===== Rakuten Update Worker Loop =====")
    print(f"mode             : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"store            : {args.store}")
    print(f"once             : {args.once}")
    print(f"max_loops        : {args.max_loops}")
    print(f"stop_on_error    : {args.stop_on_error}")
    print(f"encoding         : {CONSOLE_ENCODING}")
    print_resolved_config(resolved_worker)
    print_generated_commands(steps)

    loop_index = 0

    while True:
        loop_index += 1
        loop_started = time.perf_counter()
        loop_started_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        summary: list[tuple[str, int, float, dict[str, Any]]] = []

        print("")
        print("############################################################")
        print(f"LOOP {loop_index} BEGIN")
        print(f"started_at : {loop_started_at}")
        print("############################################################")

        failed = False
        failed_step_name = ""
        failed_returncode = 0
        had_targets_any = False
        hit_limit_any = False

        for step_name, cmd, step_limit in steps:
            returncode, elapsed, output = run_live_step(loop_index, step_name, cmd)
            analysis = analyze_step_output(step_name, output, step_limit)
            summary.append((step_name, returncode, elapsed, analysis))

            had_targets_any = had_targets_any or analysis["had_targets"]
            hit_limit_any = hit_limit_any or analysis["hit_limit"]

            if returncode != 0:
                failed = True
                failed_step_name = step_name
                failed_returncode = returncode
                break

        loop_elapsed = time.perf_counter() - loop_started
        loop_finished_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        print("")
        print("===== LOOP SUMMARY =====")
        print(f"loop            : {loop_index}")
        print(f"started_at      : {loop_started_at}")
        print(f"finished_at     : {loop_finished_at}")
        print(f"elapsed_seconds : {loop_elapsed:.1f}")
        for step_name, returncode, elapsed, analysis in summary:
            print(
                f"{step_name}: "
                f"returncode={returncode}, "
                f"elapsed={elapsed:.1f}s, "
                f"target_count={analysis.get('target_count')}, "
                f"success_count={analysis.get('success_count')}, "
                f"failed_count={analysis.get('failed_count')}, "
                f"skipped_count={analysis.get('skipped_count')}"
            )
        print(f"had_targets_any : {had_targets_any}")
        print(f"hit_limit_any   : {hit_limit_any}")

        if failed:
            print("")
            print("Rakuten update worker loop detected an error.")
            print(f"failed_step : {failed_step_name}")
            print(f"returncode  : {failed_returncode}")

            if args.stop_on_error:
                log_next_action("exit", "stop_on_error")
                print("stop_on_error is enabled. Exiting.")
                return failed_returncode

            if args.once:
                log_next_action("exit", "once_child_error")
                print("once is set. Exiting after one loop.")
                return failed_returncode

            if args.max_loops and loop_index >= args.max_loops:
                log_next_action("exit", "max_loops_reached_after_error")
                print(f"--max-loops={args.max_loops} reached. Exiting.")
                return failed_returncode

            print("")
            log_next_action("sleep_error", "child_error", error_sleep_seconds)
            print(f"Error detected. Sleeping {error_sleep_seconds} seconds before next loop.")
            time.sleep(error_sleep_seconds)
            continue

        if args.once:
            print("")
            log_next_action("exit", "once")
            print("once is set. Exiting after one loop.")
            return 0

        if args.max_loops and loop_index >= args.max_loops:
            print("")
            log_next_action("exit", "max_loops_reached")
            print(f"--max-loops={args.max_loops} reached. Exiting.")
            return 0

        if had_targets_any or hit_limit_any:
            print("")
            log_next_action("continue_immediately", "limit_reached" if hit_limit_any else "targets_remaining")
            print("Updates were detected in this loop. Starting next loop immediately.")
            continue

        print("")
        log_next_action("sleep_empty", "no_targets", empty_sleep_seconds)
        print(f"No update targets detected. Sleeping {empty_sleep_seconds} seconds before next loop.")
        time.sleep(empty_sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
