"""Continuous store-scoped Rakuten price API worker.

Each cycle delegates the actual items.patch work to the existing, audited
single-run script.  The child is intentionally kept in this process tree so
the Web Orchestrator can stop the whole tree through its managed run id.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from db_config import connect_db


SCRIPT_DIR = Path(__file__).resolve().parent
PATCH_SCRIPT = SCRIPT_DIR / "rakuten_price_patch.py"


def run_is_enabled(run_id: str) -> bool:
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT desired_state FROM job_runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
            return bool(row and str(row[0] or "").lower() == "running")
    finally:
        conn.close()


def wait_until_next_cycle(run_id: str, seconds: int) -> bool:
    for _ in range(max(0, seconds)):
        if not run_is_enabled(run_id):
            return False
        time.sleep(1)
    return run_is_enabled(run_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous Rakuten price API worker")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store", default="rakuten_2")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--cycle-wait", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-change-rate", type=float, default=0.5)
    parser.add_argument("--allow-large-change", action="store_true")
    parser.add_argument("--api-interval", type=float, default=1.5)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--retry-count", type=int, default=5)
    parser.add_argument("--retry-wait", type=float, default=5.0)
    args = parser.parse_args()

    store_code = args.store.strip().lower()
    if not store_code:
        raise SystemExit("store is required")
    if args.limit < 0 or args.cycle_wait < 1 or args.batch_size < 1:
        raise SystemExit("limit must be >= 0, cycle-wait must be >= 1, and batch-size must be >= 1")

    # A continuous run must never keep a many-thousand-row price snapshot in
    # memory.  ``limit=0`` still means that every pending target is eventually
    # processed, but each cycle refreshes only this oldest batch from the DB.
    batch_limit = min(args.limit, args.batch_size) if args.limit > 0 else args.batch_size

    cycle = 0
    while run_is_enabled(args.run_id):
        cycle += 1
        command = [
            sys.executable,
            "-u",
            str(PATCH_SCRIPT),
            "--execute",
            "--store",
            store_code,
            "--limit",
            str(batch_limit),
            "--max-change-rate",
            str(args.max_change_rate),
            "--api-interval",
            str(args.api_interval),
            "--retry-count",
            str(args.retry_count),
            "--retry-wait",
            str(args.retry_wait),
            "--retry-policy",
            "--pending-queue",
        ]
        if args.allow_large_change:
            command.append("--allow-large-change")
            command.append("--retry-large-change-holds")
        if args.verify:
            command.append("--verify")
        print(
            f"[continuous-price] cycle={cycle} start store={store_code} "
            f"batch_limit={batch_limit} requested_limit={args.limit}",
            flush=True,
        )
        result = subprocess.run(command, cwd=SCRIPT_DIR.parent, check=False)
        print(f"[continuous-price] cycle={cycle} finished exit_code={result.returncode}", flush=True)
        if not wait_until_next_cycle(args.run_id, args.cycle_wait):
            break
        print(f"[continuous-price] cycle={cycle} wait_complete seconds={args.cycle_wait}", flush=True)

    print("[continuous-price] stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
