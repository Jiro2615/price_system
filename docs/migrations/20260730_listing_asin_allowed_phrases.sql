CREATE TABLE IF NOT EXISTS listing_asin_allowed_phrases (
    id BIGSERIAL PRIMARY KEY,
    store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    asin TEXT NOT NULL,
    forbidden_word TEXT NOT NULL,
    allowed_phrase TEXT NOT NULL,
    keepa_avg90_min NUMERIC(8,2) NOT NULL DEFAULT 3.5,
    note TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (store_id, asin, forbidden_word, allowed_phrase),
    CHECK (keepa_avg90_min >= 3.5)
);
