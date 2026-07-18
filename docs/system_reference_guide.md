# System Reference Guide

## Purpose

This document is a practical reference for the current `C:\price_system` repository.

Use it when you need to understand:

- what the system does end to end
- where each major file lives
- which script should be used for which operation
- how Amazon check, target calculation, Rakuten API update, and Rakuten CSV update are separated
- which APIs and tables are involved
- where to look first when behavior is unclear

This guide is intentionally operational. It is not a future roadmap. It explains the repository as it exists now.

## 1. Project Summary

This repository manages Rakuten selling prices and stock based on Amazon product page checks.

The system is split into two main update routes:

- Daily update route
  - Amazon page check
  - DB update
  - `target_price` / `target_stock` recalculation
  - Rakuten API update for price and stock
- Bulk update route
  - full-store target recalculation
  - Rakuten CSV export
  - SFTP upload and result watch
  - success apply + blocked-product handling

Important design rule:

- daily or small updates should use Rakuten APIs
- large all-store recalculation should use Rakuten CSV

## 2. Repository Layout

### Root

- [README.md](/abs/path/C:/price_system/README.md)
  - high-level operational overview
- [AGENTS.md](/abs/path/C:/price_system/AGENTS.md)
  - working rules, safety rules, encoding rules
- [requirements.txt](/abs/path/C:/price_system/requirements.txt)
  - Python dependencies
- [.env.example](/abs/path/C:/price_system/.env.example)
  - example environment variable file
- [ROADMAP.md](/abs/path/C:/price_system/ROADMAP.md)
  - future-oriented notes if present
- [TODO.md](/abs/path/C:/price_system/TODO.md)
  - local task notes if present

### Main directories

- [scripts](/abs/path/C:/price_system/scripts)
  - core operational scripts
- [docs](/abs/path/C:/price_system/docs)
  - design notes, settings inventory, migrations
- [tests](/abs/path/C:/price_system/tests)
  - test files
- [config](/abs/path/C:/price_system/config)
  - local launcher config files
- [input](/abs/path/C:/price_system/input)
  - source files and imported CSVs
- [output](/abs/path/C:/price_system/output)
  - generated JSON, logs, dry-run outputs
- [backup](/abs/path/C:/price_system/backup)
  - DB dump files and restore test artifacts

## 3. Main Operational Flows

### 3.1 Amazon check flow

Primary files:

- [price_check_from_db.py](/abs/path/C:/price_system/scripts/price_check_from_db.py)
- [price_check_one_asin_db.py](/abs/path/C:/price_system/scripts/price_check_one_asin_db.py)
- [amazon_check_worker_loop.py](/abs/path/C:/price_system/scripts/amazon_check_worker_loop.py)

Flow:

1. Select ASIN targets from DB
2. Open Amazon pages
3. Parse price, point, stock, shipping, gift availability, restriction pages, BuyBox state
4. Save result to `amazon_products`
5. Update `amazon_check_stats`
6. Recalculate `target_price` / `target_stock` for related Rakuten products

Use cases:

- one-shot small run:
  - `py price_check_from_db.py --limit 20 --summary`
- stats-based claim/lock run:
  - `py price_check_from_db.py --limit 20 --summary --use-stats`
- one-ASIN diagnosis:
  - `py price_check_one_asin_db.py B0047XOC0A`
- continuous worker loop:
  - `py amazon_check_worker_loop.py --worker-number 1 --once`

### 3.2 Target recalculation flow

Primary file:

- [calc_store_targets.py](/abs/path/C:/price_system/scripts/calc_store_targets.py)

Purpose:

- convert Amazon state into Rakuten `target_price` and `target_stock`
- apply store policy such as fee rate, profit rule, stock cap, and error handling

Key behavior:

- `business_ng` usually drives `target_stock = 0`
- `system_error` keeps current target unchanged
- stock is capped by `stores.max_stock`
- final price is rounded to integer price, with current policy implemented in code

Use cases:

- full store:
  - `py calc_store_targets.py --store rakuten_1`
- one ASIN:
  - `py calc_store_targets.py --store rakuten_1 --asin 1950321444`
- multiple ASINs:
  - `py calc_store_targets.py --store rakuten_1 --asin-list "1950321444,3037786574"`

### 3.3 Show update targets

Primary file:

- [show_update_targets.py](/abs/path/C:/price_system/scripts/show_update_targets.py)

Purpose:

- compare current Rakuten DB values and calculated targets
- preview which products still need update

Typical command:

- `py show_update_targets.py --mall rakuten --limit 50`

### 3.4 Rakuten daily API update flow

Primary files:

- [rakuten_inventory_bulk_upsert.py](/abs/path/C:/price_system/scripts/rakuten_inventory_bulk_upsert.py)
- [rakuten_price_patch.py](/abs/path/C:/price_system/scripts/rakuten_price_patch.py)
- [rakuten_update_worker_loop.py](/abs/path/C:/price_system/scripts/rakuten_update_worker_loop.py)
- [rakuten_daily_update_flow.py](/abs/path/C:/price_system/scripts/rakuten_daily_update_flow.py)

Flow:

1. stock update by inventory bulk API
2. price update by item patch API
3. blocked-product fallback by item patch API if needed

Important behavior:

- do not call Rakuten API unless `--execute` is specified
- dry-run should remain safe
- stock and price are handled separately
- price API pacing and retry control live in `rakuten_price_patch.py`

### 3.5 Rakuten bulk CSV update flow

Primary files:

- [export_rakuten_normal_item_price_csv.py](/abs/path/C:/price_system/scripts/export_rakuten_normal_item_price_csv.py)
- [rakuten_csv_winscp_upload_and_watch.py](/abs/path/C:/price_system/scripts/rakuten_csv_winscp_upload_and_watch.py)
- [apply_rakuten_csv_success_to_db.py](/abs/path/C:/price_system/scripts/apply_rakuten_csv_success_to_db.py)
- [apply_rakuten_csv_result_to_db.py](/abs/path/C:/price_system/scripts/apply_rakuten_csv_result_to_db.py)
- [rakuten_csv_price_update_flow.py](/abs/path/C:/price_system/scripts/rakuten_csv_price_update_flow.py)

Purpose:

- perform full-store or large-batch price updates when pricing rules change

Important CSV rules:

- output must be CP932 / Shift-JIS compatible
- filename must begin with `normal-item`
- product-level row is required
- CSV errors may be partial, not total failure
- blocked products must be excluded from future CSV runs and handled by API

## 4. Script Reference

### Core DB and settings

- [db_config.py](/abs/path/C:/price_system/scripts/db_config.py)
  - shared PostgreSQL connection loader
  - reads `PRICE_SYSTEM_DB_*` and fallback `DB_*`
- [db_retry.py](/abs/path/C:/price_system/scripts/db_retry.py)
  - DB retry helper if used by callers
- [settings_loader.py](/abs/path/C:/price_system/scripts/settings_loader.py)
  - resolves worker settings with priority:
    - CLI explicit value
    - DB `settings_json`
    - code default
- [show_resolved_worker_settings.py](/abs/path/C:/price_system/scripts/show_resolved_worker_settings.py)
  - read-only inspector for resolved worker settings

### Amazon side

- [price_check_one_asin_db.py](/abs/path/C:/price_system/scripts/price_check_one_asin_db.py)
  - one-ASIN browser check and parsing
- [price_check_from_db.py](/abs/path/C:/price_system/scripts/price_check_from_db.py)
  - DB target selection, claim/lock, save, stats update, worker summary
- [amazon_check_worker_loop.py](/abs/path/C:/price_system/scripts/amazon_check_worker_loop.py)
  - long-running parent loop for Amazon checks
- [start_amazon_workers.ps1](/abs/path/C:/price_system/scripts/start_amazon_workers.ps1)
  - launcher for multiple Amazon worker windows
- [start_amazon_workers.bat](/abs/path/C:/price_system/scripts/start_amazon_workers.bat)
  - batch wrapper
- [start_amazon_workers_once.bat](/abs/path/C:/price_system/scripts/start_amazon_workers_once.bat)
  - one-loop wrapper

### Recalculation and preview

- [calc_store_targets.py](/abs/path/C:/price_system/scripts/calc_store_targets.py)
  - recalculates target values
- [show_update_targets.py](/abs/path/C:/price_system/scripts/show_update_targets.py)
  - preview differences

### Rakuten API side

- [rakuten_auth.py](/abs/path/C:/price_system/scripts/rakuten_auth.py)
  - loads per-store auth from `.env`
  - builds ESA auth header
- [rakuten_inventory_bulk_upsert.py](/abs/path/C:/price_system/scripts/rakuten_inventory_bulk_upsert.py)
  - stock update
- [rakuten_price_patch.py](/abs/path/C:/price_system/scripts/rakuten_price_patch.py)
  - price update
- [rakuten_sync_one_to_db.py](/abs/path/C:/price_system/scripts/rakuten_sync_one_to_db.py)
  - fetches one Rakuten item and inventory state into DB
- [rakuten_update_worker_loop.py](/abs/path/C:/price_system/scripts/rakuten_update_worker_loop.py)
  - looping API updater
- [start_rakuten_update_worker.ps1](/abs/path/C:/price_system/scripts/start_rakuten_update_worker.ps1)
  - launcher
- [start_rakuten_update_worker.bat](/abs/path/C:/price_system/scripts/start_rakuten_update_worker.bat)
  - batch wrapper
- [start_rakuten_update_worker_once.bat](/abs/path/C:/price_system/scripts/start_rakuten_update_worker_once.bat)
  - one-loop wrapper

### Rakuten CSV side

- [rakuten_csv_price_update_flow.py](/abs/path/C:/price_system/scripts/rakuten_csv_price_update_flow.py)
  - parent flow
- [rakuten_csv_winscp_upload_and_watch.py](/abs/path/C:/price_system/scripts/rakuten_csv_winscp_upload_and_watch.py)
  - upload and watch
- [export_rakuten_normal_item_price_csv.py](/abs/path/C:/price_system/scripts/export_rakuten_normal_item_price_csv.py)
  - CSV export
- [export_rakuten_normal_item_noop_csv.py](/abs/path/C:/price_system/scripts/export_rakuten_normal_item_noop_csv.py)
  - no-op timing or upload validation
- [apply_rakuten_csv_success_to_db.py](/abs/path/C:/price_system/scripts/apply_rakuten_csv_success_to_db.py)
  - all-success apply
- [apply_rakuten_csv_result_to_db.py](/abs/path/C:/price_system/scripts/apply_rakuten_csv_result_to_db.py)
  - partial-success apply and block

### Simulation and reporting

- [rakuten_price_update_simulator.py](/abs/path/C:/price_system/scripts/rakuten_price_update_simulator.py)
  - shadow simulation of price update throughput without touching real `current_price`
- [report_rakuten_price_simulation.py](/abs/path/C:/price_system/scripts/report_rakuten_price_simulation.py)
  - read-only reporting of simulation state and runs

### Setup and backup

- [setup_worker_pc.ps1](/abs/path/C:/price_system/scripts/setup_worker_pc.ps1)
  - worker PC setup helper
- [backup_local_db.ps1](/abs/path/C:/price_system/scripts/backup_local_db.ps1)
  - local DB dump
- [backup_qnap_db.ps1](/abs/path/C:/price_system/scripts/backup_qnap_db.ps1)
  - central QNAP DB dump
- [restore_to_qnap_test_db.ps1](/abs/path/C:/price_system/scripts/restore_to_qnap_test_db.ps1)
  - restore helper for test DB
- [check_qnap_db.ps1](/abs/path/C:/price_system/scripts/check_qnap_db.ps1)
  - DB connectivity and count checks
- [test_db_connection.py](/abs/path/C:/price_system/scripts/test_db_connection.py)
  - simple DB connection confirmation

## 5. Database Reference

This repository depends heavily on PostgreSQL. The most important tables are:

- `stores`
  - per-store policy and metadata
  - includes `store_code`, `mall`, `max_stock`, pricing-related fields
- `price_rules`
  - store-specific pricing rules
- `amazon_products`
  - last known Amazon state per ASIN
- `store_products`
  - Rakuten-side product rows with current and target values
- `amazon_check_stats`
  - Amazon claim/lock scheduling state
- `amazon_check_worker_runs`
  - per-run Amazon worker metrics
- `price_update_logs`
  - Rakuten update result logs
- `rakuten_api_snapshots`
  - stored API snapshots if available in current flow
- `price_update_sim_state`
  - simulator shadow current price state
- `price_update_sim_runs`
  - simulator run summaries
- `price_update_sim_measurements`
  - named measurement windows for simulation reports

For management-setting tables, see:

- [settings_inventory.md](/abs/path/C:/price_system/docs/settings_inventory.md)
- [20260705_management_v1_tables.sql](/abs/path/C:/price_system/docs/migrations/20260705_management_v1_tables.sql)

## 6. External API Reference

### Rakuten item API

Used mainly by [rakuten_price_patch.py](/abs/path/C:/price_system/scripts/rakuten_price_patch.py).

Base:

- `https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/{manageNumber}`

Typical use:

- `PATCH` for price update
- optional `GET` verify when `--verify` is enabled

Auth:

- ESA auth header built by [rakuten_auth.py](/abs/path/C:/price_system/scripts/rakuten_auth.py)

### Rakuten inventory API

Used mainly by [rakuten_inventory_bulk_upsert.py](/abs/path/C:/price_system/scripts/rakuten_inventory_bulk_upsert.py).

Base:

- `https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-upsert`

Single inventory read path is also used in [rakuten_sync_one_to_db.py](/abs/path/C:/price_system/scripts/rakuten_sync_one_to_db.py):

- `https://api.rms.rakuten.co.jp/es/2.1/inventories/manage-numbers/{manageNumber}/variants/{sku}`

### Amazon product pages

Used by:

- [price_check_one_asin_db.py](/abs/path/C:/price_system/scripts/price_check_one_asin_db.py)
- [price_check_from_db.py](/abs/path/C:/price_system/scripts/price_check_from_db.py)

Current parsing behavior is implemented in code rather than a formal API spec.

Important note:

- Amazon is not queried through an official product API here
- browser automation and HTML parsing are the source of truth
- restriction pages, BuyBox absence, 404 pages, region limits, adult checks, and medical restrictions are treated by parser logic

## 7. Environment Variables and Secrets

Main DB settings:

- `PRICE_SYSTEM_DB_HOST`
- `PRICE_SYSTEM_DB_PORT`
- `PRICE_SYSTEM_DB_NAME`
- `PRICE_SYSTEM_DB_USER`
- `PRICE_SYSTEM_DB_PASSWORD`

Rakuten auth settings:

- `RAKUTEN_1_SERVICE_SECRET`
- `RAKUTEN_1_LICENSE_KEY`
- `RAKUTEN_2_SERVICE_SECRET`
- `RAKUTEN_2_LICENSE_KEY`

Compatibility fallback for `rakuten_1` may still exist for older single-store keys, but new code should follow the store-prefixed naming.

Never store secrets in:

- tracked source files
- markdown docs
- test fixtures
- launcher logs

## 8. Launcher and Worker Configuration

There are two layers of runtime configuration:

### Local machine layer

Examples:

- PowerShell launcher `.ini` files under [config](/abs/path/C:/price_system/config)
- `PRICE_SYSTEM_NODE_CODE`
- local Python command
- local project path

This layer is machine-specific.

### DB-backed worker layer

Resolved through [settings_loader.py](/abs/path/C:/price_system/scripts/settings_loader.py).

Priority:

```text
CLI explicit value
-> DB settings_json
-> code default
```

Reference files:

- [settings_inventory.md](/abs/path/C:/price_system/docs/settings_inventory.md)
- [show_resolved_worker_settings.py](/abs/path/C:/price_system/scripts/show_resolved_worker_settings.py)

## 9. Safety Model

Always assume the following:

- `--execute` is dangerous and must be explicit
- dry-run is the default safety route
- CSV and API are separate routes
- blocked CSV products are not automatically safe for CSV on the next run
- `stores.max_stock` is a hard safety rule for Rakuten stock
- `system_error` on Amazon side should not force target recalculation that changes selling state

Before real updates, the usual safe sequence is:

1. `price_check_from_db.py --summary`
2. `calc_store_targets.py`
3. `show_update_targets.py`
4. API dry-run
5. API execute only if reviewed

## 10. Where To Look When You Are Not Sure

### If you do not know how the whole system is supposed to work

Start with:

- [README.md](/abs/path/C:/price_system/README.md)
- [rakuten_price_system_design.md](/abs/path/C:/price_system/docs/rakuten_price_system_design.md)

### If you do not know which settings are CLI vs DB vs `.env`

Look at:

- [settings_inventory.md](/abs/path/C:/price_system/docs/settings_inventory.md)
- [settings_loader.py](/abs/path/C:/price_system/scripts/settings_loader.py)

### If you do not know how Amazon worker target claim works

Look at:

- [price_check_from_db.py](/abs/path/C:/price_system/scripts/price_check_from_db.py)
  - `ensure_amazon_check_stats_schema`
  - `claim_target_asins_by_stats_v2`
  - `update_amazon_check_stats`
  - `build_worker_run_summary`

### If you do not know why a Rakuten stock update was skipped

Look at:

- [rakuten_inventory_bulk_upsert.py](/abs/path/C:/price_system/scripts/rakuten_inventory_bulk_upsert.py)
  - `validate_target_stock_for_store`
  - `split_safe_and_skipped_rows`

### If you do not know how price update pacing or verify works

Look at:

- [rakuten_price_patch.py](/abs/path/C:/price_system/scripts/rakuten_price_patch.py)
  - `call_item_patch`
  - `call_item_get`
  - `retry_wait_seconds`
  - `print_wait_log`
  - `print_summary`

### If you do not know how target price is calculated

Look at:

- [calc_store_targets.py](/abs/path/C:/price_system/scripts/calc_store_targets.py)
  - `calc_price`
  - `calc_target_for_row`
  - `resolve_store_max_stock`

### If you do not know how CSV success or partial success is applied

Look at:

- [apply_rakuten_csv_success_to_db.py](/abs/path/C:/price_system/scripts/apply_rakuten_csv_success_to_db.py)
- [apply_rakuten_csv_result_to_db.py](/abs/path/C:/price_system/scripts/apply_rakuten_csv_result_to_db.py)

### If you do not know how to test worker configuration safely

Look at:

- [show_resolved_worker_settings.py](/abs/path/C:/price_system/scripts/show_resolved_worker_settings.py)
- launcher `-DryRun` options in PowerShell scripts

### If you do not know whether something belongs in this repo or the separate listing repo

Use this rule:

- `C:\price_system` is the main Amazon check + Rakuten update operations repo
- new listing-preparation work intended for the separate listing flow should not be mixed in here without explicit decision

## 11. Recommended Reading Order For New Work

For operations work:

1. [AGENTS.md](/abs/path/C:/price_system/AGENTS.md)
2. [README.md](/abs/path/C:/price_system/README.md)
3. this file
4. target script

For Amazon parser work:

1. [price_check_one_asin_db.py](/abs/path/C:/price_system/scripts/price_check_one_asin_db.py)
2. [price_check_from_db.py](/abs/path/C:/price_system/scripts/price_check_from_db.py)
3. [amazon_check_worker_loop.py](/abs/path/C:/price_system/scripts/amazon_check_worker_loop.py)

For Rakuten API work:

1. [rakuten_auth.py](/abs/path/C:/price_system/scripts/rakuten_auth.py)
2. [rakuten_inventory_bulk_upsert.py](/abs/path/C:/price_system/scripts/rakuten_inventory_bulk_upsert.py)
3. [rakuten_price_patch.py](/abs/path/C:/price_system/scripts/rakuten_price_patch.py)
4. [rakuten_update_worker_loop.py](/abs/path/C:/price_system/scripts/rakuten_update_worker_loop.py)

For CSV work:

1. [export_rakuten_normal_item_price_csv.py](/abs/path/C:/price_system/scripts/export_rakuten_normal_item_price_csv.py)
2. [rakuten_csv_winscp_upload_and_watch.py](/abs/path/C:/price_system/scripts/rakuten_csv_winscp_upload_and_watch.py)
3. [apply_rakuten_csv_result_to_db.py](/abs/path/C:/price_system/scripts/apply_rakuten_csv_result_to_db.py)
4. [rakuten_csv_price_update_flow.py](/abs/path/C:/price_system/scripts/rakuten_csv_price_update_flow.py)

## 12. Scope Boundary

This guide documents the current main repo only.

It does not define:

- separate listing-only repository structure
- future web admin implementation details
- future mail ingestion internals beyond current design notes
- business process outside the current automation code
