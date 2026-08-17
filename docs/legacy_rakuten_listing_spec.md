
# Legacy Rakuten Listing Spec Notes

This file is an early reverse-engineering note for the legacy workbook and
legacy master files. It is useful for historical context only.

For the current Rakuten listing implementation, use
`docs/rakuten_listing_developer_guide.md` as the canonical guide.

Important current differences from this early note:

- The flow now includes dry-run, preflight, mock execute, real readiness,
  real execute plan, guarded real execute, and DB sync.
- Standard image operation is 1 image per item, controlled by
  `LISTING_IMAGE_LIMIT` / `RAKUTEN_1_LISTING_IMAGE_LIMIT`.
- R-Cabinet destination filenames must not contain ASIN-derived names.
- Item API attributes must use `values: [...]`, not `value`.
- Item API `articleNumber.value` is not populated from ASIN/JAN/EAN in the
  pilot flow; `articleNumber.exemptionReason` is used when required.
- API specifications under `reference/rakuten_api/spec_pages/` are the source
  of truth for current RMS WEB SERVICE behavior.

---

## Original Phase 1 Notes

## Scope
This document records the Phase 1 understanding of the legacy workbook `楽天出品_PWなし.xlsm` and the files under `reference/legacy_listing`.

Phase 1 only builds dry-run JSON for Rakuten item registration and inventory registration. It does not call Rakuten APIs, upload images, update the existing DB, or start any worker process.

## Legacy workbook signals
The workbook VBA could not be fully exported automatically in this phase, but the following procedure and field names were confirmed from `xl/vbaProject.bin` string inspection:

- `RegisterRakutenItem`
- `UpdateRakutenInventory`
- `FetchKeepaASINData`
- `genreIdhenkan`
- `GetShipFromData`
- `managementNumber`
- `normalDeliveryDateId`
- `backOrderDeliveryDateId`
- `normalDeliveryTimeId`
- `backOrderDeliveryTimeId`
- `shipFromIds`
- `standardPrice`
- `inventoryDisplay`
- `attributes`
- `customizationOptions`
- `variants`

## Confirmed payload skeleton
### Item payload
Legacy strings indicate the item payload includes at least:

- `itemNumber`
- `title`
- `itemType = NORMAL`
- `genreId`
- `productDescription.pc`
- `productDescription.sp`
- `payment.taxRate = 0.1`
- `features.inventoryDisplay = DISPLAY_ABSOLUTE_STOCK_COUNT`
- `images[].type = CABINET`
- `images[].location = /{managementNumber}_1.jpg`
- `customizationOptions`
- `variants[{managementNumber}]`

Variant fields confirmed from VBA strings:

- `standardPrice`
- `normalDeliveryDateId`
- `backOrderDeliveryDateId`
- `shipping.postageIncluded = true`
- `articleNumber`
- `attributes`

### Inventory payload
Legacy strings indicate the inventory payload includes at least:

- `mode = ABSOLUTE`
- `quantity`
- `operationLeadTime.normalDeliveryTimeId`
- `operationLeadTime.backOrderDeliveryTimeId`
- `shipFromIds`

## Confirmed customization option texts
Recovered from workbook binary with CP932 decoding:

1. `【ストアからのお知らせ】をご確認頂き、在庫確保ができない場合、キャンセルをさせて頂く場合がございますが、ご了承いただけますでしょうか？`
2. `【Amazon倉庫から届くことについてご了承いただけますでしょうか？】弊社では一日でも早くお客様に商品をお届けする為、Amazonマルチチャネル(配送代行サービス)と提携しております。その際お荷物にAmazonのロゴや置き配となる場合がございます。`
3. `【配達時間指定不可】配達時間の指定はできません。置配希望の方はご指定下さい。`

The current payload contains the original Amazon fulfillment acknowledgement plus:

- Required `SINGLE_SELECTION` delivery preference: `宅配ボックス`, `置き配OK`, or `置き配NG`.
- Required `MULTIPLE_SELECTION` acknowledgement that the requested delivery method is not guaranteed and may be changed by the delivery driver.

## Master file formats
### `blacklist.txt`
- One ASIN per line.
- Exact match.

### `kakoNG_rakuten.txt`
- Tab-separated.
- Column 1: ASIN.
- Column 2: NG reason.

### `replacelist_rakuten.txt`
- Tab-separated.
- Column 1: source text.
- Column 2: replacement text.
- If column 2 is empty, the source text is removed.

### `kinsiword_rakuten.txt` / `kinsiword_other.txt`
- One prohibited word per line.
- Partial substring match against title and description.

### `shuppinlist_rakuten.txt`
- Tab-separated.
- Column 1: ASIN.
- Column 2: existing Rakuten management number.

### `catlist_rakuten.txt`
- Tab-separated.
- Column 1: Keepa leaf category ID.
- Column 2: Rakuten genre ID.

### `属性定義書.txt`
- Tab-separated.
- Column 1: Rakuten genre ID.
- Column 2: Rakuten category path.
- Column 3 onward: required attribute names.

## Legacy "-" fallback precedent
An old real Rakuten item JSON example named `items_get_20251111221917_187.json`
used `manageNumber=20251111221917_187` and `genreId=210724`, and showed the
same attribute names populated with `"-"` values.

This is only a legacy fallback precedent.

- It was a real registered item.
- Its genre was `210724`, not `111120`.
- It does not guarantee that every current Rakuten API registration for
  `genreId=111120` will accept `"-"`.
- For Phase D we use it only as evidence for a cautious legacy fallback path.
- Any production use should first be confirmed by dry-run payload review and
  then by one pilot item before wider rollout.

## Management number notes
Legacy VBA appears to use `yyyymmddhhmmss_187`.

Phase 1 keeps this as a documented legacy candidate, but the dry-run selected value uses a collision-safe suffix:

- Legacy candidate: `yyyymmddhhmmss_187`
- Dry-run candidate: `yyyymmddhhmmss_187_ab12`

This avoids collisions when multiple registrations are prepared within the same second.

## Price calculation note
The exact legacy `raku金額調整` implementation was not fully extracted in this phase. Phase 1 uses current store fee/profit settings from DB and environment overrides, and isolates the calculation in `calc_listing_price()` for later parity tuning.

## Current gaps for next phase
- Full VBA module export for exact parity review.
- Legacy `raku金額調整` formula verification.
- Legacy `GetShipFromData` lookup parity.
- Attribute generation for more Rakuten genres beyond the basic mappings used in Phase 1.
- Real image download and upload flow.
- Real Rakuten API PUT flow.

## Phase D image planning note
Phase D keeps image handling at the planning level only.

- Main image uses `image_urls[0]`.
- Sub images use `image_urls[1:]` in order.
- Filenames are planned from the ASIN only at this stage.
- Example: `B0CJR955SM_main.jpg`, `B0CJR955SM_01.jpg`, `B0CJR955SM_02.jpg`.
- Planned relative paths use `images/<ASIN>/<filename>`.
- `image_download_plan` is diagnostic JSON only in this phase.
- No HTTP fetch, local file write, image validation, or upload is performed here.
- Amazon image fallback is not part of this phase.
- Amazon or Keepa image URLs are not inserted into the Rakuten item payload at this stage.
