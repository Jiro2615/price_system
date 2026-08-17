CREATE TABLE IF NOT EXISTS rakuten_price_api_retry_state (
    store_product_id BIGINT PRIMARY KEY REFERENCES store_products(id) ON DELETE CASCADE,
    store_code TEXT NOT NULL,
    target_price INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('retry_scheduled', 'permanent_hold')),
    failure_kind TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    last_error TEXT NOT NULL DEFAULT '',
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rakuten_price_api_retry_state_due
    ON rakuten_price_api_retry_state (store_code, state, next_retry_at);
