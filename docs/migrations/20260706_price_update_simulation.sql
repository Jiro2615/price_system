-- Rakuten price update shadow simulation tables
-- Apply to test DB first. Do not apply automatically to production.

BEGIN;

CREATE TABLE IF NOT EXISTS price_update_sim_state (
    store_product_id BIGINT PRIMARY KEY REFERENCES store_products(id) ON DELETE CASCADE,
    store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE RESTRICT,
    simulated_current_price INTEGER,
    pending_target_price INTEGER,
    first_pending_at TIMESTAMPTZ,
    last_target_changed_at TIMESTAMPTZ,
    last_simulated_update_at TIMESTAMPTZ,
    retarget_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_price_update_sim_state_retarget_count
        CHECK (retarget_count >= 0)
);

CREATE INDEX IF NOT EXISTS ix_price_update_sim_state_store_pending
    ON price_update_sim_state (store_id, first_pending_at, store_product_id)
    WHERE pending_target_price IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_price_update_sim_state_store_updated_at
    ON price_update_sim_state (store_id, updated_at);

CREATE TABLE IF NOT EXISTS price_update_sim_runs (
    id BIGSERIAL PRIMARY KEY,
    store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE RESTRICT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    backlog_start_count INTEGER NOT NULL,
    backlog_end_count INTEGER,
    new_pending_count INTEGER NOT NULL DEFAULT 0,
    retargeted_count INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    oldest_pending_seconds_start NUMERIC,
    oldest_pending_seconds_end NUMERIC,
    elapsed_seconds NUMERIC,
    average_seconds_per_item NUMERIC,
    throughput_per_hour NUMERIC,
    estimated_drain_seconds NUMERIC,
    api_interval_seconds NUMERIC NOT NULL,
    simulated_request_seconds NUMERIC NOT NULL,
    result_status TEXT NOT NULL,
    result_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_price_update_sim_runs_counts
        CHECK (
            backlog_start_count >= 0
            AND COALESCE(backlog_end_count, 0) >= 0
            AND new_pending_count >= 0
            AND retargeted_count >= 0
            AND processed_count >= 0
        ),
    CONSTRAINT chk_price_update_sim_runs_seconds
        CHECK (
            COALESCE(oldest_pending_seconds_start, 0) >= 0
            AND COALESCE(oldest_pending_seconds_end, 0) >= 0
            AND COALESCE(elapsed_seconds, 0) >= 0
            AND COALESCE(average_seconds_per_item, 0) >= 0
            AND COALESCE(throughput_per_hour, 0) >= 0
            AND COALESCE(estimated_drain_seconds, 0) >= 0
            AND api_interval_seconds >= 0
            AND simulated_request_seconds >= 0
        )
);

CREATE INDEX IF NOT EXISTS ix_price_update_sim_runs_store_started_at
    ON price_update_sim_runs (store_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_price_update_sim_runs_result_status
    ON price_update_sim_runs (result_status, started_at DESC);

COMMIT;
