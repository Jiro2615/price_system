# Rakuten Listing Standard Operation

Detailed developer and operations notes are maintained in
`docs/rakuten_listing_developer_guide.md`.

## Image Count

Default listing image upload count is 1 image per item.

- Default source: `scripts/listing/store_config.py`
- Setting name: `LISTING_IMAGE_LIMIT`
- Store-specific override: `RAKUTEN_1_LISTING_IMAGE_LIMIT`
- Global listing override: `RAKUTEN_LISTING_LISTING_IMAGE_LIMIT`

If the setting is omitted, the listing flow uses `1`.
Set a positive integer to upload more images for future pilot runs.

The limit is applied when building `image_download_plan`; real execute, mock execute, readiness, and resume guards should use the planned image count instead of a fixed count.

## Standard Pilot Flow

Use this order for normal pilot work:

1. `dry-run` or `offline`
2. `preflight`
3. `mock execute`
4. `real readiness`
5. `real execute plan`
6. guarded `real execute`
7. RMS visual check
8. optional `rakuten_listing_db_sync`

Do not skip directly to real execute. The detailed commands and troubleshooting
notes are in `docs/rakuten_listing_developer_guide.md`.

## After Successful Real Execute

If the item is confirmed in RMS, DB sync can store the result into:

- `amazon_products`
- `store_products`
- `rakuten_api_snapshots`

Run DB sync in preview mode first, then add `--execute` only when the preview is correct.
