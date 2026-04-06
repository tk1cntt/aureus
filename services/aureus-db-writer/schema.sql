-- Enable TimescaleDB extension (usually done in DB init, but good to have)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Strategy Templates Table
CREATE TABLE IF NOT EXISTS aureus_strategy_templates (
    id          SERIAL PRIMARY KEY,
    name        TEXT              NOT NULL UNIQUE,
    description TEXT,
    config      JSONB             NOT NULL,
    min_score   DOUBLE PRECISION  NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

-- Symbol ↔ Strategy Assignment Table
CREATE TABLE IF NOT EXISTS aureus_symbol_strategies (
    id          SERIAL PRIMARY KEY,
    symbol      TEXT              NOT NULL,
    strategy_id INTEGER           NOT NULL REFERENCES aureus_strategy_templates(id) ON DELETE CASCADE,
    is_active   BOOLEAN           NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_symbol_strategies_symbol_active
    ON aureus_symbol_strategies (symbol, is_active);
CREATE INDEX IF NOT EXISTS idx_symbol_strategies_strategy_id
    ON aureus_symbol_strategies (strategy_id);

-- Candles Table
CREATE TABLE IF NOT EXISTS aureus_candles (
    time        TIMESTAMPTZ       NOT NULL,
    symbol      TEXT              NOT NULL,
    timeframe   TEXT              NOT NULL,
    open        DOUBLE PRECISION  NOT NULL,
    high        DOUBLE PRECISION  NOT NULL,
    low         DOUBLE PRECISION  NOT NULL,
    close       DOUBLE PRECISION  NOT NULL,
    volume      DOUBLE PRECISION  NOT NULL,
    UNIQUE (time, symbol, timeframe)
);

-- Convert to Hypertable
SELECT create_hypertable('aureus_candles', 'time', if_not_exists => TRUE);

-- Swing Points Table
CREATE TABLE IF NOT EXISTS aureus_swing_points (
    time        TIMESTAMPTZ       NOT NULL,
    symbol      TEXT              NOT NULL,
    timeframe   TEXT              NOT NULL,
    price       DOUBLE PRECISION  NOT NULL,
    is_high     BOOLEAN           NOT NULL,
    type        TEXT              NOT NULL,
    UNIQUE (time, symbol, timeframe, is_high)
);

-- Convert to Hypertable
-- AI Analysis Table
CREATE TABLE IF NOT EXISTS aureus_ai_analysis (
    time               TIMESTAMPTZ       NOT NULL,
    symbol             TEXT              NOT NULL,
    aci                INTEGER           NOT NULL,
    sentiment          TEXT,
    narrative          TEXT,
    debate_log         JSONB             NOT NULL,
    analysis_type      TEXT              NOT NULL DEFAULT 'PULSE', -- 'PULSE' or 'AUDIT'
    decision           TEXT,             -- 'ACTIVE', 'REDUCED_RISK', 'REJECTED' (for AUDIT)
    key_insight        TEXT,             -- One-sentence summary (for AUDIT)
    trigger_id         TEXT,             -- Link to trace_id or order_id
    prompt_tokens      INTEGER,
    completion_tokens  INTEGER,
    llm_latency_ms     INTEGER,
    total_latency_ms   INTEGER,
    request_payload    TEXT
);


-- Signal Snapshots Table (Core)
CREATE TABLE IF NOT EXISTS aureus_signal_snapshots (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    atr DOUBLE PRECISION,
    ema_21 DOUBLE PRECISION,
    ema_34 DOUBLE PRECISION,
    ema_55 DOUBLE PRECISION,
    ema_89 DOUBLE PRECISION,
    ema_100 DOUBLE PRECISION,
    ema_200 DOUBLE PRECISION,
    vol_sma_20 DOUBLE PRECISION,
    htf_trend TEXT,
    market_regime TEXT,
    session TEXT,
    events JSONB,
    active_obs JSONB,
    swing_label TEXT,
    -- Phase 7 / Backtest fields
    aci INTEGER DEFAULT 0,
    sentiment TEXT DEFAULT 'NEUTRAL',
    narrative TEXT,
    obs_full JSONB,
    swing_points_snapshot JSONB,
    strategy_progress JSONB,
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('aureus_signal_snapshots', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_signal_snapshots_symbol ON aureus_signal_snapshots (symbol, time DESC);

-- Execution Events Table (Aureus ↔ Nautilus bridge)
CREATE TABLE IF NOT EXISTS aureus_execution_events (
    event_time        TIMESTAMPTZ      NOT NULL,
    trace_id          TEXT             NOT NULL,
    symbol            TEXT             NOT NULL,
    status            TEXT             NOT NULL,
    side              TEXT,
    order_type        TEXT,
    quantity          DOUBLE PRECISION,
    fill_price        DOUBLE PRECISION,
    adapter_order_id  TEXT,
    rejection_reason  TEXT,
    execution_mode    TEXT             NOT NULL DEFAULT 'simulated',
    raw_status        TEXT,
    payload           JSONB            NOT NULL,
    created_at        TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (trace_id, status, event_time)
);

SELECT create_hypertable('aureus_execution_events', 'event_time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_execution_events_trace_id ON aureus_execution_events (trace_id);
CREATE INDEX IF NOT EXISTS idx_execution_events_symbol_time ON aureus_execution_events (symbol, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_execution_events_status ON aureus_execution_events (status);

-- Position Snapshots Table
CREATE TABLE IF NOT EXISTS aureus_position_snapshots (
    event_time        TIMESTAMPTZ      NOT NULL,
    symbol            TEXT             NOT NULL,
    position_id       TEXT             NOT NULL,
    side              TEXT             NOT NULL,
    qty               DOUBLE PRECISION NOT NULL,
    avg_entry_price   DOUBLE PRECISION,
    mark_price        DOUBLE PRECISION,
    unrealized_pnl    DOUBLE PRECISION,
    realized_pnl      DOUBLE PRECISION,
    payload           JSONB            NOT NULL,
    UNIQUE (position_id, event_time)
);

SELECT create_hypertable('aureus_position_snapshots', 'event_time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_symbol_time ON aureus_position_snapshots (symbol, event_time DESC);

-- Account Snapshots Table
CREATE TABLE IF NOT EXISTS aureus_account_snapshots (
    event_time        TIMESTAMPTZ      NOT NULL,
    account_id        TEXT             NOT NULL,
    equity            DOUBLE PRECISION,
    balance           DOUBLE PRECISION,
    margin_used       DOUBLE PRECISION,
    margin_free       DOUBLE PRECISION,
    unrealized_pnl    DOUBLE PRECISION,
    realized_pnl      DOUBLE PRECISION,
    payload           JSONB            NOT NULL,
    UNIQUE (account_id, event_time)
);

SELECT create_hypertable('aureus_account_snapshots', 'event_time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_id_time ON aureus_account_snapshots (account_id, event_time DESC);

-- ── BACKTEST ISOLATION TABLES ──

-- Backtest Candles (Isolated from Live)
CREATE TABLE IF NOT EXISTS aureus_backtest_candles (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, symbol, timeframe)
);

SELECT create_hypertable('aureus_backtest_candles', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_backtest_candles_symbol ON aureus_backtest_candles (symbol, timeframe, time DESC);

-- Backtest Snapshots (Isolated from Live)
CREATE TABLE IF NOT EXISTS aureus_backtest_snapshots (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    atr DOUBLE PRECISION,
    ema_21 DOUBLE PRECISION,
    ema_34 DOUBLE PRECISION,
    ema_55 DOUBLE PRECISION,
    ema_89 DOUBLE PRECISION,
    ema_100 DOUBLE PRECISION,
    ema_200 DOUBLE PRECISION,
    vol_sma_20 DOUBLE PRECISION,
    htf_trend TEXT,
    market_regime TEXT,
    session TEXT,
    events JSONB,
    active_obs JSONB,
    swing_label TEXT,
    aci INTEGER DEFAULT 0,
    sentiment TEXT DEFAULT 'NEUTRAL',
    narrative TEXT,
    obs_full JSONB,
    swing_points_snapshot JSONB,
    strategy_progress JSONB,
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('aureus_backtest_snapshots', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_backtest_snapshots_symbol ON aureus_backtest_snapshots (symbol, time DESC);

-- Migration Safety (Ensure columns exist for existing tables)
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS analysis_type TEXT NOT NULL DEFAULT 'PULSE';
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS decision TEXT;
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS key_insight TEXT;
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS trigger_id TEXT;
ALTER TABLE aureus_ai_analysis ALTER COLUMN sentiment DROP NOT NULL;

-- ============================================================================
-- Phase 30: Trade State Management
-- ============================================================================

CREATE TABLE IF NOT EXISTS aureus_trades (
    id                  BIGSERIAL PRIMARY KEY,
    trace_id            TEXT NOT NULL UNIQUE,
    ticket              BIGINT,
    symbol              TEXT NOT NULL,
    magic_number        BIGINT,
    strategy_id         BIGINT,
    strategy_name       TEXT,
    direction           TEXT NOT NULL,
    entry_type          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    entry_price         DOUBLE PRECISION,
    exit_price          DOUBLE PRECISION,
    sl                  DOUBLE PRECISION,
    tp                  DOUBLE PRECISION,
    volume              DOUBLE PRECISION,
    commission          DOUBLE PRECISION DEFAULT 0,
    swap                DOUBLE PRECISION DEFAULT 0,
    profit              DOUBLE PRECISION DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filled_at           TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    payload             JSONB
);

-- Regular indexes (no hypertable needed for trade volume)
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON aureus_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON aureus_trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_magic ON aureus_trades(magic_number);
CREATE INDEX IF NOT EXISTS idx_trades_ticket ON aureus_trades(ticket);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON aureus_trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON aureus_trades(created_at);

-- Compression & Retention (Phase 30)
-- NOTE: add_compression_policy requires columnstore enabled (TimescaleDB >= 2.13)
-- For now, manual compression can be done via:
--   SELECT compress_chunk(show_chunks('aureus_trades', older_than => INTERVAL '30 days'));
-- SELECT add_compression_policy('aureus_trades', compress_after => INTERVAL '30 days');
-- SELECT add_retention_policy('aureus_trades', drop_after => INTERVAL '2 years');

-- Phase 26: Magic number per strategy (migration applied, documented here)
ALTER TABLE aureus_strategy_templates
  ADD COLUMN IF NOT EXISTS magic_number BIGINT;

COMMENT ON COLUMN aureus_strategy_templates.magic_number IS
  'Static MT5 magic number per strategy for order tracking';
ALTER TABLE aureus_ai_analysis ALTER COLUMN narrative DROP NOT NULL;
