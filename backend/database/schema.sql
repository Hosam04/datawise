-- ────────────────────────────────────────────────────────────
-- DataWise Full Schema (Unified)
-- Combines migration 001 + full schema
-- Safe to run on a fresh database
-- ────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ────────────────────────────────────────────────────────────
-- Helper function: auto-update `updated_at`
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ────────────────────────────────────────────────────────────
-- users
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255),
    picture         TEXT,
    provider        VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- ────────────────────────────────────────────────────────────
-- datasets
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS datasets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- NOTE: NOT using inline UNIQUE here; we use a partial unique index below
    -- so that multiple NULLs are allowed (matches migration 001 behavior).
    session_id          VARCHAR(64),
    name                VARCHAR(255) NOT NULL,
    original_filename   VARCHAR(255) NOT NULL,
    storage_key         TEXT NOT NULL,
    file_size           BIGINT,
    mime_type           VARCHAR(100),
    content_hash        VARCHAR(64),
    schema_hash         VARCHAR(64),
    dataset_fingerprint VARCHAR(64),
    row_count           INTEGER,
    column_count        INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_datasets_user_id ON datasets (user_id);
CREATE INDEX IF NOT EXISTS ix_datasets_session_id ON datasets (session_id);
CREATE INDEX IF NOT EXISTS ix_datasets_user_created ON datasets (user_id, created_at DESC);

-- Partial unique index: uniqueness enforced only when session_id is NOT NULL
-- (multiple NULLs allowed — matches migration 001 semantics)
CREATE UNIQUE INDEX IF NOT EXISTS uq_datasets_session_id
    ON datasets (session_id)
    WHERE session_id IS NOT NULL;

-- Multiple NULLs allowed; uniqueness applies only when fingerprint is set.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_user_fingerprint
    ON datasets (user_id, dataset_fingerprint)
    WHERE dataset_fingerprint IS NOT NULL;

-- ────────────────────────────────────────────────────────────
-- analyses
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analyses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id          UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    user_query          TEXT,
    analysis_type       VARCHAR(50),
    status              VARCHAR(30) NOT NULL DEFAULT 'pending',
    target_column       VARCHAR(255),
    target_detection    JSONB,
    plan_json           JSONB,
    statistics_json     JSONB,
    evidence_json       JSONB,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_analyses_dataset_id ON analyses (dataset_id);
CREATE INDEX IF NOT EXISTS ix_analyses_status ON analyses (status);
CREATE INDEX IF NOT EXISTS ix_analyses_dataset_status ON analyses (dataset_id, status);

-- ────────────────────────────────────────────────────────────
-- dataset_profiles  (1:1 with analyses)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dataset_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id         UUID NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
    row_count           INTEGER,
    column_count        INTEGER,
    target_column       VARCHAR(255),
    target_confidence   DECIMAL(5,4),
    columns_json        JSONB,
    profile_json        JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_dataset_profiles_analysis_id ON dataset_profiles (analysis_id);

-- ────────────────────────────────────────────────────────────
-- cleaning_runs  (1:1 with analyses)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cleaning_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id         UUID NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
    status              VARCHAR(30) NOT NULL DEFAULT 'pending',
    initial_rows        INTEGER,
    final_rows          INTEGER,
    initial_columns     INTEGER,
    final_columns       INTEGER,
    summary_json        JSONB,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_cleaning_runs_analysis_id ON cleaning_runs (analysis_id);

-- ────────────────────────────────────────────────────────────
-- cleaning_actions  (N:1 with cleaning_runs)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cleaning_actions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cleaning_run_id     UUID NOT NULL REFERENCES cleaning_runs(id) ON DELETE CASCADE,
    action_type         VARCHAR(100) NOT NULL,
    column_name         VARCHAR(255),
    reason              TEXT,
    decision            VARCHAR(50),
    status              VARCHAR(50),
    before_json         JSONB,
    after_json          JSONB,
    evidence_json       JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_cleaning_actions_run_id ON cleaning_actions (cleaning_run_id);

-- ────────────────────────────────────────────────────────────
-- ml_results  (1:1 with analyses)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ml_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id         UUID NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    problem_type        VARCHAR(50),
    target_column       VARCHAR(255),
    selected_model      VARCHAR(100),
    fallback_model      VARCHAR(100),
    confidence          DECIMAL(5,4),
    metrics_json        JSONB,
    feature_importance  JSONB,
    model_metadata      JSONB,
    training_time_sec   DOUBLE PRECISION,
    rows_used           INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ml_results_analysis_id ON ml_results (analysis_id);

-- ────────────────────────────────────────────────────────────
-- insights
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS insights (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id         UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    type                VARCHAR(50) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    finding             TEXT,
    interpretation      TEXT,
    evidence_json       JSONB,
    confidence          DECIMAL(5,4),
    importance_score    DECIMAL(5,4),
    is_favorite         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_insights_analysis_id ON insights (analysis_id);
CREATE INDEX IF NOT EXISTS ix_insights_analysis_importance ON insights (analysis_id, importance_score DESC);

-- ────────────────────────────────────────────────────────────
-- visualizations
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS visualizations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id         UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    type                VARCHAR(50) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    config_json         JSONB,
    data_json           JSONB,
    image_storage_key   TEXT,
    sort_order          INTEGER DEFAULT 0,
    is_favorite         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_visualizations_analysis_id ON visualizations (analysis_id);
CREATE INDEX IF NOT EXISTS ix_visualizations_analysis_sort ON visualizations (analysis_id, sort_order);

-- ────────────────────────────────────────────────────────────
-- reports
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Owner so reports survive Clean Datasets (dataset/analysis deletion).
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    -- Nullable + SET NULL so deleting an analysis does not wipe the report.
    analysis_id         UUID REFERENCES analyses(id) ON DELETE SET NULL,
    title               VARCHAR(255) NOT NULL,
    -- Denormalized dataset name for display after analysis is gone.
    dataset_label       VARCHAR(255),
    filename            VARCHAR(255),
    storage_key         TEXT,
    status              VARCHAR(30) NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique index on analysis_id (explicit — clearer than inline UNIQUE)
-- Multiple NULLs are allowed (PostgreSQL unique index semantics).
CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_analysis_id
    ON reports (analysis_id);

CREATE INDEX IF NOT EXISTS ix_reports_analysis_id ON reports (analysis_id);
CREATE INDEX IF NOT EXISTS ix_reports_user_id ON reports (user_id);
CREATE INDEX IF NOT EXISTS ix_reports_status ON reports (status);

-- Migration for existing DBs (run once):
-- ALTER TABLE reports ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
-- ALTER TABLE reports ADD COLUMN IF NOT EXISTS dataset_label VARCHAR(255);
-- ALTER TABLE reports ALTER COLUMN analysis_id DROP NOT NULL;
-- ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_analysis_id_fkey;
-- ALTER TABLE reports ADD CONSTRAINT reports_analysis_id_fkey
--     FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE SET NULL;
-- UPDATE reports r SET user_id = d.user_id, dataset_label = d.original_filename
--   FROM analyses a JOIN datasets d ON d.id = a.dataset_id
--   WHERE r.analysis_id = a.id AND r.user_id IS NULL;

-- ────────────────────────────────────────────────────────────
-- report_visualizations  (M:N junction)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS report_visualizations (
    report_id           UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    visualization_id    UUID NOT NULL REFERENCES visualizations(id) ON DELETE CASCADE,
    sort_order          INTEGER DEFAULT 0,
    PRIMARY KEY (report_id, visualization_id)
);

CREATE INDEX IF NOT EXISTS ix_report_visualizations_report_id
    ON report_visualizations (report_id);
CREATE INDEX IF NOT EXISTS ix_report_visualizations_visualization_id
    ON report_visualizations (visualization_id);

-- ────────────────────────────────────────────────────────────
-- chat_conversations
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dataset_id          UUID REFERENCES datasets(id) ON DELETE SET NULL,
    analysis_id         UUID REFERENCES analyses(id) ON DELETE SET NULL,
    title               VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_conversations_user_id ON chat_conversations (user_id);
CREATE INDEX IF NOT EXISTS ix_chat_conversations_dataset_id ON chat_conversations (dataset_id);
CREATE INDEX IF NOT EXISTS ix_chat_conversations_analysis_id ON chat_conversations (analysis_id);

-- ────────────────────────────────────────────────────────────
-- chat_messages
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    role                VARCHAR(30) NOT NULL,
    content             TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_id ON chat_messages (conversation_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_created ON chat_messages (conversation_id, created_at);

-- ────────────────────────────────────────────────────────────
-- favorites  (user-saved datasets / reports)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS favorites (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id             VARCHAR(64) NOT NULL,
    item_type           VARCHAR(30) NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    dataset_id          UUID REFERENCES datasets(id) ON DELETE SET NULL,
    report_id           UUID REFERENCES reports(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_favorites_user_item UNIQUE (user_id, item_id)
);

CREATE INDEX IF NOT EXISTS ix_favorites_user_id ON favorites (user_id);
CREATE INDEX IF NOT EXISTS ix_favorites_user_type ON favorites (user_id, item_type);

-- ────────────────────────────────────────────────────────────
-- Triggers: auto-update `updated_at`
-- ────────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_datasets_updated_at ON datasets;
CREATE TRIGGER trg_datasets_updated_at
    BEFORE UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_analyses_updated_at ON analyses;
CREATE TRIGGER trg_analyses_updated_at
    BEFORE UPDATE ON analyses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_insights_updated_at ON insights;
CREATE TRIGGER trg_insights_updated_at
    BEFORE UPDATE ON insights
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_visualizations_updated_at ON visualizations;
CREATE TRIGGER trg_visualizations_updated_at
    BEFORE UPDATE ON visualizations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_reports_updated_at ON reports;
CREATE TRIGGER trg_reports_updated_at
    BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_chat_conversations_updated_at ON chat_conversations;
CREATE TRIGGER trg_chat_conversations_updated_at
    BEFORE UPDATE ON chat_conversations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_favorites_updated_at ON favorites;
CREATE TRIGGER trg_favorites_updated_at
    BEFORE UPDATE ON favorites
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();