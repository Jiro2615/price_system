"""Continuous store-2 Rakuten inventory API worker.

Each cycle reads rows where ``current_stock != target_stock`` and delegates
the non-empty difference to the existing inventories.bulk.upsert script. The
bulk endpoint accepts one row as well as 400 rows.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from db_config import connect_db


SCRIPT_DIR = Path(__file__).resolve().parent
UPSERT_SCRIPT = SCRIPT_DIR / "rakuten_inventory_bulk_upsert.py"
RECONCILE_SCRIPT = SCRIPT_DIR / "rakuten_inventory_reconcile.py"


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
    parser = argparse.ArgumentParser(description="Continuous Rakuten inventory API worker")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store", default="rakuten_2")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument("--cycle-wait", type=int, default=300)
    parser.add_argument("--reconcile-interval", type=int, default=3600)
    parser.add_argument("--reconcile-limit", type=int, default=200)
    args = parser.parse_args()

    if args.store.strip().lower() != "rakuten_2":
        raise SystemExit("continuous Rakuten inventory API worker is restricted to store=rakuten_2")
    if args.limit < 0:
        raise SystemExit("limit must be >= 0")
    if not 1 <= args.batch_size <= 400:
        raise SystemExit("batch-size must be between 1 and 400")
    if args.cycle_wait < 60:
        raise SystemExit("cycle-wait must be >= 60")
    if args.reconcile_interval < 0:
        raise SystemExit("reconcile-interval must be >= 0")
    if args.reconcile_interval and args.reconcile_interval < 300:
        raise SystemExit("reconcile-interval must be 0 or at least 300")
    if not 1 <= args.reconcile_limit <= 400:
        raise SystemExit("reconcile-limit must be between 1 and 400")

    cycle = 0
    last_reconciliation_at = 0.0
    while run_is_enabled(args.run_id):
        cycle += 1
        command = [
            sys.executable,
            "-u",
            str(UPSERT_SCRIPT),
            "--execute",
            "--store",
            "rakuten_2",
            "--limit",
            str(args.limit),
            "--batch-size",
            str(args.batch_size),
        ]
        print(
            f"[continuous-inventory] cycle={cycle} start "
            f"store=rakuten_2 limit={args.limit} batch_size={args.batch_size}",
            flush=True,
        )
        result = subprocess.run(command, cwd=SCRIPT_DIR.parent, check=False)
        print(
            f"[continuous-inventory] cycle={cycle} finished exit_code={result.returncode}",
            flush=True,
        )
        if args.reconcile_interval and time.monotonic() - last_reconciliation_at >= args.reconcile_interval:
            last_reconciliation_at = time.monotonic()
            reconcile_command = [
                sys.executable,
                "-u",
                str(RECONCILE_SCRIPT),
                "--execute",
                "--store",
                "rakuten_2",
                "--limit",
                str(args.reconcile_limit),
            ]
            print(
                f"[continuous-inventory] reconcile start limit={args.reconcile_limit}",
                flush=True,
            )
            reconcile_result = subprocess.run(reconcile_command, cwd=SCRIPT_DIR.parent, check=False)
            print(
                f"[continuous-inventory] reconcile finished exit_code={reconcile_result.returncode}",
                flush=True,
            )
        if not wait_until_next_cycle(args.run_id, args.cycle_wait):
            break
        print(
            f"[continuous-inventory] cycle={cycle} wait_complete seconds={args.cycle_wait}",
            flush=True,
        )

    print("[continuous-inventory] stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
