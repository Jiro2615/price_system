-- Track the first time each Rakuten SKU reaches zero RMS stock.
-- Existing zero-stock rows begin tracking when this migration is applied;
-- the prior transition time was not stored historically.

ALTER TABLE store_products
    ADD COLUMN IF NOT EXISTS stock_zero_since TIMESTAMPTZ;

UPDATE store_products
SET stock_zero_since = CURRENT_TIMESTAMP
WHERE current_stock = 0
  AND stock_zero_since IS NULL;

CREATE OR REPLACE FUNCTION track_store_product_stock_zero_since()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.current_stock = 0 THEN
        IF TG_OP = 'UPDATE'
           AND OLD.current_stock = 0
           AND OLD.stock_zero_since IS NOT NULL THEN
            NEW.stock_zero_since := OLD.stock_zero_since;
        ELSIF NEW.stock_zero_since IS NULL THEN
            NEW.stock_zero_since := CURRENT_TIMESTAMP;
        END IF;
    ELSE
        NEW.stock_zero_since := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_store_product_stock_zero_since ON store_products;

CREATE TRIGGER trg_store_product_stock_zero_since
BEFORE INSERT OR UPDATE OF current_stock ON store_products
FOR EACH ROW EXECUTE FUNCTION track_store_product_stock_zero_since();

CREATE INDEX IF NOT EXISTS ix_store_products_stock_zero_since
ON store_products (store_id, stock_zero_since)
WHERE current_stock = 0;
