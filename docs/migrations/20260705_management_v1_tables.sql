-- Management feature v1
-- Design-only migration draft
-- Do not apply automatically

BEGIN;

CREATE TABLE IF NOT EXISTS store_settings (
    store_id BIGINT PRIMARY KEY REFERENCES stores(id) ON DELETE RESTRICT,
    amazon_target_recalc_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    rakuten_inventory_update_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    rakuten_price_update_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    rakuten_blocked_fallback_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    note TEXT,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_store_settings_revision
        CHECK (revision >= 1)
);

CREATE TABLE IF NOT EXISTS worker_nodes (
    id BIGSERIAL PRIMARY KEY,
    node_code TEXT NOT NULL,
    hostname TEXT NOT NULL,
    display_name TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    project_dir TEXT,
    python_command TEXT,
    max_amazon_workers INTEGER,
    log_root TEXT,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_worker_nodes_max_amazon_workers
        CHECK (max_amazon_workers IS NULL OR max_amazon_workers >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_worker_nodes_node_code
    ON worker_nodes(node_code);

CREATE TABLE IF NOT EXISTS worker_configs (
    id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL REFERENCES worker_nodes(id) ON DELETE CASCADE,
    worker_type TEXT NOT NULL,
    store_id BIGINT REFERENCES stores(id) ON DELETE RESTRICT,
    worker_number INTEGER,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    desired_state TEXT NOT NULL DEFAULT 'stopped',
    settings_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_worker_configs_worker_type
        CHECK (worker_type IN ('amazon_check', 'rakuten_update')),
    CONSTRAINT chk_worker_configs_desired_state
        CHECK (desired_state IN ('running', 'stopped')),
    CONSTRAINT chk_worker_configs_settings_json_object
        CHECK (jsonb_typeof(settings_json) = 'object'),
    CONSTRAINT chk_worker_configs_worker_number
        CHECK (worker_number IS NULL OR worker_number >= 1),
    CONSTRAINT chk_worker_configs_revision
        CHECK (revision >= 1),
    CONSTRAINT chk_worker_configs_amazon_shape
        CHECK (
            worker_type <> 'amazon_check'
            OR (worker_number IS NOT NULL AND store_id IS NULL)
        ),
    CONSTRAINT chk_worker_configs_rakuten_shape
        CHECK (
            worker_type <> 'rakuten_update'
            OR (store_id IS NOT NULL AND worker_number IS NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_worker_configs_amazon_node_worker_number
    ON worker_configs (node_id, worker_number)
    WHERE worker_type = 'amazon_check';

CREATE UNIQUE INDEX IF NOT EXISTS uq_worker_configs_rakuten_node_store
    ON worker_configs (node_id, store_id)
    WHERE worker_type = 'rakuten_update';

CREATE INDEX IF NOT EXISTS ix_worker_configs_desired_state
    ON worker_configs (desired_state);

CREATE TABLE IF NOT EXISTS worker_status (
    worker_config_id BIGINT PRIMARY KEY REFERENCES worker_configs(id) ON DELETE CASCADE,
    worker_id TEXT NOT NULL,
    actual_state TEXT NOT NULL DEFAULT 'stopped',
    pid INTEGER,
    started_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    last_finished_at TIMESTAMPTZ,
    last_returncode INTEGER,
    last_success_count INTEGER,
    last_error_count INTEGER,
    last_message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_worker_status_actual_state
        CHECK (actual_state IN ('stopped', 'starting', 'running', 'stopping', 'error')),
    CONSTRAINT chk_worker_status_pid
        CHECK (pid IS NULL OR pid >= 0)
);

CREATE INDEX IF NOT EXISTS ix_worker_status_actual_state
    ON worker_status (actual_state);

CREATE INDEX IF NOT EXISTS ix_worker_status_heartbeat_at
    ON worker_status (heartbeat_at);

-- Deferred table for future management commands:
-- worker_commands
-- Future use cases:
-- - run once
-- - check specific ASIN
-- - force restart
-- - remote operator actions from admin UI

COMMIT;
