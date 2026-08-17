# 楽天新規出品 本番パイロットチェックリスト

このファイルは本番1件パイロット直前の短縮チェックリストです。
詳細仕様、ファイル説明、API仕様の参照先、トラブル対応は
`docs/rakuten_listing_developer_guide.md` を正として扱ってください。

注意: このファイルの旧本文には、初期パイロット `B0CN39X1FC` 時点の記述と
文字化けが残っています。現行運用では下記の「現行チェック」を優先します。

## 現行チェック

### 実行前に揃えるJSON

- dry-run JSON
- preflight JSON
- mock execute JSON
- real readiness JSON
- real execute plan JSON

### dry-run

- `listing_status = eligible`
- `blocking_reasons = []`
- `management_number` が確定している
- `item_payload` が生成されている
- `inventory_payload` が生成されている
- `seller_count_evaluation.passed = true`
- `matched_forbidden_words = []`
- `legacy_spacing_reviews = []`

### Item payload

- `attributes[]` は `values` 配列を使う
- `attributes[].value` は送信payloadに存在しない
- `articleNumber.value` は送らない
- 必要な場合は `articleNumber.exemptionReason` を送る
- title / description に機種依存文字が残っていない

### R-Cabinet

- 標準運用では画像1枚
- `fileName == filePath`
- XML previewにASIN由来名が含まれない
- item `images[].location` がR-Cabinet destinationを指している

### preflight / mock / readiness

- `preflight_status = passed` または許容済み `warning`
- mock `final_status = completed`
- mock `external_actions_performed = false`
- `readiness_status = ready`
- `ready_for_real_execute = true`
- `secrets_exposed = false`

### real executeに必要なconfirm

- `--execute`
- `--approved`
- `--confirm-real-api`
- `--allow-live-transport`
- `--confirm-asin <ASIN>`
- `--confirm-management-number <management_number>`
- `--confirm-store rakuten_1`

### 実行後

- real execute resultの `final_status = completed`
- item upsert成功
- inventory upsert成功
- RMSで商品、画像、価格、在庫、説明文、属性を目視確認
- 必要ならRMSで修正し、ルールへ戻す
- 必要なら `scripts/rakuten_listing_db_sync.py` でDB同期

---

## 旧本文

## Scope

This checklist is for the first real pilot after:

1. `offline round-trip`
2. `preflight`
3. `mock execute`
4. `real readiness`

It does not authorize real execution by itself.

## Required Inputs

- `output/listing/B0CN39X1FC_offline_dry_run.json`
- `output/listing/B0CN39X1FC_preflight.json`
- `output/listing/B0CN39X1FC_mock_execute.json`
- `output/listing/B0CN39X1FC_real_readiness.json`
- `reference/rakuten_api/rakuten_listing_api_spec.json`

## Must Be True Before Real Execute

- `listing_status = eligible`
- `blocking_reasons = []`
- `matched_forbidden_words = []`
- `legacy_spacing_reviews = []`
- `preflight_status = passed` or `warning`
- `ready_for_mock_execute = true`
- `mock final_status = completed`
- `mock_only = true`
- `external_actions_performed = false`
- `management_number` matches across dry-run, preflight, mock result, and final confirmation arguments

## Human Confirmation Items

- Confirm the Rakuten item API endpoint, method, and auth type from RMS documentation.
- Confirm the Rakuten inventory API endpoint, method, and auth type from RMS documentation.
- Confirm the Rakuten image upload API endpoint, auth type, upload destination format, and response URL field.
- Confirm whether `genreId=213661` attribute `代表カラー` accepts direct text values.
- Confirm whether `attributeId` is required.
- Confirm whether `choiceId` is required.
- Confirm pilot cleanup method after the test:
  - delete
  - hide
  - manual RMS rollback
- Confirm duplicate execution guard behavior and history logging path.

## Payload Review

- Title has no legacy spacing artifact like `ク リア`.
- Title contains `クリアブルーラメ`.
- `genreId = 213661`
- `代表カラー = クリアブルーラメ`
- `standardPrice` is positive
- `quantity >= 0`
- `itemNumber = management_number`
- `variantPath.managementNumber = management_number`
- Main/sub image order is correct
- Mock image URLs are not present in the real execute payload plan

## Auth Review

- `RAKUTEN_1_SERVICE_SECRET` is present
- `RAKUTEN_1_LICENSE_KEY` is present
- Any image API auth keys are present if required by the confirmed specification
- No secret values are printed in logs or JSON outputs

## Logging And Cleanup

- Confirm planned history file:
  - `output/listing/execution_history/<management_number>.json`
- Confirm what should mark:
  - `item_registered`
  - `inventory_registered`
  - `images_uploaded`
  - `cleanup_completed`
- Confirm cleanup owner and fallback steps if item registration succeeds but inventory fails

## Real Execute Guard Proposal

Require all of the following:

- `--execute`
- `--approved`
- `--confirm-asin B0CN39X1FC`
- `--confirm-management-number 20260710131514_187_3478`
- `--confirm-store rakuten_1`
- `--confirm-real-api`
- readiness JSON says `ready_for_real_execute = true`

## Current Expected State

At the current phase, `ready_for_real_execute` should stay `false` until:

- API specifications are confirmed
- image API auth is confirmed
- `代表カラー` specification is confirmed
- pilot cleanup is confirmed
