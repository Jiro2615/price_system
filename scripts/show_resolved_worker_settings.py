import argparse

from settings_loader import (
    WORKER_TYPE_AMAZON,
    WORKER_TYPE_RAKUTEN,
    format_resolved_settings_json,
    load_resolved_worker_settings,
)


def build_cli_overrides(args: argparse.Namespace) -> dict[str, object]:
    overrides: dict[str, object] = {}

    if args.worker_type == WORKER_TYPE_AMAZON:
        if args.limit is not None:
            overrides["limit"] = args.limit
        if args.sleep is not None:
            overrides["loop_sleep_seconds"] = args.sleep
        if args.empty_sleep is not None:
            overrides["empty_sleep_seconds"] = args.empty_sleep
        if args.page_timeout is not None:
            overrides["page_timeout_ms"] = args.page_timeout
        if args.use_stats is not None:
            overrides["use_stats"] = args.use_stats
        if args.log_retention_days is not None:
            overrides["log_retention_days"] = args.log_retention_days
        return overrides

    if args.price_limit is not None:
        overrides["price_limit"] = args.price_limit
    if args.stock_limit is not None:
        overrides["stock_limit"] = args.stock_limit
    if args.blocked_limit is not None:
        overrides["blocked_limit"] = args.blocked_limit
    if args.empty_sleep is not None:
        overrides["empty_sleep_seconds"] = args.empty_sleep
    if args.error_sleep is not None:
        overrides["error_sleep_seconds"] = args.error_sleep
    if args.verify is not None:
        overrides["verify"] = args.verify
    if args.api_interval is not None:
        overrides["api_interval_seconds"] = args.api_interval
    if args.verify_wait is not None:
        overrides["verify_wait_seconds"] = args.verify_wait
    if args.retry_count is not None:
        overrides["retry_count"] = args.retry_count
    if args.retry_wait is not None:
        overrides["retry_wait_seconds"] = args.retry_wait
    if args.max_change_rate is not None:
        overrides["max_change_rate"] = args.max_change_rate
    if args.inventory_batch_size is not None:
        overrides["inventory_batch_size"] = args.inventory_batch_size
    return overrides


def add_bool_override(parser: argparse.ArgumentParser, name: str, dest: str, help_true: str, help_false: str) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(name, dest=dest, action="store_true", help=help_true)
    group.add_argument(f"--no-{name[2:]}", dest=dest, action="store_false", help=help_false)
    parser.set_defaults(**{dest: None})


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show resolved worker settings from worker_nodes / worker_configs using read-only DB access."
    )
    parser.add_argument("--node-code", default="", help="test override for worker_nodes.node_code")
    parser.add_argument("--worker-type", required=True, choices=[WORKER_TYPE_AMAZON, WORKER_TYPE_RAKUTEN])
    parser.add_argument("--worker-number", type=int, default=None, help="required for amazon_check")
    parser.add_argument("--store", default="", help="required for rakuten_update")
    parser.add_argument("--worker-id", default="", help="optional explicit worker_id override")
    parser.add_argument("--db-name", default="price_system_migrate_test", help="target DB name for read-only checks")

    parser.add_argument("--limit", type=int, default=None, help="amazon override")
    parser.add_argument("--sleep", type=int, default=None, help="amazon override for loop_sleep_seconds")
    parser.add_argument("--empty-sleep", type=int, default=None, help="override empty_sleep_seconds")
    parser.add_argument("--page-timeout", type=int, default=None, help="amazon override for page_timeout_ms")
    add_bool_override(parser, "--use-stats", "use_stats", "amazon override: use stats", "amazon override: disable stats")
    parser.add_argument("--log-retention-days", type=int, default=None, help="amazon override")

    parser.add_argument("--price-limit", type=int, default=None, help="rakuten override")
    parser.add_argument("--stock-limit", type=int, default=None, help="rakuten override")
    parser.add_argument("--blocked-limit", type=int, default=None, help="rakuten override")
    parser.add_argument("--error-sleep", type=int, default=None, help="rakuten override for error_sleep_seconds")
    add_bool_override(parser, "--verify", "verify", "rakuten override: verify", "rakuten override: no verify")
    parser.add_argument("--api-interval", type=float, default=None, help="rakuten override")
    parser.add_argument("--verify-wait", type=float, default=None, help="rakuten override")
    parser.add_argument("--retry-count", type=int, default=None, help="rakuten override")
    parser.add_argument("--retry-wait", type=float, default=None, help="rakuten override")
    parser.add_argument("--max-change-rate", type=float, default=None, help="rakuten override")
    parser.add_argument("--inventory-batch-size", type=int, default=None, help="rakuten override")

    args = parser.parse_args()

    store_code = args.store.strip() or None
    node_code = args.node_code.strip() or None
    worker_id = args.worker_id.strip() or None

    if args.worker_type == WORKER_TYPE_AMAZON and args.worker_number is None:
        raise RuntimeError("--worker-number is required for amazon_check")
    if args.worker_type == WORKER_TYPE_RAKUTEN and not store_code:
        raise RuntimeError("--store is required for rakuten_update")

    cli_overrides = build_cli_overrides(args)

    data = load_resolved_worker_settings(
        worker_type=args.worker_type,
        worker_number=args.worker_number,
        store_code=store_code,
        node_code=node_code,
        explicit_worker_id=worker_id,
        cli_overrides=cli_overrides,
        db_name=args.db_name,
    )

    print(format_resolved_settings_json(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
