-- Rakuten price update shadow simulation measurements
-- Apply to test DB first. Do not apply automatically to production.

BEGIN;

CREATE TABLE IF NOT EXISTS price_update_sim_measurements (
    id BIGSERIAL PRIMARY KEY,
    store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE RESTRICT,
    measurement_label TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    baseline_product_count INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_price_update_sim_measurements_status
        CHECK (status IN ('running', 'finished', 'cancelled')),
    CONSTRAINT chk_price_update_sim_measurements_baseline_product_count
        CHECK (baseline_product_count >= 0)
);

CREATE INDEX IF NOT EXISTS ix_price_update_sim_measurements_store_started_at
    ON price_update_sim_measurements (store_id, started_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_price_update_sim_measurements_store_label
    ON price_update_sim_measurements (store_id, measurement_label);

CREATE UNIQUE INDEX IF NOT EXISTS uq_price_update_sim_measurements_store_running
    ON price_update_sim_measurements (store_id)
    WHERE status = 'running';

ALTER TABLE price_update_sim_runs
    ADD COLUMN IF NOT EXISTS measurement_id BIGINT REFERENCES price_update_sim_measurements(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_price_update_sim_runs_measurement_id_started_at
    ON price_update_sim_runs (measurement_id, started_at DESC);

COMMIT;
