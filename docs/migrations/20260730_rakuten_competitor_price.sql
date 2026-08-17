-- Rakuten Ichiba competitor-price lookup data.
-- Apply manually. This migration does not modify existing target_price values.

BEGIN;

ALTER TABLE amazon_products
    ADD COLUMN IF NOT EXISTS jan_code VARCHAR(14);

CREATE INDEX IF NOT EXISTS ix_amazon_products_jan_code
    ON amazon_products(jan_code)
    WHERE jan_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS rakuten_competitor_price_snapshots (
    id BIGSERIAL PRIMARY KEY,
    asin VARCHAR(32) NOT NULL REFERENCES amazon_products(asin) ON DELETE CASCADE,
    jan_code VARCHAR(14) NOT NULL,
    item_code TEXT NOT NULL DEFAULT '',
    shop_code TEXT NOT NULL DEFAULT '',
    shop_name TEXT NOT NULL DEFAULT '',
    item_name TEXT NOT NULL DEFAULT '',
    item_price INTEGER NOT NULL CHECK (item_price > 0),
    postage_included BOOLEAN NOT NULL,
    availability BOOLEAN NOT NULL,
    item_url TEXT NOT NULL DEFAULT '',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_rakuten_competitor_price_snapshots_lookup
    ON rakuten_competitor_price_snapshots (asin, fetched_at DESC, item_price)
    WHERE postage_included = TRUE AND availability = TRUE;

COMMIT;
