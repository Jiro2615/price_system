import argparse
import builtins
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from db_config import connect_db


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
class PeriodWindow:
    label: str
    started_at: datetime


@dataclass
class MeasurementSelection:
    measurement_id: int
    measurement_label: str
    status: str
    started_at: str
    finished_at: str | None
    baseline_product_count: int
    source: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only report for Rakuten price update shadow simulation."
    )
    parser.add_argument("--store", default="rakuten_1", help="stores.store_code")
    parser.add_argument("--hours", type=int, default=0, help="report window in hours")
    parser.add_argument("--days", type=int, default=0, help="report window in days")
    parser.add_argument("--measurement-label", default="", help="filter by measurement label")
    parser.add_argument("--measurement-id", type=int, default=0, help="filter by measurement id")
    parser.add_argument("--json", action="store_true", help="print report as JSON")
    parser.add_argument("--csv-output", default="", help="write flat report rows to CSV")
    parser.add_argument("--recent-runs", type=int, default=20, help="number of recent runs to include")
    args = parser.parse_args()

    if args.hours and args.days:
        raise RuntimeError("Use either --hours or --days, not both")
    if args.measurement_id and args.measurement_label.strip():
        raise RuntimeError("Use either --measurement-id or --measurement-label, not both")
    if args.hours < 0:
        raise RuntimeError("--hours must be 0 or greater")
    if args.days < 0:
        raise RuntimeError("--days must be 0 or greater")
    if args.measurement_id < 0:
        raise RuntimeError("--measurement-id must be 0 or greater")
    if args.recent_runs <= 0:
        raise RuntimeError("--recent-runs must be 1 or greater")
    return args


def determine_window(args: argparse.Namespace) -> PeriodWindow:
    now = datetime.now().astimezone()
    if args.hours:
        return PeriodWindow(label=f"last_{args.hours}_hours", started_at=now - timedelta(hours=args.hours))
    if args.days:
        return PeriodWindow(label=f"last_{args.days}_days", started_at=now - timedelta(days=args.days))
    return PeriodWindow(label="last_24_hours", started_at=now - timedelta(hours=24))


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
        "store_id": int(row[0]),
        "store_code": row[1],
        "mall": row[2],
        "store_name": row[3],
    }


def resolve_measurement_selection(
    conn,
    *,
    store_id: int,
    measurement_id: int | None,
    measurement_label: str | None,
) -> MeasurementSelection | None:
    base_sql = """
        SELECT id, measurement_label, status, started_at, finished_at, baseline_product_count
        FROM price_update_sim_measurements
        WHERE store_id = %s
    """
    params: list[Any] = [store_id]

    if measurement_id:
        sql = base_sql + " AND id = %s ORDER BY started_at DESC, id DESC LIMIT 1"
        params.append(measurement_id)
        source = "measurement_id"
    elif measurement_label:
        sql = base_sql + " AND measurement_label = %s ORDER BY started_at DESC, id DESC LIMIT 1"
        params.append(measurement_label)
        source = "measurement_label"
    else:
        sql = base_sql + " AND status = 'running' ORDER BY started_at DESC, id DESC LIMIT 1"
        source = "auto_running"

    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()

    if not row:
        if measurement_id or measurement_label:
            raise RuntimeError("measurement not found for selected store")
        return None

    return MeasurementSelection(
        measurement_id=int(row[0]),
        measurement_label=row[1],
        status=row[2],
        started_at=row[3].isoformat(),
        finished_at=row[4].isoformat() if row[4] is not None else None,
        baseline_product_count=int(row[5] or 0),
        source=source,
    )


def fetch_current_state(conn, store_id: int) -> dict[str, Any]:
    sql = """
        WITH state_rows AS (
            SELECT
                st.pending_target_price,
                st.first_pending_at,
                st.simulated_current_price,
                st.retarget_count,
                st.last_simulated_update_at,
                sp.target_price
            FROM price_update_sim_state st
            JOIN store_products sp ON sp.id = st.store_product_id
            WHERE st.store_id = %s
        )
        SELECT
            COUNT(*) FILTER (WHERE pending_target_price IS NOT NULL)::int AS backlog_count,
            MIN(first_pending_at) FILTER (WHERE pending_target_price IS NOT NULL) AS oldest_pending_at,
            EXTRACT(
                EPOCH FROM (
                    CURRENT_TIMESTAMP - MIN(first_pending_at) FILTER (WHERE pending_target_price IS NOT NULL)
                )
            )::double precision AS oldest_pending_seconds,
            COUNT(*) FILTER (
                WHERE target_price IS NOT NULL
                  AND simulated_current_price IS NOT NULL
                  AND target_price <> simulated_current_price
            )::int AS simulated_vs_target_diff_count,
            COUNT(*) FILTER (WHERE pending_target_price IS NOT NULL)::int AS pending_target_count,
            COUNT(*) FILTER (WHERE COALESCE(retarget_count, 0) >= 1)::int AS retargeted_product_count,
            COALESCE(SUM(retarget_count), 0)::int AS retarget_count_total,
            MAX(last_simulated_update_at) AS last_simulated_update_at
        FROM state_rows
    """
    with conn.cursor() as cur:
        cur.execute(sql, (store_id,))
        row = cur.fetchone()

    oldest_seconds = float(row[2]) if row[2] is not None else None
    return {
        "backlog_count": int(row[0] or 0),
        "oldest_pending_at": row[1].isoformat() if row[1] is not None else None,
        "oldest_pending_seconds": oldest_seconds,
        "oldest_pending_minutes": (oldest_seconds / 60.0) if oldest_seconds is not None else None,
        "simulated_vs_target_diff_count": int(row[3] or 0),
        "pending_target_count": int(row[4] or 0),
        "retargeted_product_count": int(row[5] or 0),
        "retarget_count_total": int(row[6] or 0),
        "last_simulated_update_at": row[7].isoformat() if row[7] is not None else None,
    }


def fetch_period_summary(
    conn,
    store_id: int,
    started_at: datetime,
    measurement: MeasurementSelection | None,
) -> dict[str, Any]:
    if measurement is not None:
        sql = """
        SELECT
            COUNT(*)::int AS run_count,
            COALESCE(SUM(new_pending_count), 0)::int AS new_pending_count_total,
            COALESCE(SUM(retargeted_count), 0)::int AS retargeted_count_total,
            COALESCE(SUM(processed_count), 0)::int AS processed_count_total,
            MAX(GREATEST(backlog_start_count, COALESCE(backlog_end_count, 0)))::int AS backlog_max_count,
            (
                SELECT r2.backlog_end_count
                FROM price_update_sim_runs r2
                WHERE r2.measurement_id = %s
                ORDER BY r2.started_at DESC, r2.id DESC
                LIMIT 1
            )::int AS latest_backlog_end_count,
            GREATEST(
                COALESCE(MAX(oldest_pending_seconds_start), 0),
                COALESCE(MAX(oldest_pending_seconds_end), 0)
            )::double precision AS oldest_pending_seconds_max,
            AVG(elapsed_seconds)::double precision AS avg_elapsed_seconds,
            AVG(average_seconds_per_item)::double precision AS avg_seconds_per_item,
            AVG(throughput_per_hour)::double precision AS avg_throughput_per_hour,
            MIN(throughput_per_hour)::double precision AS min_throughput_per_hour,
            MAX(throughput_per_hour)::double precision AS max_throughput_per_hour,
            COUNT(*) FILTER (WHERE result_status <> 'success')::int AS error_run_count,
            MAX(finished_at) AS last_finished_at,
            MAX(estimated_drain_seconds) FILTER (
                WHERE started_at = (
                    SELECT MAX(r3.started_at)
                    FROM price_update_sim_runs r3
                    WHERE r3.measurement_id = %s
                )
            )::double precision AS latest_estimated_drain_seconds
        FROM price_update_sim_runs
        WHERE measurement_id = %s
        """
        params = (measurement.measurement_id, measurement.measurement_id, measurement.measurement_id)
    else:
        sql = """
        SELECT
            COUNT(*)::int AS run_count,
            COALESCE(SUM(new_pending_count), 0)::int AS new_pending_count_total,
            COALESCE(SUM(retargeted_count), 0)::int AS retargeted_count_total,
            COALESCE(SUM(processed_count), 0)::int AS processed_count_total,
            MAX(backlog_start_count)::int AS backlog_max_count,
            (
                SELECT r2.backlog_end_count
                FROM price_update_sim_runs r2
                WHERE r2.store_id = %s
                  AND r2.started_at >= %s
                ORDER BY r2.started_at DESC, r2.id DESC
                LIMIT 1
            )::int AS latest_backlog_end_count,
            GREATEST(
                COALESCE(MAX(oldest_pending_seconds_start), 0),
                COALESCE(MAX(oldest_pending_seconds_end), 0)
            )::double precision AS oldest_pending_seconds_max,
            AVG(elapsed_seconds)::double precision AS avg_elapsed_seconds,
            AVG(average_seconds_per_item)::double precision AS avg_seconds_per_item,
            AVG(throughput_per_hour)::double precision AS avg_throughput_per_hour,
            MIN(throughput_per_hour)::double precision AS min_throughput_per_hour,
            MAX(throughput_per_hour)::double precision AS max_throughput_per_hour,
            COUNT(*) FILTER (WHERE result_status <> 'success')::int AS error_run_count,
            MAX(finished_at) AS last_finished_at,
            MAX(estimated_drain_seconds) FILTER (
                WHERE started_at = (
                    SELECT MAX(r3.started_at)
                    FROM price_update_sim_runs r3
                    WHERE r3.store_id = %s
                      AND r3.started_at >= %s
                )
            )::double precision AS latest_estimated_drain_seconds
        FROM price_update_sim_runs
        WHERE store_id = %s
          AND started_at >= %s
    """
        params = (store_id, started_at, store_id, started_at, store_id, started_at)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()

    run_count = int(row[0] or 0)
    new_pending = int(row[1] or 0)
    retargeted = int(row[2] or 0)
    processed = int(row[3] or 0)

    # retargeted_count updates existing pending rows and does not add queue items,
    # so queue_delta should not include it.
    queue_delta = new_pending - processed

    return {
        "run_count": run_count,
        "new_pending_count_total": new_pending,
        "retargeted_count_total": retargeted,
        "processed_count_total": processed,
        "queue_delta": queue_delta,
        "queue_delta_note": "queue_delta = new_pending_count_total - processed_count_total; retargeted_count only updates existing pending rows",
        "backlog_max_count": int(row[4] or 0),
        "latest_backlog_end_count": int(row[5] or 0),
        "oldest_pending_seconds_max": float(row[6]) if row[6] is not None else None,
        "avg_elapsed_seconds": float(row[7]) if row[7] is not None else None,
        "avg_seconds_per_item": float(row[8]) if row[8] is not None else None,
        "avg_throughput_per_hour": float(row[9]) if row[9] is not None else None,
        "min_throughput_per_hour": float(row[10]) if row[10] is not None else None,
        "max_throughput_per_hour": float(row[11]) if row[11] is not None else None,
        "error_run_count": int(row[12] or 0),
        "last_finished_at": row[13].isoformat() if row[13] is not None else None,
        "latest_estimated_drain_seconds": float(row[14]) if row[14] is not None else None,
    }


def fetch_daily_summary(
    conn,
    store_id: int,
    started_at: datetime,
    measurement: MeasurementSelection | None,
) -> list[dict[str, Any]]:
    if measurement is not None:
        sql = """
        SELECT
            DATE(started_at) AS run_date,
            COALESCE(SUM(new_pending_count), 0)::int AS new_pending_count,
            COALESCE(SUM(retargeted_count), 0)::int AS retargeted_count,
            COALESCE(SUM(processed_count), 0)::int AS processed_count,
            COALESCE(MAX(GREATEST(backlog_start_count, COALESCE(backlog_end_count, 0))), 0)::int AS backlog_max_count,
            GREATEST(
                COALESCE(MAX(oldest_pending_seconds_start), 0),
                COALESCE(MAX(oldest_pending_seconds_end), 0)
            )::double precision AS oldest_pending_seconds_max,
            AVG(throughput_per_hour)::double precision AS avg_throughput_per_hour,
            COUNT(*) FILTER (WHERE result_status <> 'success')::int AS error_run_count
        FROM price_update_sim_runs
        WHERE measurement_id = %s
        GROUP BY DATE(started_at)
        ORDER BY run_date ASC
        """
        params = (measurement.measurement_id,)
    else:
        sql = """
        SELECT
            DATE(started_at) AS run_date,
            COALESCE(SUM(new_pending_count), 0)::int AS new_pending_count,
            COALESCE(SUM(retargeted_count), 0)::int AS retargeted_count,
            COALESCE(SUM(processed_count), 0)::int AS processed_count,
            COALESCE(MAX(GREATEST(backlog_start_count, COALESCE(backlog_end_count, 0))), 0)::int AS backlog_max_count,
            GREATEST(
                COALESCE(MAX(oldest_pending_seconds_start), 0),
                COALESCE(MAX(oldest_pending_seconds_end), 0)
            )::double precision AS oldest_pending_seconds_max,
            AVG(throughput_per_hour)::double precision AS avg_throughput_per_hour,
            COUNT(*) FILTER (WHERE result_status <> 'success')::int AS error_run_count
        FROM price_update_sim_runs
        WHERE store_id = %s
          AND started_at >= %s
        GROUP BY DATE(started_at)
        ORDER BY run_date ASC
    """
        params = (store_id, started_at)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        oldest_seconds = float(row[5]) if row[5] is not None else None
        results.append(
            {
                "date": row[0].isoformat(),
                "new_pending_count": int(row[1] or 0),
                "retargeted_count": int(row[2] or 0),
                "processed_count": int(row[3] or 0),
                "backlog_max_count": int(row[4] or 0),
                "oldest_pending_minutes_max": (oldest_seconds / 60.0) if oldest_seconds is not None else None,
                "avg_throughput_per_hour": float(row[6]) if row[6] is not None else None,
                "error_run_count": int(row[7] or 0),
            }
        )
    return results


def fetch_recent_runs(
    conn,
    store_id: int,
    limit: int,
    measurement: MeasurementSelection | None,
) -> list[dict[str, Any]]:
    if measurement is not None:
        sql = """
        SELECT
            started_at,
            backlog_start_count,
            new_pending_count,
            retargeted_count,
            processed_count,
            backlog_end_count,
            oldest_pending_seconds_end,
            elapsed_seconds,
            throughput_per_hour,
            estimated_drain_seconds,
            result_status
        FROM price_update_sim_runs
        WHERE measurement_id = %s
        ORDER BY started_at DESC, id DESC
        LIMIT %s
        """
        params = (measurement.measurement_id, limit)
    else:
        sql = """
        SELECT
            started_at,
            backlog_start_count,
            new_pending_count,
            retargeted_count,
            processed_count,
            backlog_end_count,
            oldest_pending_seconds_end,
            elapsed_seconds,
            throughput_per_hour,
            estimated_drain_seconds,
            result_status
        FROM price_update_sim_runs
        WHERE store_id = %s
        ORDER BY started_at DESC, id DESC
        LIMIT %s
    """
        params = (store_id, limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "started_at": row[0].isoformat() if row[0] is not None else None,
                "backlog_start_count": int(row[1] or 0),
                "new_pending_count": int(row[2] or 0),
                "retargeted_count": int(row[3] or 0),
                "processed_count": int(row[4] or 0),
                "backlog_end_count": int(row[5] or 0),
                "oldest_pending_seconds_end": float(row[6]) if row[6] is not None else None,
                "elapsed_seconds": float(row[7]) if row[7] is not None else None,
                "throughput_per_hour": float(row[8]) if row[8] is not None else None,
                "estimated_drain_seconds": float(row[9]) if row[9] is not None else None,
                "result_status": row[10],
            }
        )
    return results


def build_assessment(current_state: dict[str, Any], period_summary: dict[str, Any]) -> dict[str, Any]:
    processed = period_summary["processed_count_total"]
    incoming = period_summary["new_pending_count_total"]
    processed_vs_new_pending = "yes" if processed >= incoming else "no"

    queue_delta = period_summary["queue_delta"]
    if queue_delta < 0:
        backlog_trend = "decreasing"
    elif queue_delta > 0:
        backlog_trend = "increasing"
    else:
        backlog_trend = "flat"

    return {
        "processed_count_meets_new_pending": processed_vs_new_pending,
        "backlog_trend": backlog_trend,
        "latest_estimated_drain_seconds": period_summary["latest_estimated_drain_seconds"],
        "max_wait_seconds": period_summary["oldest_pending_seconds_max"],
        "current_max_wait_seconds": current_state["oldest_pending_seconds"],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    window = determine_window(args)
    with connect_db() as conn:
        store_info = fetch_store_info(conn, args.store)
        measurement = resolve_measurement_selection(
            conn,
            store_id=store_info["store_id"],
            measurement_id=args.measurement_id or None,
            measurement_label=args.measurement_label.strip() or None,
        )
        current_state = fetch_current_state(conn, store_info["store_id"])
        period_summary = fetch_period_summary(conn, store_info["store_id"], window.started_at, measurement)
        daily_summary = fetch_daily_summary(conn, store_info["store_id"], window.started_at, measurement)
        recent_runs = fetch_recent_runs(conn, store_info["store_id"], args.recent_runs, measurement)

    return {
        "store": store_info,
        "window": {
            "label": window.label,
            "started_at": window.started_at.isoformat(),
        },
        "measurement": (
            {
                "measurement_id": measurement.measurement_id,
                "measurement_label": measurement.measurement_label,
                "status": measurement.status,
                "started_at": measurement.started_at,
                "finished_at": measurement.finished_at,
                "baseline_product_count": measurement.baseline_product_count,
                "source": measurement.source,
            }
            if measurement is not None
            else None
        ),
        "current_state": current_state,
        "period_summary": period_summary,
        "daily_summary": daily_summary,
        "recent_runs": recent_runs,
        "assessment": build_assessment(current_state, period_summary),
        "safety_review": {
            "simulated_current_price_overwritten_from_current_price": False,
            "current_price_used_only_for_initial_state_or_null_fallback": True,
            "rakuten_api_calls_present": False,
            "store_products_update_present": False,
            "notes": [
                "simulated_current_price is written only in price_update_sim_state",
                "store_products.current_price is used when creating a missing simulation state row",
                "no requests or Rakuten API helper imports exist in the simulator",
                "the simulator does not execute UPDATE against store_products",
            ],
        },
    }


def print_text_report(report: dict[str, Any], recent_runs_limit: int) -> None:
    print("")
    print("===== Rakuten Price Simulation Report =====")
    print(f"store_code                 : {report['store']['store_code']}")
    print(f"store_id                   : {report['store']['store_id']}")
    print(f"window                     : {report['window']['label']}")
    print(f"window_started_at          : {report['window']['started_at']}")
    measurement = report["measurement"]
    if measurement is not None:
        print(f"measurement_id             : {measurement['measurement_id']}")
        print(f"measurement_label          : {measurement['measurement_label']}")
        print(f"measurement_status         : {measurement['status']}")
        print(f"measurement_started_at     : {measurement['started_at']}")
        print(f"measurement_finished_at    : {measurement['finished_at']}")
        print(f"measurement_source         : {measurement['source']}")
    else:
        print("measurement_id             : <none>")
        print("measurement_label          : <none>")
        print("measurement_status         : <none>")

    current = report["current_state"]
    print("")
    print("===== Current State =====")
    for key in (
        "backlog_count",
        "oldest_pending_at",
        "oldest_pending_seconds",
        "oldest_pending_minutes",
        "simulated_vs_target_diff_count",
        "pending_target_count",
        "retargeted_product_count",
        "retarget_count_total",
        "last_simulated_update_at",
    ):
        print(f"{key:29}: {current[key]}")

    period = report["period_summary"]
    print("")
    print("===== Period Summary =====")
    for key in (
        "run_count",
        "new_pending_count_total",
        "retargeted_count_total",
        "processed_count_total",
        "queue_delta",
        "backlog_max_count",
        "latest_backlog_end_count",
        "oldest_pending_seconds_max",
        "avg_elapsed_seconds",
        "avg_seconds_per_item",
        "avg_throughput_per_hour",
        "min_throughput_per_hour",
        "max_throughput_per_hour",
        "error_run_count",
        "last_finished_at",
        "latest_estimated_drain_seconds",
    ):
        print(f"{key:29}: {period[key]}")
    print(f"{'queue_delta_note':29}: {period['queue_delta_note']}")

    print("")
    print("===== Daily Summary =====")
    if not report["daily_summary"]:
        print("no runs in selected window")
    else:
        for row in report["daily_summary"]:
            print(
                " | ".join(
                    [
                        f"date={row['date']}",
                        f"new_pending_count={row['new_pending_count']}",
                        f"retargeted_count={row['retargeted_count']}",
                        f"processed_count={row['processed_count']}",
                        f"backlog_max_count={row['backlog_max_count']}",
                        f"oldest_pending_minutes_max={row['oldest_pending_minutes_max']}",
                        f"avg_throughput_per_hour={row['avg_throughput_per_hour']}",
                        f"error_run_count={row['error_run_count']}",
                    ]
                )
            )

    print("")
    print(f"===== Recent Runs ({recent_runs_limit}) =====")
    if not report["recent_runs"]:
        print("no recent runs")
    else:
        for row in report["recent_runs"]:
            print(
                " | ".join(
                    [
                        f"started_at={row['started_at']}",
                        f"backlog_start_count={row['backlog_start_count']}",
                        f"new_pending_count={row['new_pending_count']}",
                        f"retargeted_count={row['retargeted_count']}",
                        f"processed_count={row['processed_count']}",
                        f"backlog_end_count={row['backlog_end_count']}",
                        f"oldest_pending_seconds_end={row['oldest_pending_seconds_end']}",
                        f"elapsed_seconds={row['elapsed_seconds']}",
                        f"throughput_per_hour={row['throughput_per_hour']}",
                        f"estimated_drain_seconds={row['estimated_drain_seconds']}",
                        f"result_status={row['result_status']}",
                    ]
                )
            )

    assessment = report["assessment"]
    print("")
    print("===== Assessment =====")
    for key in (
        "processed_count_meets_new_pending",
        "backlog_trend",
        "latest_estimated_drain_seconds",
        "max_wait_seconds",
        "current_max_wait_seconds",
    ):
        print(f"{key:29}: {assessment[key]}")

    print("")
    print("===== Safety Review =====")
    safety = report["safety_review"]
    for key in (
        "simulated_current_price_overwritten_from_current_price",
        "current_price_used_only_for_initial_state_or_null_fallback",
        "rakuten_api_calls_present",
        "store_products_update_present",
    ):
        print(f"{key:53}: {safety[key]}")


def write_csv_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "section",
        "key",
        "value",
        "date",
        "started_at",
        "backlog_start_count",
        "new_pending_count",
        "retargeted_count",
        "processed_count",
        "backlog_end_count",
        "oldest_pending_seconds_end",
        "elapsed_seconds",
        "throughput_per_hour",
        "estimated_drain_seconds",
        "result_status",
        "backlog_max_count",
        "oldest_pending_minutes_max",
        "avg_throughput_per_hour",
        "error_run_count",
    ]

    rows: list[dict[str, Any]] = []
    rows.append({"section": "store", "key": "store_code", "value": report["store"]["store_code"]})
    rows.append({"section": "store", "key": "store_id", "value": report["store"]["store_id"]})
    rows.append({"section": "window", "key": "label", "value": report["window"]["label"]})
    rows.append({"section": "window", "key": "started_at", "value": report["window"]["started_at"]})
    if report["measurement"] is not None:
        for key, value in report["measurement"].items():
            rows.append({"section": "measurement", "key": key, "value": value})

    for key, value in report["current_state"].items():
        rows.append({"section": "current_state", "key": key, "value": value})
    for key, value in report["period_summary"].items():
        rows.append({"section": "period_summary", "key": key, "value": value})
    for key, value in report["assessment"].items():
        rows.append({"section": "assessment", "key": key, "value": value})
    for key, value in report["safety_review"].items():
        rows.append({"section": "safety_review", "key": key, "value": json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value})

    for row in report["daily_summary"]:
        rows.append(
            {
                "section": "daily_summary",
                "date": row["date"],
                "new_pending_count": row["new_pending_count"],
                "retargeted_count": row["retargeted_count"],
                "processed_count": row["processed_count"],
                "backlog_max_count": row["backlog_max_count"],
                "oldest_pending_minutes_max": row["oldest_pending_minutes_max"],
                "avg_throughput_per_hour": row["avg_throughput_per_hour"],
                "error_run_count": row["error_run_count"],
            }
        )

    for row in report["recent_runs"]:
        rows.append(
            {
                "section": "recent_runs",
                "started_at": row["started_at"],
                "backlog_start_count": row["backlog_start_count"],
                "new_pending_count": row["new_pending_count"],
                "retargeted_count": row["retargeted_count"],
                "processed_count": row["processed_count"],
                "backlog_end_count": row["backlog_end_count"],
                "oldest_pending_seconds_end": row["oldest_pending_seconds_end"],
                "elapsed_seconds": row["elapsed_seconds"],
                "throughput_per_hour": row["throughput_per_hour"],
                "estimated_drain_seconds": row["estimated_drain_seconds"],
                "result_status": row["result_status"],
            }
        )

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    report = build_report(args)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report, args.recent_runs)

    if args.csv_output:
        output_path = Path(args.csv_output)
        write_csv_report(report, output_path)
        print("")
        print(f"csv_output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
