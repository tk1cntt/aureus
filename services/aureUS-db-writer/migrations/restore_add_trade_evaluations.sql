-- Restore evaluation table removed by quick task 260425-duy
-- Based on Phase 55 schema decisions (D-01 to D-08)
-- Evaluation records store per-trade scoring metadata for strategy evaluation

CREATE TABLE IF NOT EXISTS aureus_trade_evaluations (
    id BIGSERIAL PRIMARY KEY,
    trade_journal_id BIGINT NOT NULL REFERENCES aureus_trade_journal(id) ON DELETE CASCADE,
    trace_id TEXT NOT NULL,
    ticket BIGINT,
    score_version TEXT NOT NULL DEFAULT 'scor-v1.0.0',
    score_total DOUBLE PRECISION,
    score_breakdown JSONB NOT NULL DEFAULT '{}',
    weights_snapshot JSONB NOT NULL DEFAULT '{}',
    missing_data_policy TEXT NOT NULL DEFAULT 'impute_neutral_and_flag',
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL DEFAULT 'M1',
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_evaluation_trade_version UNIQUE (trade_journal_id, score_version),
    CONSTRAINT chk_evaluation_breakdown_object CHECK (
        jsonb_typeof(score_breakdown) = 'object'
        AND jsonb_object_length(score_breakdown) >= 0
    ),
    CONSTRAINT chk_evaluation_weights_object CHECK (
        jsonb_typeof(weights_snapshot) = 'object'
        AND jsonb_object_length(weights_snapshot) >= 0
    )
);

-- Index for querying by symbol/timeframe over time
CREATE INDEX idx_evaluation_symbol_timeframe_evaluated_at
    ON aureus_trade_evaluations(symbol, timeframe, evaluated_at DESC);

-- Partial index for current evaluations only
CREATE INDEX idx_evaluation_current_symbol_tf_evaluated_at
    ON aureus_trade_evaluations(symbol, timeframe, evaluated_at DESC)
    WHERE is_current = TRUE;

-- Index for querying by strategy
CREATE INDEX idx_evaluation_strategy_name ON aureus_trade_evaluations(strategy_name, evaluated_at DESC);

-- Index for querying by trade journal lineage
CREATE INDEX idx_evaluation_trade_journal_id ON aureus_trade_evaluations(trade_journal_id);
