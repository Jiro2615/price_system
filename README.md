# 楽天価格・在庫更新・出品管理システム

## ドキュメント案内
詳細仕様、主要ファイルの役割、APIの使い分け、DBやworker設定、迷ったときの参照先は以下を使う。

- [docs/system_reference_guide.md](/abs/path/C:/price_system/docs/system_reference_guide.md)
  - 全体の実務向けガイド
  - ファイルのありか、主要スクリプトの説明、DB/APIの参照先
- [docs/rakuten_price_system_design.md](/abs/path/C:/price_system/docs/rakuten_price_system_design.md)
  - 価格・在庫更新ルートの設計方針
- [docs/settings_inventory.md](/abs/path/C:/price_system/docs/settings_inventory.md)
  - CLI、DB設定、`.env` の役割分担

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
## 初回セットアップ

### clone後に置くもの

`C:\price_system` を clone した後、少なくとも以下をローカルに用意してください。

- `.env`
- `input\` 配下で使う各種CSVや手動取込ファイル
- `output\` と `temp\` を使う場合は、必要に応じて作成

`.env` は Git に入れない方針です。  
このリポジトリでは `.gitignore` で `.env` を除外しており、認証情報やパスワードはコミットしません。

### .env に書くもの

最低限、DB接続と楽天API用に以下の環境変数を設定してください。

```dotenv
PRICE_SYSTEM_DB_HOST=localhost
PRICE_SYSTEM_DB_PORT=5432
PRICE_SYSTEM_DB_NAME=price_system
PRICE_SYSTEM_DB_USER=price_app
PRICE_SYSTEM_DB_PASSWORD=your_password_here

RAKUTEN_1_SERVICE_SECRET=your_rakuten_service_secret
RAKUTEN_1_LICENSE_KEY=your_rakuten_license_key
```

補足:

- DB接続は `PRICE_SYSTEM_DB_PASSWORD` を優先し、互換のため `DB_PASSWORD` も利用可能です。
- DB接続は `PRICE_SYSTEM_DB_HOST` / `PORT` / `NAME` / `USER` も優先し、旧 `DB_*` 名は互換用です。
- 本番のパスワードやAPIキーは README やソースコードに直接書かないでください。

### 複数PCでDBを共有する場合

Amazonワーカーを複数PCで動かす場合は、各PCが同じ PostgreSQL に接続する前提でそろえます。  
アプリ側で最低限そろえる項目は以下です。

```dotenv
PRICE_SYSTEM_DB_HOST=192.168.1.10
PRICE_SYSTEM_DB_PORT=5432
PRICE_SYSTEM_DB_NAME=price_system
PRICE_SYSTEM_DB_USER=price_app
PRICE_SYSTEM_DB_PASSWORD=shared_db_password
```

考え方:

- `PRICE_SYSTEM_DB_HOST` は DB サーバーのホスト名または固定IPを指定する
- `PRICE_SYSTEM_DB_PORT` は PostgreSQL の待受ポートを指定する
- `PRICE_SYSTEM_DB_NAME` / `USER` / `PASSWORD` は全PCで同じ共有DBの値を使う
- `.env` は各PCローカルに置き、Gitには入れない
- PostgreSQL サーバーの `listen_addresses` や `pg_hba.conf` の変更は別作業として進める

他PC側の `.env` 例:

```dotenv
PRICE_SYSTEM_DB_HOST=192.168.1.10
PRICE_SYSTEM_DB_PORT=5432
PRICE_SYSTEM_DB_NAME=price_system
PRICE_SYSTEM_DB_USER=price_app
PRICE_SYSTEM_DB_PASSWORD=shared_db_password
RAKUTEN_1_SERVICE_SECRET=your_rakuten_service_secret
RAKUTEN_1_LICENSE_KEY=your_rakuten_license_key
```

接続確認コマンド:

```powershell
cd C:\price_system\scripts
py -m py_compile db_config.py
py test_db_connection.py
py price_check_from_db.py --limit 1 --summary --use-stats --worker-id db-config-test
```

worker_id 例:

- `PC1-worker1`
- `PC1-worker2`
- `PC2-worker1`
- `PC2-worker2`

### まず最初に確認するコマンド

clone後の確認は、まず dry-run 系か読み取り系から始めてください。

```powershell
cd C:\price_system\scripts
py test_db_connection.py
py price_check_from_db.py --limit 5 --summary
py calc_store_targets.py --store rakuten_1
py show_update_targets.py --mall rakuten --limit 20
```

確認の順番の目安:

1. `py test_db_connection.py`
2. `py price_check_from_db.py --limit 5 --summary`
3. `py calc_store_targets.py --store rakuten_1`
4. `py show_update_targets.py --mall rakuten --limit 20`

注意:

- `--execute` 付きコマンドは、初回確認では実行しないでください。
- 楽天API更新やCSV更新は、DB接続・Amazonチェック・target計算を確認してから進めてください。

### 別PCセットアップ

別PCへ `price_system` を展開する時は、まず Python 仮想環境と依存ライブラリを入れる。

```powershell
git clone https://github.com/Jiro2615/price_system.git
cd C:\price_system
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
```

依存ライブラリは `requirements.txt` にまとめている。

- `playwright`
- `psycopg[binary]`
- `python-dotenv`
- `requests`

`.env` 作成後は、少なくとも以下を設定する。

```dotenv
PRICE_SYSTEM_DB_HOST=192.168.1.10
PRICE_SYSTEM_DB_PORT=5432
PRICE_SYSTEM_DB_NAME=price_system
PRICE_SYSTEM_DB_USER=price_app
PRICE_SYSTEM_DB_PASSWORD=your_password_here
```

`.env` やパスワードは Git 管理しない。

最初の確認コマンド:

```powershell
cd C:\price_system\scripts
python test_db_connection.py
python price_check_from_db.py --limit 1 --summary --use-stats --worker-id worker-pc-test
```

少件数 worker テスト例:

```powershell
python amazon_check_worker_loop.py --worker-id PC2-worker1 --limit 5 --sleep 10 --once
```

補助スクリプト:

```powershell
cd C:\price_system\scripts
.\setup_worker_pc.ps1
```

`setup_worker_pc.ps1` は実行コマンド例を表示する補助スクリプトで、依存導入や `.env` 設定の流れを確認しやすくする。
## Worker Metrics

Amazon check worker の実行状況確認では、以下を使います。

```powershell
cd C:\price_system\scripts
py price_check_from_db.py --limit 20 --summary --use-stats --worker-id metrics-test
py amazon_check_worker_loop.py --worker-id PC1-worker1 --limit 20 --sleep 10 --max-loops 2
```

`price_check_from_db.py --summary --use-stats` は、人間向けサマリーに加えて
`WORKER_RUN_SUMMARY key=value ...`
の1行も出力します。  
`amazon_check_worker_loop.py` はその行を拾って、loop 終了時に見やすく再表示します。

### Amazon worker 起動ランチャー

Amazon worker を複数起動しやすくするため、`scripts\` に以下のランチャーを置いている。

- `start_amazon_workers.bat`
  - 常駐起動用
- `start_amazon_workers_once.bat`
  - 1ループ確認用
- `start_amazon_workers.ps1`
  - 本体スクリプト

入力例:

- `1-3`
- `4-6`
- `2`
- `1,3`

動作:

- 入力した worker 番号に応じて `amazon_check_worker_loop.py` を別ウィンドウで起動する
- `start_amazon_workers.bat` は通常起動
- `start_amazon_workers_once.bat` は `--once` 付きで起動
- 前回の入力値は `config/amazon_worker_launcher.ini` に保存される
- `config/amazon_worker_launcher.ini` は実行時生成ファイルのため Git 管理しない

使用例:

```powershell
cd C:\price_system\scripts
.\start_amazon_workers.bat
.\start_amazon_workers_once.bat
```

## QNAP中央DB移行手順

この章は、ローカル PostgreSQL から QNAP 上の PostgreSQL コンテナへ移行する時の運用手順書です。  
ここでは手順整理だけを行い、実DB移行、Docker起動、PostgreSQL設定変更、実行系コマンドの実施はまだ行いません。

前提:

- 現在のローカルDB名は `price_system`
- 中央DBは QNAP 上の PostgreSQL コンテナを想定する
- まずは `price_system_migrate_test` にリストアして確認する
- 問題なければ本番用 `price_system` へ切り替える
- 各PCのツールは `.env` の `PRICE_SYSTEM_DB_*` で QNAP 側DBへ接続する
- DBファイルを NAS 共有フォルダに置いて直接読む方式は採用しない

### 1. 作業前に止めるもの

- Amazon worker
  - `price_check_from_db.py --use-stats`
  - `amazon_check_worker_loop.py`
- 楽天更新 worker
  - `rakuten_inventory_bulk_upsert.py`
  - `rakuten_price_patch.py`
  - `rakuten_daily_update_flow.py`
- CSV更新系
  - `rakuten_csv_price_update_flow.py`
  - `rakuten_csv_winscp_upload_and_watch.py`
  - `apply_rakuten_csv_success_to_db.py`
  - `apply_rakuten_csv_result_to_db.py`
- その他DBを書き換えるスクリプト
  - `calc_store_targets.py`
  - import系
  - 単発の補正スクリプト

### 2. 現ローカルDBのバックアップ

保存先例:

- `C:\price_system\backup\`

ファイル名例:

- `price_system_20260703_103000.dump`

PowerShell での `pg_dump` 例:

```powershell
mkdir C:\price_system\backup -Force

pg_dump `
  -h localhost `
  -p 5432 `
  -U price_app `
  -d price_system `
  -F c `
  -f C:\price_system\backup\price_system_20260703_103000.dump
```

補足:

- 可能なら作業前に全ワーカーを止めた状態でバックアップする
- バックアップファイルはローカルだけでなく別保存先にも退避する

### 3. QNAP PostgreSQLコンテナ作成時に決める値

初期値の基本:

- `POSTGRES_DB=postgres`
- `POSTGRES_USER=price_app`
- `POSTGRES_PASSWORD=強いパスワード`
- `TZ=Asia/Tokyo`

あわせて決めるもの:

- 公開ポート
  - 例: `5432`
- 永続化ボリューム
  - PostgreSQL の data directory を永続化する
- 接続経路
  - LAN
  - または Tailscale

補足:

- テストDBと本番DBはコンテナ初期DBとは別にあとから作る
- DBファイルを NAS 共有フォルダに置いて複数PCから直接読む方式はNG

### 4. QNAP側でテストDBを作る流れ

作成するDB:

- `price_system_migrate_test`
- `price_system`

作成SQL:

```sql
CREATE DATABASE price_system_migrate_test;
CREATE DATABASE price_system;
```

テストDBへの `pg_restore` 例:

```powershell
pg_restore `
  -h <QNAP_HOST> `
  -p 5432 `
  -U price_app `
  -d price_system_migrate_test `
  C:\price_system\backup\price_system_20260703_103000.dump
```

件数確認SQL:

```sql
SELECT COUNT(*) FROM amazon_products;
SELECT COUNT(*) FROM store_products;
SELECT COUNT(*) FROM amazon_check_stats;
SELECT COUNT(*) FROM amazon_check_worker_runs;
```

### 5. Windows PC側からQNAP DBへ接続確認する方法

`psql` での確認:

```powershell
psql `
  -h <QNAP_HOST> `
  -p 5432 `
  -U price_app `
  -d price_system_migrate_test
```

アプリ側の確認:

```powershell
cd C:\price_system\scripts
py test_db_connection.py
py price_check_from_db.py --limit 1 --summary --use-stats --worker-id db-config-test
```

### 6. `.env` の切り替え例

QNAP の LAN IP を使う例:

```dotenv
PRICE_SYSTEM_DB_HOST=192.168.1.10
PRICE_SYSTEM_DB_PORT=5432
PRICE_SYSTEM_DB_NAME=price_system_migrate_test
PRICE_SYSTEM_DB_USER=price_app
PRICE_SYSTEM_DB_PASSWORD=your_shared_password
```

QNAP の Tailscale IP または MagicDNS 名を使う例:

```dotenv
PRICE_SYSTEM_DB_HOST=100.x.y.z
PRICE_SYSTEM_DB_PORT=5432
PRICE_SYSTEM_DB_NAME=price_system_migrate_test
PRICE_SYSTEM_DB_USER=price_app
PRICE_SYSTEM_DB_PASSWORD=your_shared_password
```

または:

```dotenv
PRICE_SYSTEM_DB_HOST=qnap-name.tailnet-name.ts.net
PRICE_SYSTEM_DB_PORT=5432
PRICE_SYSTEM_DB_NAME=price_system_migrate_test
PRICE_SYSTEM_DB_USER=price_app
PRICE_SYSTEM_DB_PASSWORD=your_shared_password
```

本番切替時は `PRICE_SYSTEM_DB_NAME=price_system` に変更する。

### 7. 切替後の確認SQL

```sql
SELECT COUNT(*) FROM amazon_products;
SELECT COUNT(*) FROM store_products;
SELECT COUNT(*) FROM amazon_check_stats WHERE status = 'processing';

SELECT *
FROM amazon_check_worker_runs
ORDER BY id DESC
LIMIT 10;
```

確認ポイント:

- `amazon_products` 件数が移行前と一致する
- `store_products` 件数が移行前と一致する
- `amazon_check_stats` に `processing` が残っていない
- `amazon_check_worker_runs` に新しい実行履歴が残る

### 7.5. 移行完了後チェック

移行直後は、少なくとも以下を確認する。

- `py test_db_connection.py` が通る
- `py price_check_from_db.py --limit 1 --summary --use-stats --worker-id db-config-test` が通る
- `py amazon_check_worker_loop.py --worker-id post-migrate-test --limit 20 --once` が通る
- `amazon_check_stats` に `processing` が残らない
- `amazon_check_worker_runs` に新しい実行履歴が残る
- `system_error_count` や `page_reset_count` が不自然に増えていない

### 8. 複数PCテスト手順

1台で少件数:

```powershell
py price_check_from_db.py --limit 1 --summary --use-stats --worker-id PC1-worker1
```

1台で通常少件数:

```powershell
py price_check_from_db.py --limit 20 --summary --use-stats --worker-id PC1-worker1
```

2台同時テスト:

```powershell
py price_check_from_db.py --limit 20 --summary --use-stats --worker-id PC1-worker1
py price_check_from_db.py --limit 20 --summary --use-stats --worker-id PC2-worker1
```

確認ポイント:

- `processing` が残らない
- `claim` した ASIN が重複しない
- `system_error_count` が不自然に増えない
- `amazon_check_worker_runs` の直近ログが記録される

### 9. バックアップ運用

- 毎日 `pg_dump`
- 14日保持
- 週1回は別保存先へコピー
- 定期的に復元テストを行う

運用例:

- 日次: `price_system_YYYYMMDD_HHMM.dump`
- 世代保持: 14日
- 週次: 別NASまたは別PCへコピー
- 月次: テストDBへ復元確認

QNAP 本番DBをバックアップする補助スクリプト:

```powershell
cd C:\price_system\scripts
.\backup_qnap_db.ps1 -RetentionDays 14
```

保存先:

- `C:\price_system\backup\qnap\`

出力例:

- `price_system_20260703_220000.dump`

### 10. セキュリティ注意

- PostgreSQL の `5432` をインターネットへ公開しない
- 接続は LAN または Tailscale 内だけに限定する
- `.env` は Git 管理しない
- `pg_hba.conf` で接続元を制限する
- 強い `POSTGRES_PASSWORD` を使う
- QNAP 管理用認証情報と DB 認証情報は分ける

### 11. 本番切替の流れ

1. ローカルDBのバックアップを取得する
2. QNAP 側で `price_system_migrate_test` を作成する
3. テストDBへ `pg_restore` する
4. 1台だけ `.env` を切り替えて接続確認する
5. 1台 → 2台で Amazon worker の claim/lock を確認する
6. 問題なければ `.env` の `PRICE_SYSTEM_DB_NAME` を `price_system` に切り替える
7. 本番用 worker を段階的に再開する

### 12. PowerShell補助スクリプト

QNAP への移行作業をしやすくするため、以下の PowerShell 補助スクリプトを `scripts\` に置いている。

- `backup_local_db.ps1`
  - ローカル `price_system` を `pg_dump` する
  - `backup\` 配下へ日時付き `.dump` を保存する
- `restore_to_qnap_test_db.ps1`
  - 指定した `.dump` を QNAP 側の `price_system_migrate_test` へ `pg_restore` する
- `check_qnap_db.ps1`
  - QNAP DB へ `psql` で接続し、件数確認SQLを流す
- `backup_qnap_db.ps1`
  - QNAP 上の本番 `price_system` を `pg_dump` する
  - `backup\qnap\` 配下へ日時付き `.dump` を保存する
  - `-RetentionDays` で古い dump の削除日数を指定できる

パスワードの扱い:

- `.env` に `PRICE_SYSTEM_DB_PASSWORD` があればそれを使う
- 未設定なら PowerShell 実行時に入力を求める
- パスワードをスクリプトに直書きしない

使用例:

```powershell
cd C:\price_system\scripts

.\backup_local_db.ps1

.\restore_to_qnap_test_db.ps1 `
  -DumpPath C:\price_system\backup\price_system_20260703_103000.dump `
  -DbHost 192.168.1.10 `
  -DbPort 5432 `
  -DbUser price_app `
  -TargetDbName price_system_migrate_test

.\check_qnap_db.ps1 `
  -DbHost 192.168.1.10 `
  -DbPort 5432 `
  -DbName price_system_migrate_test `
  -DbUser price_app

.\backup_qnap_db.ps1 `
  -DbHost 192.168.1.10 `
  -DbPort 5432 `
  -DbName price_system `
  -DbUser price_app `
  -RetentionDays 14
```

Tailscale を使う場合の例:

```powershell
.\check_qnap_db.ps1 `
  -DbHost 100.x.y.z `
  -DbPort 5432 `
  -DbName price_system_migrate_test `
  -DbUser price_app
```

または:

```powershell
.\check_qnap_db.ps1 `
  -DbHost qnap-name.tailnet-name.ts.net `
  -DbPort 5432 `
  -DbName price_system_migrate_test `
  -DbUser price_app
```

### 13. タスクスケジューラで日次バックアップを登録する

QNAP 本番DBの日次バックアップは、Windows タスクスケジューラで `backup_qnap_db.ps1` を呼ぶ形にすると運用しやすい。

設定例:

- 実行プログラム
  - `powershell.exe`
- 引数
  - `-ExecutionPolicy Bypass -File "C:\price_system\scripts\backup_qnap_db.ps1" -RetentionDays 14`
- 開始フォルダ
  - `C:\price_system\scripts`
- 推奨実行時刻
  - `03:30`
  - または `04:00`

登録手順の目安:

1. タスクスケジューラを開く
2. 「基本タスクの作成」または「タスクの作成」を選ぶ
3. トリガーを「毎日」にする
4. 開始時刻を `03:30` または `04:00` にする
5. 操作を「プログラムの開始」にする
6. プログラムに `powershell.exe` を指定する
7. 引数に `-ExecutionPolicy Bypass -File "C:\price_system\scripts\backup_qnap_db.ps1" -RetentionDays 14` を入れる
8. 開始フォルダに `C:\price_system\scripts` を入れる

実行後の確認コマンド:

```powershell
Get-ChildItem C:\price_system\backup\qnap
```

復元テスト時の注意:

- 復元先は本番 `price_system` ではなく `price_system_restore_test` を使う
- 本番DBへ直接 `pg_restore` して動作確認しない
## Rakuten Update Worker Launcher

The Rakuten update worker launcher files are available under `scripts\`.

- `start_rakuten_update_worker.bat`
  - starts the execute loop launcher
- `start_rakuten_update_worker_once.bat`
  - starts the execute once launcher
- `start_rakuten_update_worker.ps1`
  - main launcher script

Default values:

- `store = rakuten_1`
- `price-limit = 20`
- `stock-limit = 50`
- `empty-sleep = 60`
- `error-sleep = 300`

Behavior:

- opens a separate PowerShell window for `rakuten_update_worker_loop.py`
- saves the last values to `config/rakuten_worker_launcher.ini`
- writes logs to `logs\rakuten_update_worker\`
- prevents duplicate launch when a live lock file is present

Usage:

```powershell
cd C:\price_system\scripts
.\start_rakuten_update_worker.bat
.\start_rakuten_update_worker_once.bat
```

## Rakuten Price Update Simulator

Use the simulator when you want to measure Rakuten price-update throughput without calling the Rakuten API and without changing `store_products.current_price`, `target_price`, or `target_stock`.

- simulated state is stored in `price_update_sim_state`
- per-loop metrics are stored in `price_update_sim_runs`
- candidate detection compares `target_price` with `simulated_current_price`, not with `store_products.current_price`
- the real Rakuten API is never called

Migration file:

```powershell
docs\migrations\20260706_price_update_simulation.sql
```

Direct CLI examples:

```powershell
cd C:\price_system\scripts
py rakuten_price_update_simulator.py --store rakuten_1 --resolve-only
py rakuten_price_update_simulator.py --store rakuten_1 --start-measurement --measurement-label "initial_7days"
py rakuten_price_update_simulator.py --store rakuten_1 --finish-measurement
py rakuten_price_update_simulator.py --store rakuten_1 --cancel-measurement
py rakuten_price_update_simulator.py --store rakuten_1 --limit 5 --once --fast-test
py rakuten_price_update_simulator.py --store rakuten_1 --limit 5 --once
py rakuten_price_update_simulator.py --store rakuten_1 --limit 20 --empty-sleep 10
```

Key options:

- `--store`
- `--limit`
- `--once`
- `--max-loops`
- `--empty-sleep`
- `--api-interval`
- `--simulated-request-seconds`
- `--resolve-only`
- `--fast-test`
- `--start-measurement`
- `--finish-measurement`
- `--cancel-measurement`
- `--measurement-label`

Defaults:

- `limit = 20`
- `empty_sleep_seconds = 10`
- `api_interval_seconds = 1.5`
- `simulated_request_seconds = 0.2`

Loop summary output includes:

- `backlog_start_count`
- `new_pending_count`
- `retargeted_count`
- `processed_count`
- `backlog_end_count`
- `queue_delta`
- `oldest_pending_seconds`
- `elapsed_seconds`
- `average_seconds_per_item`
- `throughput_per_hour`
- `estimated_drain_seconds`

Launcher files:

- `scripts\start_rakuten_price_update_simulator.ps1`
- `scripts\start_rakuten_price_update_simulator.bat`
- `scripts\start_rakuten_price_update_simulator_once.bat`

Launcher behavior:

- stores local settings in `config\rakuten_price_simulator.ini`
- reuses `Store` and `NodeCode` automatically after first setup
- writes logs to `logs\rakuten_price_update_simulator\`
- uses a separate local lock file and a separate PostgreSQL advisory lock from the real Rakuten update worker

Formal measurement flow:

- use `--start-measurement --measurement-label ...` after the initial full Amazon scan has completed
- the baseline reset aligns `simulated_current_price` to the current `target_price` for the selected store
- use `--finish-measurement` to close the current formal measurement early
- use `--cancel-measurement` to stop the current formal measurement without deleting data
- stopping only the simulator process does not change measurement status; a running measurement can be resumed later
- pre-measurement simulation history is kept, but formal reports can filter by `measurement_id` or `measurement_label`

Measurement report examples:

```powershell
cd C:\price_system\scripts
py report_rakuten_price_simulation.py --store rakuten_1
py report_rakuten_price_simulation.py --store rakuten_1 --measurement-label initial_7days --json
py report_rakuten_price_simulation.py --store rakuten_1 --measurement-id 1 --recent-runs 20
```
