# Legacy Comparison Input Spec

`legacy comparison` 用の offline 入力は、次のディレクトリ構造に統一する。

```text
input/legacy_comparison/<ASIN>/amazon_result.json
input/legacy_comparison/<ASIN>/keepa_result.json
input/legacy_comparison/<ASIN>/metadata.json
```

`metadata.json` は任意だが、次のような UTF-8 / BOM なし JSON を推奨する。

```json
{
  "asin": "B0CN39X1FC",
  "source": "legacy_system_saved_result",
  "captured_at": null,
  "notes": null
}
```

## amazon_result.json

`AmazonCheckResult` へ変換できる正規化済み JSON を保存する。

必須項目:

- `requested_asin`

主な項目:

- `page_asin`
- `title`
- `amazon_price`
- `available_qty`
- `gift_available`
- `shipping_status`
- `business_ng`
- `system_error`
- `ng_reason`
- `current_url`

## keepa_result.json

`KeepaProductData` へ変換できる正規化済み JSON を保存する。

必須項目:

- `asin`

主な項目:

- `title`
- `brand`
- `manufacturer`
- `model`
- `part_number`
- `ean`
- `images_csv`
- `image_urls`
- `image_source`
- `category_id`
- `features`
- `description`
- `style`
- `size`
- `color`
- `current_new_offer_count`
- `avg90_new_offer_count`
- `avg90_seller_count`
- `total_offer_count`
- `offer_count_fba`
- `offer_count_fbm`
- `hazardous_materials`
- `is_heat_sensitive`
- `scent`
- `is_adult`
- `is_adult_source`
- `raw_summary`

## ASIN 一致確認

offline 評価前に次を確認する。

- `amazon_result.json.requested_asin == 引数 ASIN`
- `amazon_result.json.page_asin` が空でなければ `== 引数 ASIN`
- `keepa_result.json.asin == 引数 ASIN`

不一致なら `invalid` として扱い、外部取得へフォールバックしない。

## 不足フィールドの扱い

- `amazon_result.json` / `keepa_result.json` が欠落していれば `missing`
- JSON 構文不正、dataclass 変換失敗、ASIN 不一致は `invalid`
- `raw` レスポンスをそのまま置くのではなく、`AmazonCheckResult` / `KeepaProductData` に合わせた正規化済み結果を保存する

## raw レスポンスとの違い

- `raw` は API / 取得元そのままの構造
- offline 入力は新システムが直接再利用できる正規化済み構造
- 参考として `output/listing/B0CN39X1FC_dry_run.json` の `amazon_result` / `keepa_result` を流用できる

## 秘密情報

次は保存しない。

- Authorization
- Cookie
- Keepa API key
- その他の secret / token / password 類

元ファイルは変更せず、必要なら dry-run JSON から `amazon_result` と `keepa_result` だけを抽出して保存する。
