-- Run only with approval. Restore only missing genre IDs from the latest
-- successful saved listing for the exact store and management number.
-- No price, stock, enabled state, or remote RMS data is changed.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
WITH latest AS (
    SELECT DISTINCT ON (store_id, mall_item_code)
           store_id, mall_item_code, response_json
    FROM rakuten_api_snapshots
    WHERE api_name = 'listing.real_execute'
    ORDER BY store_id, mall_item_code, fetched_at DESC, id DESC
), confirmed AS (
    SELECT store_id, mall_item_code,
           CASE WHEN response_json->'executed_item_payload'->>'genreId' ~ '^[1-9][0-9]{0,8}$'
                THEN (response_json->'executed_item_payload'->>'genreId')::bigint END AS genre_id
    FROM latest
    WHERE response_json->>'final_status' = 'completed'
      AND response_json->>'item_success' = 'true'
      AND response_json->>'inventory_success' = 'true'
)
UPDATE store_products sp
SET rakuten_genre_id = c.genre_id
FROM confirmed c
WHERE sp.store_id = c.store_id
  AND sp.mall_item_code = c.mall_item_code
  AND sp.rakuten_genre_id IS NULL
  AND c.genre_id IS NOT NULL;
COMMIT;
