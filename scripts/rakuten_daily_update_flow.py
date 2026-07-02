import argparse
import locale
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(r"C:\price_system")
SCRIPTS_DIR = BASE_DIR / "scripts"
CONSOLE_ENCODING = locale.getpreferredencoding(False) or "cp932"


def script_path(name: str) -> Path:
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise RuntimeError(f"必要なスクリプトが見つかりません: {path}")
    return path


def py_cmd(script_name: str) -> list[str]:
    return [sys.executable, "-u", str(script_path(script_name))]


def run_live_step(step_no: int, total_steps: int, step_name: str, cmd: list[str]) -> tuple[int, float]:
    started = time.perf_counter()

    print("")
    print("============================================================")
    print(f"STEP {step_no}/{total_steps} 開始: {step_name}")
    print("コマンド:", " ".join(cmd))
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

    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")

    proc.wait()
    elapsed = time.perf_counter() - started
    returncode = int(proc.returncode or 0)

    print("")
    print("------------------------------------------------------------")
    print(f"STEP {step_no}/{total_steps} 終了: {step_name}")
    print(f"returncode: {returncode}")
    print(f"所要秒数  : {elapsed:.1f}s")
    print(f"結果      : {'SUCCESS' if returncode == 0 else 'FAILED'}")
    print("------------------------------------------------------------")

    return returncode, elapsed


def build_steps(args) -> list[tuple[str, list[str]]]:
    calc_cmd = [
        *py_cmd("calc_store_targets.py"),
        "--store",
        args.store,
    ]
    if not args.execute:
        calc_cmd.append("--dry-run")

    inventory_cmd = [
        *py_cmd("rakuten_inventory_bulk_upsert.py"),
        "--store",
        args.store,
        "--limit",
        str(args.stock_limit),
    ]
    if args.execute:
        inventory_cmd.append("--execute")

    price_cmd = [
        *py_cmd("rakuten_price_patch.py"),
        "--store",
        args.store,
        "--limit",
        str(args.price_limit),
    ]
    if args.execute:
        price_cmd.append("--execute")

    blocked_cmd = [
        *py_cmd("rakuten_price_patch.py"),
        "--store",
        args.store,
        "--blocked-only",
        "--limit",
        str(args.blocked_limit),
    ]
    if args.execute:
        blocked_cmd.append("--execute")

    show_cmd = [
        *py_cmd("show_update_targets.py"),
        "--mall",
        "rakuten",
        "--store",
        args.store,
        "--limit",
        str(args.show_limit),
    ]

    return [
        (
            "Amazon価格確認",
            [
                *py_cmd("price_check_from_db.py"),
                "--limit",
                str(args.amazon_limit),
                "--summary",
            ],
        ),
        ("target計算", calc_cmd),
        ("更新前確認", show_cmd.copy()),
        ("在庫API更新", inventory_cmd),
        ("価格API更新", price_cmd),
        ("blocked商品API fallback", blocked_cmd),
        ("最終確認", show_cmd.copy()),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="楽天の日常運用フローを順番実行します。Amazon確認 → target計算 → 更新確認 → 在庫API → 価格API → blocked fallback → 最終確認"
    )
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--amazon-limit", type=int, default=20, help="price_check_from_db.py に渡す最大件数")
    parser.add_argument("--price-limit", type=int, default=10, help="rakuten_price_patch.py に渡す最大件数")
    parser.add_argument("--stock-limit", type=int, default=50, help="rakuten_inventory_bulk_upsert.py に渡す最大件数")
    parser.add_argument("--blocked-limit", type=int, default=10, help="rakuten_price_patch.py --blocked-only に渡す最大件数")
    parser.add_argument("--show-limit", type=int, default=50, help="show_update_targets.py に渡す表示件数")
    parser.add_argument("--execute", action="store_true", help="在庫API・価格API・blocked fallback を実更新する")
    args = parser.parse_args()

    for name in ("amazon_limit", "price_limit", "stock_limit", "blocked_limit", "show_limit"):
        if getattr(args, name) <= 0:
            raise RuntimeError(f"--{name.replace('_', '-')} は 1以上にしてください。")

    steps = build_steps(args)

    print("")
    print("===== 楽天日常更新フロー開始 =====")
    print(f"mode          : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"store         : {args.store}")
    print(f"amazon_limit  : {args.amazon_limit}")
    print(f"stock_limit   : {args.stock_limit}")
    print(f"price_limit   : {args.price_limit}")
    print(f"blocked_limit : {args.blocked_limit}")
    print(f"show_limit    : {args.show_limit}")
    print(f"encoding      : {CONSOLE_ENCODING}")
    print("")

    summary: list[tuple[str, int, float]] = []

    for index, (step_name, cmd) in enumerate(steps, start=1):
        returncode, elapsed = run_live_step(index, len(steps), step_name, cmd)
        summary.append((step_name, returncode, elapsed))

        if returncode != 0:
            print("")
            print("===== 楽天日常更新フロー中断 =====")
            print(f"失敗ステップ: {step_name}")
            print(f"returncode  : {returncode}")
            print("")
            print("===== サマリー =====")
            for name, code, sec in summary:
                print(f"{name}: returncode={code}, elapsed={sec:.1f}s")
            return returncode

    print("")
    print("===== 楽天日常更新フロー完了 =====")
    print("===== サマリー =====")
    for step_name, returncode, elapsed in summary:
        print(f"{step_name}: returncode={returncode}, elapsed={elapsed:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
