-- Per-store ASIN prices managed manually by an operator.
-- A configured fixed price suppresses automatic price updates, while the
-- ordinary Amazon check continues to calculate and update target_stock.
CREATE TABLE IF NOT EXISTS asin_fixed_price_settings (
    id BIGSERIAL PRIMARY KEY,
    store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    asin TEXT NOT NULL,
    fixed_price INTEGER NOT NULL CHECK (fixed_price > 0),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (store_id, asin)
);

CREATE INDEX IF NOT EXISTS idx_asin_fixed_price_settings_store_asin
    ON asin_fixed_price_settings (store_id, asin)
    WHERE enabled = TRUE;
