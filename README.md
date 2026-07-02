# 楽天価格・在庫更新・出品管理システム

## 目的
楽天店舗の商品について、Amazonの価格・在庫・発送可否を確認し、楽天側の販売価格・在庫数をDBで管理する。  
更新は、通常運用ではAPI、全体価格ロジック変更時などの大量更新では楽天CSV一括編集を使う。

将来的には、出品管理・配送番号取得・配達ボックス番号取得・メール処理まで統合する。

## 全体方針

### 普段の価格更新
普段はAmazonページを見て、必要な商品だけ1件ずつ、または少量ずつ更新する。

想定フロー:

```powershell
cd C:\price_system\scripts
py price_check_from_db.py --limit 20 --summary
py price_check_from_db.py --limit 20 --summary --use-stats
py price_check_from_db.py --limit 20 --summary --use-stats --worker-id PC1-worker1
py calc_store_targets.py --store rakuten_1
py show_update_targets.py --mall rakuten --limit 50
py rakuten_price_patch.py --execute --limit 5
```

`--use-stats` を付けると `amazon_check_stats.next_check_at` とロック列を使って、未チェック・長時間未チェックの商品を優先しながら Amazon チェック対象を claim する。`--worker-id` 未指定時は PC 名と PID から自動生成する。

継続実行ループの例:

```powershell
py amazon_check_worker_loop.py --worker-id PC1-worker1 --limit 300 --sleep 10 --once
py amazon_check_worker_loop.py --worker-id PC1-worker1 --limit 300 --sleep 10 --max-loops 2
py amazon_check_worker_loop.py --worker-id PC1-worker1 --limit 300 --sleep 10 --empty-sleep 60 --stop-after-empty
```

`amazon_check_worker_loop.py` は `price_check_from_db.py --summary --use-stats` を繰り返し呼び、対象0件のときは `--empty-sleep` 秒待つ。

日常運用フローをまとめて流す場合:

```powershell
py rakuten_daily_update_flow.py --amazon-limit 20
py rakuten_daily_update_flow.py --amazon-limit 20 --execute
py rakuten_daily_update_flow.py --amazon-limit 50 --price-limit 20 --stock-limit 50 --blocked-limit 20 --execute
```

`rakuten_daily_update_flow.py` は CSV/SFTP を使わず、Amazon確認 → target計算 → 更新対象確認 → 在庫API更新 → 価格API更新 → blocked商品API fallback → 最終確認を順番に呼ぶ親フロー。

価格APIは楽天側のリクエスト制限があるため、短時間に大量実行しない。  
実績としては1.5秒間隔程度で通っている。

### 普段の在庫更新
在庫は楽天Inventory APIのbulk-upsertでまとめて更新する。

```powershell
py rakuten_inventory_bulk_upsert.py --execute --limit 50
```

### 全体価格更新
価格計算ロジックを変えたとき、利益テーブルを変えたとき、ポイント考慮ON/OFFなどを変えたときは、楽天CSV一括編集を使う。

```powershell
py rakuten_csv_price_update_flow.py --limit 50000
py rakuten_csv_price_update_flow.py --limit 50000 --execute --timeout 7200 --settle-wait 600
```

CSV更新は全体変更用であり、日常の小規模更新の第一候補ではない。

## DB
DB名: `price_system`  
主なテーブル:

- `stores`
- `amazon_products`
- `store_products`
- `price_rules`
- `price_update_logs`
- `order_logs`
- `rakuten_api_snapshots`

現在メイン店舗: `rakuten_1`

## CSV更新の判定
楽天CSV処理は、成功時にログが出ない可能性がある。

判定ルール:

1. CSVを `/ritem/batch` にアップロード
2. `/ritem/batch` からCSVが消える
3. `/ritem/logs` にエラーログが出るか監視
4. エラーなしで `settle-wait` 経過 → 成功扱い
5. エラーあり → 成功分DB反映 + エラー商品blocked化

## CSV blocked商品
楽天CSVで商品属性不足などのエラーになった商品は、以下のカラムで管理する。

```sql
rakuten_csv_update_blocked BOOLEAN
rakuten_csv_update_error TEXT
rakuten_csv_update_error_at TIMESTAMP
```

blocked商品は次回CSVから除外される。  
価格更新が必要な場合はAPI更新へ回す。

```powershell
py rakuten_price_patch.py --blocked-only --limit 20
py rakuten_price_patch.py --blocked-only --execute --limit 20
```

`--blocked-only` は `rakuten_csv_update_blocked = TRUE` の商品のみを対象にする。  
API更新に成功しても、CSV属性エラーが解消されたとは限らないため blocked フラグは解除しない。

## 重要な注意
- `.env` に認証情報を置く。
- DB接続は `.env` の `PRICE_SYSTEM_DB_PASSWORD` または `DB_PASSWORD` を使う。
- 認証情報をコードへ直書きしない。
- `--execute` は明示依頼があるときだけ使う。
- テストで全件+1円のような実影響のある操作は避ける。
- 処理時間テストはno-op CSVを使う。
