# 楽天新規出品フロー 開発・運用ガイド

このドキュメントは `C:\price_system_listing` の楽天新規出品フローを、次の人が迷わず追えるようにまとめた開発・運用ガイドです。

`C:\price_system` は既存のAmazon巡回・価格更新系の本体です。楽天新規出品フローの開発・検証・実行は、原則としてこの `C:\price_system_listing` worktree 内で完結させます。

## 1. 安全ルール

- 作業場所は `C:\price_system_listing`。
- `C:\price_system` は参照のみ。コード、DB、worker、ファイルを書き換えない。
- `--execute`、楽天API送信、画像download/upload、CSV upload、DB write、worker起動は、明示的な許可があるときだけ実行する。
- 通常の確認は `offline`、`dry-run`、`preflight`、`mock execute`、`real readiness`、`plan-only` までで止める。
- 秘密情報は `.env` または環境変数から読む。コードやJSONにAPIキー、Authorization、Cookieを出さない。
- 長い一括テストはCodex側で勝手に回さない。必要な場合はPowerShellに貼れるコマンドを提示してユーザー側で実行する。
- 実API許可がある場合でも、実行前に `ready_for_real_execute=true`、`blocking_reasons=[]`、対象ASIN・management number・store一致を確認する。

## 2. 全体フロー

楽天新規出品は、次の段階で進めます。

1. `offline` / `dry-run`
   - 商品判定、属性解決、payload作成、画像計画作成まで。
   - `offline` は保存済みJSONだけを使い、DB/Amazon/Keepaへ接続しません。
   - `dry-run` はDB SELECT、Amazon単品確認、Keepa取得などの読み取りを許可するモードです。DB writeや楽天API送信はしません。
2. `preflight`
   - dry-run JSONから、実行前に不足している人間確認事項やpayload整合性を確認します。
3. `mock execute`
   - 外部通信なしで、画像、item upsert、inventory upsertの流れをモック実行します。
4. `real readiness`
   - API仕様、認証設定、duplicate guard、mock結果をまとめて、本番実行できる状態か判定します。
5. `real execute plan`
   - 実APIは呼ばず、送信予定の画像XML、item payload、inventory payload、実行順序を確認します。
6. `real execute`
   - 明示的な全confirmと `--allow-live-transport` が揃ったときだけ実APIを呼びます。
7. `DB sync`
   - 実登録成功後、`amazon_products`、`store_products`、`rakuten_api_snapshots` へ保存します。`--execute` がなければpreviewのみです。

## 3. ディレクトリ構成

| パス | 役割 |
| --- | --- |
| `scripts/` | CLI入口。PowerShellから実行するコマンド群。 |
| `scripts/listing/` | 楽天出品フロー本体。判定、payload、API transport、DB syncなど。 |
| `reference/legacy_listing/` | 旧システム由来のマスター。カテゴリ、禁止語、出品済み一覧、属性定義など。 |
| `reference/rakuten_api/spec_pages/` | RMS WEB SERVICEから取得したAPI仕様ページ。API仕様の正本。 |
| `reference/rakuten_api/rakuten_listing_api_spec.json` | 実装側で使うAPI仕様サマリー。迷ったら `spec_pages` を優先。 |
| `tests/fixtures/` | offline / mock用の最小fixture。実Keepa rawや秘密情報は入れない。 |
| `output/listing/` | dry-run、preflight、mock、readiness、real execute結果。Git追加しない運用。 |
| `output/listing/execution_history/` | 実行履歴。二重実行防止のための状態ファイル。 |
| `output/keepa_inspect/` | Keepa raw調査・field report・mapping report。 |
| `docs/` | 設計、運用、調査メモ。 |

## 4. API仕様の正本

楽天API仕様は `reference/rakuten_api/spec_pages/` を正本として扱います。

重要な参照先:

| API | 仕様ファイル |
| --- | --- |
| Item API 2.0 `items.upsert` | `reference/rakuten_api/spec_pages/01_商品API_2.0（ItemAPI_2.0）/03_items.upsert.md` |
| Item API 2.0 `items.get` | `reference/rakuten_api/spec_pages/01_商品API_2.0（ItemAPI_2.0）/02_items.get.md` |
| Item API 2.0 `items.bulk.get` | `reference/rakuten_api/spec_pages/01_商品API_2.0（ItemAPI_2.0）/09_items.bulk.get.md` |
| Inventory API 2.1 `inventories.variants.upsert` | `reference/rakuten_api/spec_pages/03_在庫API_2.1（InventoryAPI_2.1）/02_inventories.variants.upsert.md` |
| R-Cabinet `cabinet.file.insert` | `reference/rakuten_api/spec_pages/07_R-CabinetAPI（CabinetAPI）/08_cabinet.file.insert.md` |
| Navigation API `genres.attributes.get` | `reference/rakuten_api/spec_pages/05_ジャンル・商品属性情報検索API/03_genres.attributes.get.md` |
| Category API | `reference/rakuten_api/spec_pages/02_カテゴリAPI_2.0（CategoryAPI_2.0）/` |

判断ルール:

- 実装と `rakuten_listing_api_spec.json` と `spec_pages` が食い違う場合、`spec_pages` を優先します。
- RMS画面の挙動と仕様が食い違う場合、実APIレスポンスとRMS画面の実測結果を `docs/` または `output/listing/` に残してから修正します。
- APIエラーを受けた場合は、まず `propertyPath` と送信payloadを確認し、該当APIの `.md` を見ます。

## 5. 旧マスターと役割

| ファイル | 役割 |
| --- | --- |
| `reference/legacy_listing/catlist_rakuten.txt` | Keepa category_id から楽天 genreId への対応。カテゴリ不明時の最初の確認先。 |
| `reference/legacy_listing/属性定義書.txt` | genreIdごとの必須属性・属性仕様の旧定義。 |
| `reference/legacy_listing/shuppinlist_rakuten.txt` | 旧出品済み一覧。既出品なら外部アクセス前に `already_listed` で止める。 |
| `reference/legacy_listing/blacklist.txt` | 出品除外ASINなど。 |
| `reference/legacy_listing/kakoNG_rakuten.txt` | 過去NG。 |
| `reference/legacy_listing/kinsiword_rakuten.txt` | 禁止語。 |
| `reference/legacy_listing/replacelist_rakuten.txt` | 旧システムの置換ルール。禁止語回避目的と通常整形を混同しない。 |
| `reference/legacy_listing/allowed_phrases_rakuten.json` | 新方式の禁止語許可フレーズ。商品文字列は変更せず、判定用コピーだけマスクする。 |
| `reference/legacy_listing/警告ありメーカ.txt` | メーカー警告マスター。 |

`kinsiword_other.txt` は欠落している環境があります。`--allow-missing-master` の場合はwarningとして継続する仕様です。

## 6. 主要CLI

### 6.1 dry-run / offline

入口: `scripts/rakuten_listing_prepare.py`

主な引数:

- `--asin`
- `--store`
- `--dry-run`
- `--offline`
- `--store-settings-json`
- `--amazon-result-json`
- `--keepa-result-json`
- `--master-dir`
- `--allow-missing-master`
- `--management-number`
- `--output-json`

`offline` ではDB、Amazon、Keepaへ接続しません。保存済みJSONからpayload生成まで進めます。

PowerShell例:

```powershell
cd C:\price_system_listing

py -u -m scripts.rakuten_listing_prepare `
  --asin B00HLBPOBQ `
  --store rakuten_1 `
  --dry-run `
  --master-dir reference\legacy_listing `
  --allow-missing-master `
  --output-json output\listing\B00HLBPOBQ_dry_run.json
```

### 6.2 preflight

入口: `scripts/rakuten_listing_preflight.py`

```powershell
py -u -m scripts.rakuten_listing_preflight `
  --input-json output\listing\B00HLBPOBQ_dry_run.json `
  --asin B00HLBPOBQ `
  --store rakuten_1 `
  --management-number 20260713214407_187_dab3 `
  --output-json output\listing\B00HLBPOBQ_preflight.json
```

### 6.3 mock execute

入口: `scripts/rakuten_listing_mock_execute.py`

外部通信なしで、実行順序とpayload受け渡しを確認します。

```powershell
py -u -m scripts.rakuten_listing_mock_execute `
  --dry-run-json output\listing\B00HLBPOBQ_dry_run.json `
  --preflight-json output\listing\B00HLBPOBQ_preflight.json `
  --asin B00HLBPOBQ `
  --management-number 20260713214407_187_dab3 `
  --approved `
  --output-json output\listing\B00HLBPOBQ_mock_execute.json
```

failure injection:

- `--fail-step image-download`
- `--fail-step image-validation`
- `--fail-step image-upload`
- `--fail-step item`
- `--fail-step inventory`

### 6.4 real readiness

入口: `scripts/rakuten_listing_real_readiness.py`

```powershell
py -u -m scripts.rakuten_listing_real_readiness `
  --dry-run-json output\listing\B00HLBPOBQ_dry_run.json `
  --preflight-json output\listing\B00HLBPOBQ_preflight.json `
  --mock-result-json output\listing\B00HLBPOBQ_mock_execute.json `
  --asin B00HLBPOBQ `
  --management-number 20260713214407_187_dab3 `
  --store rakuten_1 `
  --output-json output\listing\B00HLBPOBQ_real_readiness.json
```

確認ポイント:

- `readiness_status = ready`
- `ready_for_real_execute = true`
- `blocking_reasons = []`
- `secrets_exposed = false`

### 6.5 real execute plan / real execute

入口: `scripts/rakuten_listing_real_execute.py`

`--execute` がなければ外部処理は行いません。`--execute` があっても、次が揃わなければblockedです。

- `--approved`
- `--confirm-real-api`
- `--allow-live-transport`
- `--confirm-asin`
- `--confirm-management-number`
- `--confirm-store`

plan-only例:

```powershell
py -u -m scripts.rakuten_listing_real_execute `
  --plan-only `
  --approved `
  --confirm-real-api `
  --confirm-asin B00HLBPOBQ `
  --confirm-management-number 20260713214407_187_dab3 `
  --confirm-store rakuten_1 `
  --readiness-json output\listing\B00HLBPOBQ_real_readiness.json `
  --dry-run-json output\listing\B00HLBPOBQ_dry_run.json `
  --preflight-json output\listing\B00HLBPOBQ_preflight.json `
  --mock-result-json output\listing\B00HLBPOBQ_mock_execute.json `
  --asin B00HLBPOBQ `
  --management-number 20260713214407_187_dab3 `
  --store rakuten_1 `
  --output-json output\listing\B00HLBPOBQ_real_execute_plan.json
```

実行時の順序:

1. execution_history start write
2. image upload planned images
3. items.upsert
4. inventory upsert
5. execution_history final write

resume:

- `--resume-after-image-upload`
  - 画像upload済み、item未登録、inventory未登録のときにitem upsertから再開する。
- `--resume-after-item-upsert`
  - item登録済み、inventory未登録のときにinventory upsertから再開する。
- `--manual-image-cleanup-completed`
  - RMS上の画像を手動削除済みと明示するためのガード用。

### 6.6 DB sync

入口:

- CLI: `scripts/rakuten_listing_db_sync.py`
- 本体: `scripts/listing/listing_db_sync.py`

実登録成功後、ローカルDBへ同期します。`--execute` がなければpreviewだけです。

```powershell
py -u -m scripts.rakuten_listing_db_sync `
  --result-json output\listing\B00HLBPOBQ_real_execute_result.json `
  --output-json output\listing\B00HLBPOBQ_db_sync_preview.json
```

DB write実行:

```powershell
py -u -m scripts.rakuten_listing_db_sync `
  --execute `
  --result-json output\listing\B00HLBPOBQ_real_execute_result.json `
  --output-json output\listing\B00HLBPOBQ_db_sync_result.json
```

## 7. 主要モジュール

| ファイル | 役割 |
| --- | --- |
| `scripts/listing/models.py` | `AmazonCheckResult`、`KeepaProductData`、`StoreSettings` などのデータ構造。JSON化ヘルパもここ。 |
| `scripts/listing/store_config.py` | 店舗設定読み込み。DB/環境変数/fixtureを扱う。画像数の標準値はここ。 |
| `scripts/listing/master_loader.py` | 旧マスター読み込み。カテゴリ、禁止語、出品済み、属性定義など。 |
| `scripts/listing/amazon_bridge.py` | listing側のAmazon単品確認ブリッジ。`C:\price_system` を直接importしない。 |
| `scripts/listing/keepa_product_client.py` | Keepa Product API取得・パース。画像、offer count、brand/model fallbackなど。 |
| `scripts/listing/listing_evaluator.py` | 出品可否判定。禁止語、過去NG、seller count、必須属性など。 |
| `scripts/listing/common_settings.py` | 全店舗共通設定。`min_avg90_new_offer_count = 3.5` など。 |
| `scripts/listing/attribute_resolver.py` | 楽天属性候補の解決。source/raw_path/evidence/confidenceを保持する。 |
| `scripts/listing/attribute_policy.py` | genre別の属性方針。代表カラーや暫定ジャンル固有ルールをここで閉じる。 |
| `scripts/listing/provisional_genre.py` | category不明時の仮genre候補。間違っても止めにくい近似ジャンルを出す。 |
| `scripts/listing/prohibited_word_masking.py` | 許可フレーズ方式の禁止語判定。元テキストは変更しない。 |
| `scripts/listing/text_sanitizer.py` | Item API用テキストの機種依存文字対策。 |
| `scripts/listing/rakuten_payload_builder.py` | item/inventory payloadの組み立て。 |
| `scripts/listing/image_plan.py` | 画像download/upload計画。標準は1枚。 |
| `scripts/listing/image_downloader.py` | 画像download処理。実行時のみ呼ぶ。 |
| `scripts/listing/image_validator.py` | 画像validation。mockでは実ファイルを見ない構成も可能。 |
| `scripts/listing/rakuten_image_client.py` | R-Cabinet XML/multipart request生成と送信。 |
| `scripts/listing/rakuten_item_client.py` | Item API request生成と送信。send payload sanitizationの最終防衛線。 |
| `scripts/listing/rakuten_inventory_client.py` | Inventory API request生成と送信。 |
| `scripts/listing/rakuten_transport.py` | requests transport、認証ヘッダ、HTTP呼び出し。 |
| `scripts/listing/preflight_service.py` | preflight report生成。 |
| `scripts/listing/mock_execute_service.py` | mock execute report生成。 |
| `scripts/listing/real_readiness_service.py` | 実行準備チェック。認証、API仕様、duplicate guard。 |
| `scripts/listing/real_execute_plan_service.py` | 実API前のplan JSON生成。 |
| `scripts/listing/real_execute_service.py` | ガード付きreal execute本体。execution_historyも扱う。 |
| `scripts/listing/listing_db_sync.py` | 実登録成功後のDB保存。 |

## 8. Item API payloadルール

Item API 2.0 `items.upsert` の送信payloadは、RMS仕様と実APIエラーを踏まえて次を守ります。

- `variants.<variantId>.attributes[]` は `values` 配列を使う。
- `attributes[].value` は送らない。
- `values` は文字列1個でも配列にする。
- `null`、空文字、空配列の属性は送らない。
- 診断用 `resolved_fields` や `resolved_attributes` に `value` が残るのはよいが、送信payloadには出さない。
- `articleNumber.value` にASIN/JAN/EANを安易に入れない。
- 初回パイロットでは `articleNumber.exemptionReason` を送る。
- `articleNumber.value` は送らない。
- `title`、`productDescription.pc`、`productDescription.sp` など送信テキストは機種依存文字をサニタイズする。

サニタイズ例:

| Before | After |
| --- | --- |
| `№` | `No.` |
| `㎝` | `cm` |
| `㎜` | `mm` |
| `㈱` | `株式会社` |
| `①` - `⑩` | `1` - `10` |

代表的なエラーと対応:

| APIエラー | 原因 | 対応 |
| --- | --- | --- |
| `Unrecognized field "value"` | attributesに `value` を送った | `values: [...]` に変換する。 |
| `articleNumber.value or articleNumber.exemptionReason should be mandatory` | articleNumberを完全omitした | `articleNumber.exemptionReason` を送る。 |
| `Machine dependent characters cannot be registered` | `№` などがtitle/descriptionに含まれる | `text_sanitizer.py` で置換する。 |

## 9. Inventory API payloadルール

Inventory APIはSKU管理番号単位で更新します。

確認ポイント:

- variant / SKU管理番号が item payload の variant key と一致する。
- quantity は `max_stock` やstore設定から決まる。標準dry-runでは `4` のケースが多い。
- delivery関連IDは店舗設定で送る/送らないを切り替えられる。
- 実APIでdelivery関連が原因のエラーになった場合は、item payloadとinventory payloadを分けて確認する。

関連ファイル:

- `scripts/listing/rakuten_inventory_client.py`
- `scripts/listing/rakuten_payload_builder.py`
- `reference/rakuten_api/spec_pages/03_在庫API_2.1（InventoryAPI_2.1）/02_inventories.variants.upsert.md`

## 10. R-Cabinet画像ルール

現在の標準運用は「代表画像1枚」です。

- 設定元: `scripts/listing/store_config.py`
- 標準値: `LISTING_IMAGE_LIMIT = 1`
- 店舗別環境変数: `RAKUTEN_1_LISTING_IMAGE_LIMIT`
- listing共通環境変数: `RAKUTEN_LISTING_LISTING_IMAGE_LIMIT`

R-Cabinet送信ルール:

- `fileName` はdestination file nameを使う。
- `filePath` もdestination file nameを使う。
- `fileName == filePath`。
- `.jpg` を含める。
- XML previewにASIN由来名を出さない。
- local cache側のファイル名にASINが残るのは許容。ただし楽天へ送る値には使わない。

例:

```xml
<request>
  <fileInsertRequest>
    <file>
      <fileName>20260713214407_187_1.jpg</fileName>
      <folderId>13584708</folderId>
      <filePath>20260713214407_187_1.jpg</filePath>
      <overWrite>true</overWrite>
    </file>
  </fileInsertRequest>
</request>
```

item payload側のlocation例:

```text
/r_2025042547/listing_test/20260713214407_187_1.jpg
```

full URL例:

```text
https://image.rakuten.co.jp/ecprime500/cabinet/r_2025042547/listing_test/20260713214407_187_1.jpg
```

## 11. Keepaパース仕様

画像:

1. `products[0].images[].l`
2. 各要素で `l` がなければ `m`
3. `images` 全体で有効画像がない場合のみ `imagesCSV`

出力:

- `image_urls`: 採用画像URL。
- `image_source`: `keepa_images` / `keepa_images_csv` / `none`。
- `images_csv`: Keepa rawの `products[0].imagesCSV` の元値。採用URLは入れない。

offer count:

- `current_new_offer_count = products[0].stats.current[11]`
- `avg90_new_offer_count = products[0].stats.avg90[11]`
- `avg90_seller_count` は互換用。厳密なユニーク出品者数ではなく、Keepa `COUNT_NEW` 相当の互換値として扱う。
- `stats.avg90[12]` は中古オファー数なので新品出品者数には使わない。
- `-1`、配列不足、nullは安全にnull扱い。

その他:

- `isAdultProduct` を優先し、旧fixture互換で `isAdult` も見る。
- brand fallback: `brand`、空なら `manufacturer`。
- model fallback: `model`、空なら `partNumber`。
- hazardousMaterials等は診断レポートへ出すが、現時点でNG条件にはしない。

## 12. 出品可否判定

主な判定:

- 旧出品済みなら `already_listed`。
- blacklist / kakoNGは `business_ng`。
- 禁止語一致は `business_ng`。
- Amazon側が `business_ng` / `system_error` の場合、Keepaへ進まない。
- Keepa通信・API・JSON解析などのシステムエラーは `system_error`。
- Keepa正常応答だが商品情報なしは `missing_required_data`。
- `avg90_new_offer_count < 3.5` は `business_ng`。
- `avg90_new_offer_count = null` は即NGにしない。
- 必須属性不足はpayload生成前に止める。

seller count共通設定:

- 正式名: `min_avg90_new_offer_count`
- 定義: `scripts/listing/common_settings.py`
- 標準値: `3.5`
- 旧名互換: `min_avg90_sellers`、`avg90_seller_count`
- 新旧両方ある場合は新名を優先。

## 13. 禁止語と許可フレーズ

旧システムは `クリア -> ク リア` のように空白挿入で禁止語を避けていました。

新システムでは、商品タイトル・説明・属性・payloadの元文字列は変更しません。禁止語判定専用コピーだけで許可フレーズ範囲をマスクします。

関連ファイル:

- `reference/legacy_listing/allowed_phrases_rakuten.json`
- `docs/allowed_phrase_migration_candidates.md`
- `scripts/listing/prohibited_word_masking.py`

診断:

- `allowed_phrase_matches`
- `matched_forbidden_words`
- `matched_separate_check_phrases`
- `required_separate_checks`
- `legacy_spacing_reviews`

重要ルール:

- 許可フレーズに含まれる禁止語だけ無視する。
- 同じ文中の別の禁止語は検出する。
- 長い許可フレーズを優先する。
- payloadへsentinelや空白挿入済み文字列を出さない。
- 未移行の空白挿入ルールがpayloadへ入りそうな場合、本番executeでは止める。dry-runではwarning。

## 14. 属性解決

属性解決では、payloadへ入れる値だけでなく根拠も保持します。

保持すべき情報:

- `source`
- `raw_path`
- `evidence`
- `confidence`
- `fallback_used`
- `resolution_action`

例:

| 属性 | 方針 |
| --- | --- |
| ブランド名 | `brand` を優先。空なら `manufacturer`。 |
| メーカー型番 | `model` を優先。空なら `partNumber`。EANやASINで代用しない。 |
| 代表カラー | genreごとの方針に従う。ユーザー方針では `-` も許容可能。 |
| シリーズ名 | title/scent/variation等から推定する場合はconfidenceとevidenceを残す。 |
| 原産国／製造国 | `日本製` など明示根拠がある場合のみ自動投入。 |

genre固有ルールは `scripts/listing/attribute_policy.py` に閉じます。他genreへ不用意に波及させないでください。

## 15. 仮ジャンル候補

カテゴリ不明でも止めすぎない方針として、仮genre候補を出せるようにしています。

関連ファイル:

- `scripts/suggest_rakuten_genre_candidates.py`
- `scripts/listing/provisional_genre.py`
- `reference/legacy_listing/catlist_rakuten.txt`
- `reference/rakuten_api/spec_pages/05_ジャンル・商品属性情報検索API/`

方針:

- 正確性より、登録を止めすぎない近似候補を出す。
- confidenceとreasonを必ず残す。
- 仮ジャンルは人間確認対象。
- 間違いが見つかればRMSで編集、またはマスター/ルールへ反映する。

## 16. DB連携

DB接続設定は `scripts/db_config.py` から読みます。

主な環境変数:

- `PRICE_SYSTEM_DB_HOST`
- `PRICE_SYSTEM_DB_PORT`
- `PRICE_SYSTEM_DB_NAME`
- `PRICE_SYSTEM_DB_USER`
- `PRICE_SYSTEM_DB_PASSWORD`
- fallback: `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`、`PGPASSWORD`

DB syncで扱う主なテーブル:

| テーブル | 内容 |
| --- | --- |
| `amazon_products` | ASIN単位の商品情報、Amazon価格、在庫、配送可否、ギフト可否など。 |
| `store_products` | 店舗別の商品管理番号、SKU、価格、在庫、状態、ASIN紐付け。 |
| `rakuten_api_snapshots` | 実行結果やAPI snapshotの保存。 |
| `stores` | 店舗IDとstore_codeの対応。 |

DB syncの挙動:

- `amazon_products`: `asin` でupsert。
- `store_products`: `store_id + mall_item_code` で既存行を探し、あればupdate、なければinsert。
- `rakuten_api_snapshots`: 実行snapshotをinsert。`--no-snapshot` で抑止可能。
- unique constraint追加などのDB構造変更は勝手に行わない。

## 17. 実績メモ

### B0CN39X1FC

- 初回パイロット候補。
- R-Cabinet画像upload、Item API、Inventory APIの実API検証に使用。
- 代表カラーやItem API payload形式の修正起点になった商品。

主な修正:

- R-Cabinet XMLの `fileName` からASIN由来名を除去。
- Item API attributesを `value` から `values[]` へ修正。
- `articleNumber.exemptionReason` を送る方針へ修正。
- 機種依存文字サニタイズを追加。

### B00HLBPOBQ

- 2件目の成功パイロット。
- management number: `20260713214407_187_dab3`
- genreId: `216102`
- title: `トネ(TONE) 首振クイックラチェットめがねレンチ RMFQ-21 二面幅21mm`
- standardPrice: `3480`
- inventory quantity: `4`
- seller count: `avg90_new_offer_count = 26.0`
- 画像1枚運用で実登録成功。
- DB syncも実行済み。

商品説明はAmazon/Keepa由来のfeatures等を `<br />` 連結したPC/SP説明です。

## 18. よくあるトラブル

| 症状 | 見る場所 | 対応 |
| --- | --- | --- |
| コマンドが止まったように見える | まず単発・短い確認に分解 | preflight、mock、readiness、planを1つずつ実行する。 |
| `No module named scripts` | `scripts/rakuten_listing_prepare.py` | 直接実行時だけrepo rootを `sys.path` に入れる設計。通常は `-m` 推奨。 |
| `Unrecognized field "value"` | item payload / `rakuten_item_client.py` | attributesは `values[]`。 |
| `articleNumber...mandatory` | item payload / spec_pages Item API | `articleNumber.exemptionReason` を送る。 |
| `Machine dependent characters` | `text_sanitizer.py` | title/descriptionの機種依存文字を置換。 |
| R-Cabinet 400 | XML preview / `rakuten_image_client.py` | `fileName == filePath`、folderId、filePath、overWriteを確認。 |
| QPSLimit | image upload loop | retryせず停止。upload間は1.5秒wait。 |
| 画像upload済みでitem失敗 | execution_history | `--resume-after-image-upload` を検討。 |
| item成功でinventory失敗 | execution_history | `--resume-after-item-upsert` を検討。 |
| RMS検索で出ない | RMS反映遅延の可能性 | 少し待って再検索。management numberでも確認。 |
| DB syncしたい | `scripts/rakuten_listing_db_sync.py` | まずpreview、問題なければ `--execute`。 |

## 19. 確認コマンド

短い静的確認:

```powershell
cd C:\price_system_listing

git diff --check
```

AST確認例:

```powershell
@'
import ast
from pathlib import Path

paths = [
    Path("scripts/listing/rakuten_item_client.py"),
    Path("scripts/listing/rakuten_image_client.py"),
    Path("scripts/listing/rakuten_inventory_client.py"),
    Path("scripts/listing/real_execute_service.py"),
    Path("scripts/listing/listing_db_sync.py"),
    Path("scripts/rakuten_listing_db_sync.py"),
]

for path in paths:
    ast.parse(path.read_text(encoding="utf-8-sig"))
    print("AST_OK", path)
'@ | py -
```

対象テスト例:

```powershell
py -B -m unittest tests.test_rakuten_api_transport_payloads -v
```

```powershell
py -B -m unittest tests.test_rakuten_listing_payload -v
```

長い全体テストは必要なタイミングでユーザー側実行にします。

## 20. 迷ったときに見る順番

### API payloadで迷った

1. `reference/rakuten_api/spec_pages/` の該当API `.md`
2. 直近の送信payload JSON
3. `scripts/listing/rakuten_item_client.py` / `rakuten_inventory_client.py` / `rakuten_image_client.py`
4. 実APIエラーの `propertyPath`

### 属性で迷った

1. `reference/legacy_listing/属性定義書.txt`
2. `reference/rakuten_api/spec_pages/05_ジャンル・商品属性情報検索API/03_genres.attributes.get.md`
3. `scripts/listing/attribute_policy.py`
4. `scripts/listing/attribute_resolver.py`
5. 旧登録商品のCSV / RMS export

### カテゴリで迷った

1. `reference/legacy_listing/catlist_rakuten.txt`
2. `scripts/suggest_rakuten_genre_candidates.py`
3. `scripts/listing/provisional_genre.py`
4. Navigation API仕様
5. RMSで人間確認

### 禁止語で迷った

1. `reference/legacy_listing/kinsiword_rakuten.txt`
2. `reference/legacy_listing/allowed_phrases_rakuten.json`
3. `scripts/listing/prohibited_word_masking.py`
4. `docs/allowed_phrase_migration_candidates.md`

### 画像で迷った

1. dry-runの `image_download_plan`
2. real execute planのXML preview
3. `scripts/listing/image_plan.py`
4. `scripts/listing/rakuten_image_client.py`
5. R-Cabinet spec `08_cabinet.file.insert.md`

### 二重実行・再開で迷った

1. `output/listing/execution_history/<management_number>.json`
2. real execute result JSON
3. `scripts/listing/real_execute_service.py`
4. `--resume-after-image-upload` / `--resume-after-item-upsert` の条件

### DB保存で迷った

1. real execute result JSON
2. `scripts/rakuten_listing_db_sync.py`
3. `scripts/listing/listing_db_sync.py`
4. `scripts/db_config.py`
5. `amazon_products`、`store_products`、`rakuten_api_snapshots`

## 21. 今後の運用メモ

- 標準画像数は1枚。必要ならstore設定または環境変数で増やす。
- 仮genreは登録を止めないための仕組み。RMS確認後にルールへ反映する。
- 代表カラーは現運用では `-` 許容方針。ただしgenreごとに必要なら見直す。
- 実登録後はRMS目視、必要ならRMSで編集、その結果をルールへ戻す。
- API仕様は `spec_pages` を正とし、実APIで得た差分はこのドキュメントまたは専用docsへ追記する。
- DB syncは実登録成功後の標準後処理候補。まずpreview、次に `--execute`。

