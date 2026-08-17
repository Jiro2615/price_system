import argparse
import builtins
import os
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from db_config import connect_db


SIMULATOR_LOCK_NAMESPACE = 920601


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


@dataclass
class SimRunMetrics:
    backlog_start_count: int
    oldest_pending_seconds_start: float | None
    new_pending_count: int = 0
    retargeted_count: int = 0
    processed_count: int = 0
    backlog_end_count: int = 0
    oldest_pending_seconds_end: float | None = None
    elapsed_seconds: float = 0.0
    average_seconds_per_item: float = 0.0
    throughput_per_hour: float = 0.0
    estimated_drain_seconds: float | None = None


@dataclass
class MeasurementInfo:
    measurement_id: int
    measurement_label: str
    status: str
    started_at: str
    finished_at: str | None
    baseline_product_count: int


def now_text() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def log_next_action(action: str, reason: str, seconds: float | None = None) -> None:
    if seconds is None:
        print(f"next_action={action} reason={reason}")
    else:
        print(f"next_action={action} seconds={seconds} reason={reason}")


def resolve_hostname() -> str:
    value = socket.gethostname().strip()
    return value or "unknown-host"


def resolve_node_code(explicit_node_code: str | None = None) -> str:
    env_value = str(
        os.environ.get("PRICE_SYSTEM_NODE_CODE")
        or os.environ.get("WEB_ORCHESTRATOR_NODE_CODE")
        or ""
    ).strip()
    if env_value:
        return env_value
    explicit = str(explicit_node_code or "").strip()
    if explicit:
        return explicit
    return ""


def fetch_store_info(conn, store_code: str) -> dict[str, Any]:
    sql = """
        SELECT id, store_code, mall, store_name
        FROM stores
        WHERE store_code = %s
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (store_code,))
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"store not found: {store_code}")
    if row[2] != "rakuten":
        raise RuntimeError(f"store is not rakuten: {store_code}")
    return {
        "id": int(row[0]),
        "store_code": row[1],
        "mall": row[2],
        "store_name": row[3],
    }


def acquire_store_lock(conn, store_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s, %s)", (SIMULATOR_LOCK_NAMESPACE, store_id))
        row = cur.fetchone()
    return bool(row and row[0])


def release_store_lock(conn, store_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s, %s)", (SIMULATOR_LOCK_NAMESPACE, store_id))


def insert_run_start(
    conn,
    *,
    store_id: int,
    measurement_id: int | None,
    backlog_start_count: int,
    oldest_pending_seconds_start: float | None,
    api_interval_seconds: float,
    simulated_request_seconds: float,
) -> int:
    sql = """
        INSERT INTO price_update_sim_runs (
            store_id,
            measurement_id,
            started_at,
            backlog_start_count,
            oldest_pending_seconds_start,
            api_interval_seconds,
            simulated_request_seconds,
            result_status
        )
        VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, 'running')
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                store_id,
                measurement_id,
                backlog_start_count,
                Decimal(str(oldest_pending_seconds_start)) if oldest_pending_seconds_start is not None else None,
                Decimal(str(api_interval_seconds)),
                Decimal(str(simulated_request_seconds)),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return int(row[0])


def finish_run(
    conn,
    *,
    run_id: int,
    metrics: SimRunMetrics,
    result_status: str,
    result_message: str | None,
) -> None:
    sql = """
        UPDATE price_update_sim_runs
        SET
            finished_at = CURRENT_TIMESTAMP,
            backlog_end_count = %s,
            new_pending_count = %s,
            retargeted_count = %s,
            processed_count = %s,
            oldest_pending_seconds_end = %s,
            elapsed_seconds = %s,
            average_seconds_per_item = %s,
            throughput_per_hour = %s,
            estimated_drain_seconds = %s,
            result_status = %s,
            result_message = %s
        WHERE id = %s
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                metrics.backlog_end_count,
                metrics.new_pending_count,
                metrics.retargeted_count,
                metrics.processed_count,
                Decimal(str(metrics.oldest_pending_seconds_end)) if metrics.oldest_pending_seconds_end is not None else None,
                Decimal(str(metrics.elapsed_seconds)),
                Decimal(str(metrics.average_seconds_per_item)),
                Decimal(str(metrics.throughput_per_hour)),
                Decimal(str(metrics.estimated_drain_seconds)) if metrics.estimated_drain_seconds is not None else None,
                result_status,
                result_message,
                run_id,
            ),
        )
    conn.commit()


def fetch_backlog_stats(conn, store_id: int) -> tuple[int, float | None]:
    sql = """
        SELECT
            COUNT(*)::int AS backlog_count,
            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MIN(first_pending_at)))::double precision AS oldest_pending_seconds
        FROM price_update_sim_state
        WHERE store_id = %s
          AND pending_target_price IS NOT NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql, (store_id,))
        row = cur.fetchone()
    return int(row[0] or 0), (float(row[1]) if row[1] is not None else None)


def fetch_running_measurement(conn, store_id: int) -> MeasurementInfo | None:
    sql = """
        SELECT id, measurement_label, status, started_at, finished_at, baseline_product_count
        FROM price_update_sim_measurements
        WHERE store_id = %s
          AND status = 'running'
        ORDER BY started_at DESC, id DESC
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (store_id,))
        row = cur.fetchone()
    if not row:
        return None
    return MeasurementInfo(
        measurement_id=int(row[0]),
        measurement_label=row[1],
        status=row[2],
        started_at=row[3].isoformat(),
        finished_at=row[4].isoformat() if row[4] is not None else None,
        baseline_product_count=int(row[5] or 0),
    )


def update_running_measurement_status(
    conn,
    *,
    store_id: int,
    new_status: str,
) -> MeasurementInfo | None:
    if new_status not in {"finished", "cancelled"}:
        raise RuntimeError(f"unsupported measurement status: {new_status}")
    sql = """
        UPDATE price_update_sim_measurements
        SET
            status = %s,
            finished_at = CURRENT_TIMESTAMP
        WHERE id = (
            SELECT id
            FROM price_update_sim_measurements
            WHERE store_id = %s
              AND status = 'running'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        )
        RETURNING id, measurement_label, status, started_at, finished_at, baseline_product_count
    """
    with conn.cursor() as cur:
        cur.execute(sql, (new_status, store_id))
        row = cur.fetchone()
    conn.commit()
    if not row:
        return None
    return MeasurementInfo(
        measurement_id=int(row[0]),
        measurement_label=row[1],
        status=row[2],
        started_at=row[3].isoformat(),
        finished_at=row[4].isoformat() if row[4] is not None else None,
        baseline_product_count=int(row[5] or 0),
    )


def start_measurement_baseline(
    conn,
    *,
    store_id: int,
    store_code: str,
    measurement_label: str,
) -> MeasurementInfo:
    baseline_sql = """
        WITH baseline_rows AS (
            SELECT
                sp.id AS store_product_id,
                sp.store_id,
                COALESCE(sp.target_price, sp.current_price) AS baseline_price
            FROM store_products sp
            JOIN stores s ON s.id = sp.store_id
            WHERE s.id = %s
              AND s.store_code = %s
              AND s.mall = 'rakuten'
        )
        INSERT INTO price_update_sim_state (
            store_product_id,
            store_id,
            simulated_current_price,
            pending_target_price,
            first_pending_at,
            last_target_changed_at,
            last_simulated_update_at,
            retarget_count,
            created_at,
            updated_at
        )
        SELECT
            store_product_id,
            store_id,
            baseline_price,
            NULL,
            NULL,
            NULL,
            NULL,
            0,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM baseline_rows
        ON CONFLICT (store_product_id) DO UPDATE
        SET
            simulated_current_price = EXCLUDED.simulated_current_price,
            pending_target_price = NULL,
            first_pending_at = NULL,
            last_target_changed_at = NULL,
            last_simulated_update_at = NULL,
            retarget_count = 0,
            updated_at = CURRENT_TIMESTAMP
        RETURNING store_product_id
    """
    cancel_sql = """
        UPDATE price_update_sim_measurements
        SET
            status = 'cancelled',
            finished_at = CURRENT_TIMESTAMP,
            note = COALESCE(note, '') || CASE WHEN COALESCE(note, '') = '' THEN '' ELSE E'\n' END || %s
        WHERE store_id = %s
          AND status = 'running'
    """
    insert_sql = """
        INSERT INTO price_update_sim_measurements (
            store_id,
            measurement_label,
            started_at,
            status,
            baseline_product_count,
            note,
            created_at
        )
        VALUES (%s, %s, CURRENT_TIMESTAMP, 'running', %s, %s, CURRENT_TIMESTAMP)
        RETURNING id, measurement_label, status, started_at, baseline_product_count
    """
    with conn.cursor() as cur:
        cur.execute(
            cancel_sql,
            (
                f"Cancelled by new measurement start: {measurement_label}",
                store_id,
            ),
        )
        cur.execute(baseline_sql, (store_id, store_code))
        baseline_count = len(cur.fetchall())
        cur.execute(
            insert_sql,
            (
                store_id,
                measurement_label,
                baseline_count,
                "Baseline reset: simulated_current_price aligned to current target_price/current_price",
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return MeasurementInfo(
        measurement_id=int(row[0]),
        measurement_label=row[1],
        status=row[2],
        started_at=row[3].isoformat(),
        finished_at=None,
        baseline_product_count=int(row[4] or 0),
    )


def sync_simulation_state(conn, store_id: int, store_code: str) -> tuple[int, int]:
    candidate_sql = """
        SELECT
            sp.id AS store_product_id,
            sp.store_id,
            sp.current_price,
            sp.target_price,
            st.simulated_current_price,
            st.pending_target_price
        FROM store_products sp
        JOIN stores s ON s.id = sp.store_id
        LEFT JOIN price_update_sim_state st ON st.store_product_id = sp.id
        WHERE s.id = %s
          AND s.store_code = %s
          AND s.mall = 'rakuten'
          AND sp.enabled = TRUE
          AND COALESCE(sp.no_price_change, FALSE) = FALSE
          AND sp.target_price IS NOT NULL
          AND sp.mall_item_code IS NOT NULL
          AND sp.mall_item_code <> ''
        ORDER BY sp.id
    """
    pending_state_sql = """
        SELECT
            st.store_product_id,
            sp.current_price,
            sp.target_price,
            st.simulated_current_price,
            st.pending_target_price
        FROM price_update_sim_state st
        JOIN store_products sp ON sp.id = st.store_product_id
        JOIN stores s ON s.id = st.store_id
        WHERE st.store_id = %s
          AND s.store_code = %s
          AND st.pending_target_price IS NOT NULL
        ORDER BY st.store_product_id
    """

    new_pending_count = 0
    retargeted_count = 0
    now_sql = "CURRENT_TIMESTAMP"

    with conn.cursor() as cur:
        cur.execute(candidate_sql, (store_id, store_code))
        rows = cur.fetchall()

        for row in rows:
            store_product_id = int(row[0])
            current_price = row[2]
            target_price = row[3]
            simulated_current_price = row[4] if row[4] is not None else current_price
            pending_target_price = row[5]
            desired_pending_price = target_price if target_price != simulated_current_price else None
            pending_timestamp = datetime.now().astimezone() if desired_pending_price is not None else None

            if row[4] is None:
                cur.execute(
                    """
                    INSERT INTO price_update_sim_state (
                        store_product_id,
                        store_id,
                        simulated_current_price,
                        pending_target_price,
                        first_pending_at,
                        last_target_changed_at,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        store_product_id,
                        store_id,
                        simulated_current_price,
                        desired_pending_price,
                        pending_timestamp,
                        pending_timestamp,
                    ),
                )
                if desired_pending_price is not None:
                    new_pending_count += 1
                continue

            if desired_pending_price is None:
                if pending_target_price is not None:
                    cur.execute(
                        f"""
                        UPDATE price_update_sim_state
                        SET
                            pending_target_price = NULL,
                            first_pending_at = NULL,
                            last_target_changed_at = NULL,
                            updated_at = {now_sql}
                        WHERE store_product_id = %s
                        """,
                        (store_product_id,),
                    )
                continue

            if pending_target_price is None:
                cur.execute(
                    f"""
                    UPDATE price_update_sim_state
                    SET
                        pending_target_price = %s,
                        first_pending_at = {now_sql},
                        last_target_changed_at = {now_sql},
                        updated_at = {now_sql}
                    WHERE store_product_id = %s
                    """,
                    (desired_pending_price, store_product_id),
                )
                new_pending_count += 1
                continue

            if pending_target_price != desired_pending_price:
                cur.execute(
                    f"""
                    UPDATE price_update_sim_state
                    SET
                        pending_target_price = %s,
                        last_target_changed_at = {now_sql},
                        retarget_count = retarget_count + 1,
                        updated_at = {now_sql}
                    WHERE store_product_id = %s
                    """,
                    (desired_pending_price, store_product_id),
                )
                retargeted_count += 1

        cur.execute(pending_state_sql, (store_id, store_code))
        pending_rows = cur.fetchall()
        for row in pending_rows:
            store_product_id = int(row[0])
            current_price = row[1]
            target_price = row[2]
            simulated_current_price = row[3] if row[3] is not None else current_price
            desired_pending_price = target_price if target_price is not None and target_price != simulated_current_price else None
            if desired_pending_price is None:
                cur.execute(
                    f"""
                    UPDATE price_update_sim_state
                    SET
                        pending_target_price = NULL,
                        first_pending_at = NULL,
                        last_target_changed_at = NULL,
                        updated_at = {now_sql}
                    WHERE store_product_id = %s
                    """,
                    (store_product_id,),
                )

    conn.commit()
    return new_pending_count, retargeted_count


def fetch_pending_targets(conn, store_id: int, limit: int) -> list[dict[str, Any]]:
    sql = """
        SELECT
            st.store_product_id,
            st.store_id,
            s.store_code,
            sp.asin,
            sp.mall_item_code,
            COALESCE(NULLIF(sp.sku_code, ''), sp.mall_item_code) AS sku_code,
            sp.item_name,
            st.simulated_current_price,
            st.pending_target_price,
            st.first_pending_at,
            st.last_target_changed_at,
            st.retarget_count
        FROM price_update_sim_state st
        JOIN store_products sp ON sp.id = st.store_product_id
        JOIN stores s ON s.id = st.store_id
        WHERE st.store_id = %s
          AND st.pending_target_price IS NOT NULL
        ORDER BY st.first_pending_at ASC NULLS FIRST, st.store_product_id ASC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (store_id, limit))
        rows = cur.fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "store_product_id": int(row[0]),
                "store_id": int(row[1]),
                "store_code": row[2],
                "asin": row[3],
                "mall_item_code": row[4],
                "sku_code": row[5],
                "item_name": row[6],
                "simulated_current_price": row[7],
                "pending_target_price": row[8],
                "first_pending_at": row[9],
                "last_target_changed_at": row[10],
                "retarget_count": int(row[11] or 0),
            }
        )
    return results


def apply_simulated_update(conn, store_product_id: int, price_to_set: int) -> None:
    sql = """
        UPDATE price_update_sim_state
        SET
            simulated_current_price = %s,
            pending_target_price = NULL,
            first_pending_at = NULL,
            last_simulated_update_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE store_product_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (price_to_set, store_product_id))
    conn.commit()


def print_resolved_config(args, store_info: dict[str, Any], worker_id: str) -> None:
    hostname = resolve_hostname()
    node_code = resolve_node_code(args.node_code)
    print("")
    print("===== Rakuten Price Update Simulator =====")
    print(f"worker_id                  : {worker_id}")
    print(f"hostname                   : {hostname}")
    print(f"node_code                  : {node_code or '<hostname fallback>'}")
    print(f"store_code                 : {store_info['store_code']}")
    print(f"store_id                   : {store_info['id']}")
    print(f"limit                      : {args.limit}")
    print(f"empty_sleep_seconds        : {args.empty_sleep}")
    print(f"api_interval_seconds       : {args.api_interval}")
    print(f"simulated_request_seconds  : {args.simulated_request_seconds}")
    print(f"start_measurement          : {args.start_measurement}")
    print(f"finish_measurement         : {args.finish_measurement}")
    print(f"cancel_measurement         : {args.cancel_measurement}")
    print(f"measurement_label          : {args.measurement_label or ''}")
    print(f"once                       : {args.once}")
    print(f"max_loops                  : {args.max_loops}")
    print(f"fast_test                  : {args.fast_test}")
    print(f"resolve_only               : {args.resolve_only}")
    print("")


def compute_worker_id(store_code: str) -> str:
    return f"{resolve_hostname()}-{store_code}-price-sim"


def sleep_if_needed(seconds: float, *, fast_test: bool, action: str, reason: str) -> None:
    if seconds <= 0:
        return
    if fast_test:
        log_next_action("skip_sleep", f"{reason}_fast_test", seconds)
        return
    log_next_action(action, reason, seconds)
    time.sleep(seconds)


def process_pending_rows(
    conn,
    rows: list[dict[str, Any]],
    *,
    api_interval_seconds: float,
    simulated_request_seconds: float,
    fast_test: bool,
) -> int:
    processed_count = 0
    for index, row in enumerate(rows, start=1):
        asin = row.get("asin") or ""
        manage_number = row.get("mall_item_code") or ""
        from_price = row.get("simulated_current_price")
        to_price = row.get("pending_target_price")
        item_started = time.monotonic()

        print(
            f"SIMULATED_PATCH {index}/{len(rows)} "
            f"store_product_id={row['store_product_id']} "
            f"asin={asin} "
            f"manageNumber={manage_number} "
            f"price={from_price}->{to_price}"
        )

        sleep_if_needed(
            simulated_request_seconds,
            fast_test=fast_test,
            action="sleep_request",
            reason="simulated_patch",
        )
        apply_simulated_update(conn, row["store_product_id"], int(to_price))
        processed_count += 1

        elapsed = time.monotonic() - item_started
        print(
            f"sim_result asin={asin} manageNumber={manage_number} "
            f"elapsed={elapsed:.3f}s result=success simulated_price={to_price}"
        )

        if index < len(rows):
            sleep_if_needed(
                api_interval_seconds,
                fast_test=fast_test,
                action="sleep_rate_limit",
                reason="api_interval",
            )

    return processed_count


def print_measurement_info(measurement: MeasurementInfo | None) -> None:
    print("")
    print("===== Measurement =====")
    if measurement is None:
        print("measurement_id            : <none>")
        print("measurement_label         : <none>")
        print("measurement_status        : <none>")
        print("measurement_started_at    : <none>")
        print("measurement_finished_at   : <none>")
        print("baseline_product_count    : <none>")
        return
    print(f"measurement_id            : {measurement.measurement_id}")
    print(f"measurement_label         : {measurement.measurement_label}")
    print(f"measurement_status        : {measurement.status}")
    print(f"measurement_started_at    : {measurement.started_at}")
    print(f"measurement_finished_at   : {measurement.finished_at}")
    print(f"baseline_product_count    : {measurement.baseline_product_count}")


def print_loop_summary(loop_index: int, metrics: SimRunMetrics) -> None:
    queue_delta = metrics.backlog_end_count - metrics.backlog_start_count
    oldest_pending = metrics.oldest_pending_seconds_end
    print("")
    print("===== LOOP SUMMARY =====")
    print(f"loop                     : {loop_index}")
    print(f"backlog_start_count      : {metrics.backlog_start_count}")
    print(f"new_pending_count        : {metrics.new_pending_count}")
    print(f"retargeted_count         : {metrics.retargeted_count}")
    print(f"processed_count          : {metrics.processed_count}")
    print(f"backlog_end_count        : {metrics.backlog_end_count}")
    print(f"queue_delta              : {queue_delta}")
    print(f"oldest_pending_seconds   : {oldest_pending}")
    print(f"elapsed_seconds          : {metrics.elapsed_seconds:.3f}")
    print(f"average_seconds_per_item : {metrics.average_seconds_per_item:.3f}")
    print(f"throughput_per_hour      : {metrics.throughput_per_hour:.3f}")
    print(f"estimated_drain_seconds  : {metrics.estimated_drain_seconds}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Shadow simulator for Rakuten price update throughput. Uses isolated simulation tables only."
    )
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--node-code", default="", help="local node code for launcher logging")
    parser.add_argument("--limit", type=int, default=20, help="max simulated updates per loop")
    parser.add_argument("--start-measurement", action="store_true", help="reset simulation baseline and start a formal measurement window")
    parser.add_argument("--finish-measurement", action="store_true", help="mark the running measurement as finished and exit")
    parser.add_argument("--cancel-measurement", action="store_true", help="mark the running measurement as cancelled and exit")
    parser.add_argument("--measurement-label", default="", help="label for --start-measurement")
    parser.add_argument("--once", action="store_true", help="run one loop only")
    parser.add_argument("--max-loops", type=int, default=0, help="max loop count. 0 means unlimited")
    parser.add_argument("--empty-sleep", type=float, default=10.0, help="sleep seconds when backlog is empty")
    parser.add_argument("--api-interval", type=float, default=1.5, help="simulated interval between PATCH requests")
    parser.add_argument("--simulated-request-seconds", type=float, default=0.2, help="simulated PATCH request time")
    parser.add_argument("--resolve-only", action="store_true", help="print resolved settings and exit")
    parser.add_argument("--fast-test", action="store_true", help="skip request and interval sleeps")
    args = parser.parse_args()

    if args.limit <= 0:
        raise RuntimeError("--limit must be 1 or greater")
    if args.max_loops < 0:
        raise RuntimeError("--max-loops must be 0 or greater")
    if args.empty_sleep < 0:
        raise RuntimeError("--empty-sleep must be 0 or greater")
    if args.api_interval < 0:
        raise RuntimeError("--api-interval must be 0 or greater")
    if args.simulated_request_seconds < 0:
        raise RuntimeError("--simulated-request-seconds must be 0 or greater")
    control_flags = sum(
        1
        for value in (
            args.start_measurement,
            args.finish_measurement,
            args.cancel_measurement,
        )
        if value
    )
    if control_flags > 1:
        raise RuntimeError("Use only one of --start-measurement / --finish-measurement / --cancel-measurement")
    if args.start_measurement and not args.measurement_label.strip():
        raise RuntimeError("--measurement-label is required with --start-measurement")

    worker_id = compute_worker_id(args.store)

    with connect_db() as conn:
        store_info = fetch_store_info(conn, args.store)

    print_resolved_config(args, store_info, worker_id)

    if args.resolve_only:
        log_next_action("exit", "resolve_only")
        print("resolve_only is set. No simulation run was started.")
        return 0

    lock_conn = connect_db()
    lock_acquired = False
    try:
        lock_acquired = acquire_store_lock(lock_conn, store_info["id"])
        if not lock_acquired:
            print(
                f"simulator lock is already held for store_code={store_info['store_code']} "
                f"store_id={store_info['id']}"
            )
            return 2

        if args.start_measurement:
            with connect_db() as conn:
                measurement = start_measurement_baseline(
                    conn,
                    store_id=store_info["id"],
                    store_code=store_info["store_code"],
                    measurement_label=args.measurement_label.strip(),
                )
                backlog_count, oldest_pending_seconds = fetch_backlog_stats(conn, store_info["id"])
            print_measurement_info(measurement)
            print("")
            print("===== Measurement Baseline Result =====")
            print(f"backlog_count             : {backlog_count}")
            print(f"pending_target_count      : {backlog_count}")
            print(f"oldest_pending_seconds    : {oldest_pending_seconds}")
            print("store_products_updated    : False")
            print("rakuten_api_called        : False")
            log_next_action("exit", "start_measurement_completed")
            print("start_measurement completed. Exiting without simulation loop.")
            return 0

        if args.finish_measurement or args.cancel_measurement:
            target_status = "finished" if args.finish_measurement else "cancelled"
            with connect_db() as conn:
                measurement = update_running_measurement_status(
                    conn,
                    store_id=store_info["id"],
                    new_status=target_status,
                )
            print_measurement_info(measurement)
            if measurement is None:
                print("")
                print("No running measurement was found.")
                log_next_action("exit", f"{target_status}_measurement_not_found")
                return 0
            print("")
            print("===== Measurement Status Updated =====")
            print(f"new_status                : {target_status}")
            print("simulation_state_updated  : False")
            print("store_products_updated    : False")
            print("rakuten_api_called        : False")
            log_next_action("exit", f"{target_status}_measurement_completed")
            print(f"{target_status} measurement completed. Exiting without simulation loop.")
            return 0

        loop_index = 0
        while True:
            loop_index += 1
            loop_started_at = now_text()
            loop_started = time.monotonic()

            print("")
            print("############################################################")
            print(f"LOOP {loop_index} BEGIN")
            print(f"started_at : {loop_started_at}")
            print("############################################################")

            with connect_db() as conn:
                active_measurement = fetch_running_measurement(conn, store_info["id"])
                backlog_start_count, oldest_pending_start = fetch_backlog_stats(conn, store_info["id"])
                run_id = insert_run_start(
                    conn,
                    store_id=store_info["id"],
                    measurement_id=active_measurement.measurement_id if active_measurement else None,
                    backlog_start_count=backlog_start_count,
                    oldest_pending_seconds_start=oldest_pending_start,
                    api_interval_seconds=args.api_interval,
                    simulated_request_seconds=args.simulated_request_seconds,
                )
            print_measurement_info(active_measurement)

            metrics = SimRunMetrics(
                backlog_start_count=backlog_start_count,
                oldest_pending_seconds_start=oldest_pending_start,
            )

            try:
                with connect_db() as conn:
                    new_pending_count, retargeted_count = sync_simulation_state(
                        conn,
                        store_id=store_info["id"],
                        store_code=store_info["store_code"],
                    )
                metrics.new_pending_count = new_pending_count
                metrics.retargeted_count = retargeted_count

                with connect_db() as conn:
                    pending_rows = fetch_pending_targets(conn, store_info["id"], args.limit)

                if pending_rows:
                    with connect_db() as conn:
                        metrics.processed_count = process_pending_rows(
                            conn,
                            pending_rows,
                            api_interval_seconds=args.api_interval,
                            simulated_request_seconds=args.simulated_request_seconds,
                            fast_test=args.fast_test,
                        )

                with connect_db() as conn:
                    metrics.backlog_end_count, metrics.oldest_pending_seconds_end = fetch_backlog_stats(
                        conn,
                        store_info["id"],
                    )

                metrics.elapsed_seconds = time.monotonic() - loop_started
                if metrics.processed_count > 0:
                    metrics.average_seconds_per_item = metrics.elapsed_seconds / metrics.processed_count
                    metrics.throughput_per_hour = 3600.0 / metrics.average_seconds_per_item
                else:
                    metrics.average_seconds_per_item = 0.0
                    metrics.throughput_per_hour = 0.0
                metrics.estimated_drain_seconds = (
                    metrics.backlog_end_count * metrics.average_seconds_per_item
                    if metrics.backlog_end_count > 0 and metrics.average_seconds_per_item > 0
                    else 0.0
                )

                with connect_db() as conn:
                    finish_run(
                        conn,
                        run_id=run_id,
                        metrics=metrics,
                        result_status="success",
                        result_message=None,
                    )
            except Exception as exc:
                metrics.elapsed_seconds = time.monotonic() - loop_started
                with connect_db() as conn:
                    try:
                        metrics.backlog_end_count, metrics.oldest_pending_seconds_end = fetch_backlog_stats(
                            conn,
                            store_info["id"],
                        )
                    except Exception:
                        metrics.backlog_end_count = metrics.backlog_start_count
                        metrics.oldest_pending_seconds_end = metrics.oldest_pending_seconds_start
                    finish_run(
                        conn,
                        run_id=run_id,
                        metrics=metrics,
                        result_status="error",
                        result_message=str(exc)[:2000],
                    )
                raise

            print_loop_summary(loop_index, metrics)

            if args.once:
                log_next_action("exit", "once")
                print("once is set. Exiting after one loop.")
                return 0

            if args.max_loops and loop_index >= args.max_loops:
                log_next_action("exit", "max_loops_reached")
                print(f"--max-loops={args.max_loops} reached. Exiting.")
                return 0

            if metrics.backlog_end_count > 0 or metrics.processed_count >= args.limit:
                log_next_action(
                    "continue_immediately",
                    "targets_remaining" if metrics.backlog_end_count > 0 else "limit_reached",
                )
                print("Backlog remains or limit was reached. Starting next loop immediately.")
                continue

            log_next_action("sleep_empty", "no_backlog", args.empty_sleep)
            if not args.fast_test and args.empty_sleep > 0:
                print(f"No backlog detected. Sleeping {args.empty_sleep} seconds before next loop.")
                time.sleep(args.empty_sleep)
            else:
                print("No backlog detected. Empty sleep skipped.")
    finally:
        if lock_acquired:
            try:
                release_store_lock(lock_conn, store_info["id"])
            except Exception:
                pass
        lock_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
