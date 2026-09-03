-- Cache the actual RMS Item API genreId per SKU for product-list searching.
-- This is deliberately distinct from shop display categories (Category API).

ALTER TABLE store_products
    ADD COLUMN IF NOT EXISTS rakuten_genre_id BIGINT;

CREATE INDEX IF NOT EXISTS ix_store_products_rakuten_genre_id
    ON store_products (store_id, rakuten_genre_id)
    WHERE rakuten_genre_id IS NOT NULL;
