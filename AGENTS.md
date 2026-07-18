# AGENTS.md

## Project
楽天価格・在庫更新・出品管理システム。

Amazonの商品ページから価格・在庫・発送可否・ギフト可否などを取得し、PostgreSQL上の `price_system` DBで楽天商品の価格・在庫更新対象を管理する。  
最終的には、楽天API・楽天CSV一括編集・Amazon配送メール・配達ボックス通知メール・出品管理まで含めた運用システムにする。

## Environment
- OS: Windows
- Project root: `C:\price_system`
- Scripts: `C:\price_system\scripts`
- DB: PostgreSQL
- DB name: `price_system`
- DB user: `price_app`
- Main store: `rakuten_1`
- Python: use `py` or the active Python 3.12 installation
- Secrets: use `.env`; never hardcode real passwords, API keys, SFTP passwords, or license keys in code.

## Core Philosophy
Daily updates and bulk updates are different operations.

### Daily / routine update
Use Amazon page checking and API-based updates.
1. Check Amazon price/stock/shipping/gift status.
2. Calculate `target_price` / `target_stock`.
3. If a product needs updating, update it individually or in small batches.
4. Price update: use Rakuten item API patch, respecting about 1 request per second.
5. Stock update: use Rakuten inventory API, preferably bulk-upsert.

### Bulk / global update
Use Rakuten CSV only when many products need recalculation.
Examples:
- Price rule table changed.
- Profit logic changed.
- Amazon point handling changed.
- Rounding logic changed.
- Store-wide price policy changed.

CSV is not the default daily update route. CSV is the “bulk artillery” for full-store recalculation or large update waves.

## Safety Rules
- Never run `--execute` scripts unless the user explicitly asks.
- Always prefer dry-run first.
- Never upload CSV automatically unless the command explicitly asks for execution.
- Do not hardcode credentials.
- Do not remove `--dry-run` / preview behavior.
- Do not include `rakuten_csv_update_blocked = true` products in CSV unless explicitly requested.
- Do not treat CSV error logs as total failure when there are partial successes.
- If CSV error log exists:
  - Mark errored products as `rakuten_csv_update_blocked = true`.
  - Apply successful rows to DB.
  - Leave blocked products for API update.
- If CSV disappears from `/ritem/batch` and no error log appears after `settle-wait`, treat it as success.
- Rakuten CSV output must be CP932 / Shift-JIS-compatible.
- SKU-only CSV is not valid for Rakuten normal-item update. Product-level rows are required.
- Do not change production prices casually for testing. Use no-op CSV where possible.

## Important Commands

### Amazon check
```powershell
cd C:\price_system\scripts
py price_check_from_db.py --limit 20 --summary
```

### Calculate targets
```powershell
py calc_store_targets.py --store rakuten_1
```

### Show update targets
```powershell
py show_update_targets.py --mall rakuten --limit 50
```

### Daily small price API update
```powershell
py rakuten_price_patch.py --execute --limit 5
```

### Inventory update via API bulk
```powershell
py rakuten_inventory_bulk_upsert.py --execute --limit 50
```

### Bulk CSV flow dry-run
```powershell
py rakuten_csv_price_update_flow.py --limit 50000
```

### Bulk CSV flow execute
```powershell
py rakuten_csv_price_update_flow.py --limit 50000 --execute --timeout 7200 --settle-wait 600
```

## Key Scripts
- `price_check_from_db.py`: checks Amazon pages for ASINs in DB.
- `price_check_one_asin_db.py`: checks one ASIN.
- `calc_store_targets.py`: calculates `target_price` and `target_stock`.
- `show_update_targets.py`: shows current vs target differences.
- `rakuten_price_patch.py`: API price patch for small/routine price updates.
- `rakuten_inventory_bulk_upsert.py`: inventory update using Rakuten inventory bulk API.
- `export_rakuten_normal_item_price_csv.py`: creates Rakuten `normal-item_price_*.csv`.
- `rakuten_csv_winscp_upload_and_watch.py`: uploads CSV using WinSCP and watches batch/logs.
- `apply_rakuten_csv_success_to_db.py`: applies all-success CSV result to DB.
- `apply_rakuten_csv_result_to_db.py`: applies partial-success CSV result and blocks errored products.
- `rakuten_csv_price_update_flow.py`: parent flow for bulk CSV price update.
- `rakuten_sync_one_to_db.py`: reads one product/SKU from Rakuten API and syncs DB.
- `import_rakuten_normal_item_csv.py`: imports RMS product CSV into DB.
- `import_rakuten_asin_map_csv.py`: imports Rakuten item code to ASIN map.

## Known Rakuten CSV Rules
- `normal-item.csv` must be CP932/Shift-JIS-compatible.
- File name should begin with `normal-item`.
- Product-level row is required even when updating SKU-level price.
- SKU-only CSV causes error:
  - 商品オプションレベル行のみ、またはSKUレベル行のみを更新する場合であっても、商品レベル行を記載する必要があります。
- Product-level row can trigger required attribute validation.
- Products that fail CSV because of missing required attributes should be blocked from future CSV and updated via API.

## Current Architecture Decision
- Routine price update: Amazon check + `rakuten_price_patch.py`.
- Routine stock update: Amazon check + `rakuten_inventory_bulk_upsert.py`.
- Bulk price update: `rakuten_csv_price_update_flow.py`.
- CSV blocked products: update via API.
- Future mail processing:
  - Rakuten CSV result emails.
  - Amazon shipment emails.
  - Delivery box notification emails.

## Future Work Priority
1. Stabilize routine API update flow.
2. Stabilize bulk CSV update flow.
3. Add blocked-product API fallback flow.
4. Add scheduling / orchestration.
5. Add mail ingestion framework.
6. Parse Amazon shipment emails.
7. Parse delivery box notification emails.
8. Add listing/export/import replacement for current paid listing tool.

## Encoding Rules

- Source files must use UTF-8 without BOM.
- Python user-facing log messages may contain Japanese.
- Python identifiers and comments should preferably use English.
- Batch and PowerShell scripts should avoid Japanese text.
- CP932 is allowed only for Rakuten CSV input/output files.
- Always detect the existing encoding before editing.
- Do not rewrite an entire file solely because text appears garbled.
- Do not mix encoding normalization with logic changes.
- Preserve the existing line endings unless the task specifically changes them.
- After editing Python files, validate them with `ast.parse()`.
- Never decode with `errors="replace"` when editing source code.
