# docs/rakuten_price_system_design.md

## システム概要
このシステムは、Amazonを仕入れ/参照元、楽天を販売先として、価格・在庫・発送可否を管理する。

## 更新ルート

### 1. APIルート
日常運用向け。少量・即時・確実な更新に使う。

#### 価格
`rakuten_price_patch.py`

特徴:
- 1商品ずつ更新
- 1秒1回以下を意識
- 少量更新向き
- CSV属性エラーに巻き込まれにくい

#### 在庫
`rakuten_inventory_bulk_upsert.py`

特徴:
- bulk-upsertで複数SKUをまとめられる
- 在庫更新の主力

### 2. CSVルート
全体価格変更向け。大量更新に使う。

`rakuten_csv_price_update_flow.py`

特徴:
- `normal-item_price_*.csv` を作成
- WinSCPでSFTPアップロード
- `/ritem/batch` 監視
- `/ritem/logs` 監視
- 成功時DB反映
- エラー時、成功分反映 + エラー商品blocked化

## CSVエラーへの考え方
CSVでエラーが出ても全件失敗とは限らない。  
楽天の処理結果は「正常 N件、エラー M件」の部分成功になり得る。

そのため、エラーCSVが出た場合:
- エラーログに載った商品 → blocked
- エラーログに載らない商品 → 成功扱い
- blocked商品 → 次回CSV除外
- blocked商品で価格更新が必要 → API更新へ回す

## 価格計算
`calc_store_targets.py` が `price_rules` を使って計算する。

現在の考え方:
- Amazon未チェック / amazon_priceなし → 現状維持
- business_ng → target_stock = 0
- system_error → 現状維持
- Amazon価格OK → target_price計算、target_stock設定

価格計算ロジックを変更した場合、全商品の `target_price` が変わる可能性があるためCSV一括更新を使う。

## メール処理の将来設計
メールは後で重要になる。

### 楽天CSV処理結果メール
用途:
- CSV処理完了検知
- 正常件数 / エラー件数取得
- エラーログ確認へのトリガ

### Amazon発送メール
用途:
- 注文番号
- 配送業者
- 追跡番号
- 発送日時

### 配達ボックス通知メール
用途:
- ボックス番号
- 暗証番号
- 配達完了日時

## 想定テーブル追加
```sql
CREATE TABLE IF NOT EXISTS mail_processing_logs (
    id BIGSERIAL PRIMARY KEY,
    mail_type TEXT NOT NULL,
    subject TEXT,
    from_address TEXT,
    received_at TIMESTAMP,
    parsed_key TEXT,
    parsed_json JSONB,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMP,
    error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shipment_logs (
    id BIGSERIAL PRIMARY KEY,
    order_no TEXT,
    asin TEXT,
    mall_item_code TEXT,
    carrier TEXT,
    tracking_number TEXT,
    delivery_box_no TEXT,
    delivery_box_pin TEXT,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    source_mail_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
