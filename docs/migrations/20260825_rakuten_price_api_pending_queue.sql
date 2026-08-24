CREATE TABLE IF NOT EXISTS rakuten_price_api_pending_state (
    store_product_id BIGINT PRIMARY KEY REFERENCES store_products(id) ON DELETE CASCADE,
    store_code TEXT NOT NULL,
    target_price INTEGER NOT NULL,
    pending_since TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rakuten_price_api_pending_state_order
    ON rakuten_price_api_pending_state (store_code, pending_since, store_product_id);
