CREATE TABLE IF NOT EXISTS aureus_trade_evaluations (
    id BIGSERIAL PRIMARY KEY,
    trade_journal_id BIGINT NOT NULL REFERENCES aureus_trade_journal(id) ON DELETE CASCADE,
    trace_id TEXT NOT NULL,
    ticket BIGINT,
    score_version TEXT NOT NULL,
    score_total DOUBLE PRECISION NOT NULL,
    score_breakdown JSONB NOT NULL,
    weights_snapshot JSONB NOT NULL,
    missing_data_policy TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_trade_eval_trade_version UNIQUE (trade_journal_id, score_version),
    CONSTRAINT chk_trade_eval_breakdown_shape CHECK (
        jsonb_typeof(score_breakdown) = 'object'
        AND jsonb_object_length(score_breakdown) > 0
    ),
    CONSTRAINT chk_trade_eval_weights_shape CHECK (
        jsonb_typeof(weights_snapshot) = 'object'
        AND jsonb_object_length(weights_snapshot) > 0
    )
);

CREATE INDEX idx_trade_eval_symbol_tf_eval_at
    ON aureus_trade_evaluations(symbol, timeframe, evaluated_at DESC);

CREATE INDEX idx_trade_eval_current_symbol_tf_eval_at
    ON aureus_trade_evaluations(symbol, timeframe, evaluated_at DESC)
    WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS aureus_trade_signal_snapshots (
    id BIGSERIAL PRIMARY KEY,
    trade_journal_id BIGINT NOT NULL REFERENCES aureus_trade_journal(id) ON DELETE CASCADE,
    trace_id TEXT NOT NULL,
    ticket BIGINT,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    signal_schema_version TEXT NOT NULL,
    signal_snapshot JSONB NOT NULL,
    cisd_direction TEXT,
    ema21 DOUBLE PRECISION,
    ema55 DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_trade_signal_snapshot_trade_version UNIQUE (trade_journal_id, signal_schema_version),
    CONSTRAINT chk_trade_signal_snapshot_shape CHECK (
        jsonb_typeof(signal_snapshot) = 'object'
        AND jsonb_object_length(signal_snapshot) > 0
    )
);

CREATE INDEX idx_trade_signal_snapshot_symbol_tf_created_at
    ON aureus_trade_signal_snapshots(symbol, timeframe, created_at DESC);

CREATE INDEX idx_trade_signal_snapshot_symbol_tf_cisd_created_at
    ON aureus_trade_signal_snapshots(symbol, timeframe, cisd_direction, created_at DESC);

CREATE INDEX idx_trade_signal_snapshot_created_at_brin
    ON aureus_trade_signal_snapshots USING BRIN(created_at);
