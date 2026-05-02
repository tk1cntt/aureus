-- Quick 260502-wur: Reasoning Bank MVP
-- Append-only strategy decision rows linked to trade lifecycle by trace_id.

CREATE TABLE IF NOT EXISTS aureus_reasoning_entries (
    id                 BIGSERIAL PRIMARY KEY,
    trace_id           TEXT NOT NULL REFERENCES aureus_trades(trace_id) ON DELETE CASCADE,
    trade_journal_id   BIGINT REFERENCES aureus_trade_journal(id) ON DELETE SET NULL,
    signal_snapshot_id BIGINT,
    strategy_id        BIGINT,
    strategy_name      TEXT NOT NULL,
    symbol             TEXT NOT NULL,
    timeframe          TEXT,
    direction          VARCHAR(10) NOT NULL CHECK (direction IN ('BUY','SELL')),
    reasoning_source   TEXT NOT NULL DEFAULT 'strategy_match',
    prompt_digest      TEXT,
    decision_digest    TEXT,
    input_context_hash TEXT,
    reasoning_text     TEXT,
    decision_action    TEXT,
    confidence         DOUBLE PRECISION,
    active_signals     JSONB,
    context_filters    JSONB,
    ticket             BIGINT,
    pending_order_id   BIGINT,
    entry_time         TIMESTAMPTZ,
    exit_time          TIMESTAMPTZ,
    success            BOOLEAN,
    reward             DOUBLE PRECISION,
    pnl                DOUBLE PRECISION,
    pnl_pips           DOUBLE PRECISION,
    result             VARCHAR(10),
    created_at         TIMESTAMPTZ DEFAULT now(),
    evaluated_at       TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reasoning_entries_trace_id ON aureus_reasoning_entries(trace_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_entries_strategy ON aureus_reasoning_entries(strategy_id, direction);
CREATE INDEX IF NOT EXISTS idx_reasoning_entries_symbol ON aureus_reasoning_entries(symbol);
CREATE INDEX IF NOT EXISTS idx_reasoning_entries_created_at ON aureus_reasoning_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reasoning_entries_success ON aureus_reasoning_entries(success);
CREATE INDEX IF NOT EXISTS idx_reasoning_entries_active_signals ON aureus_reasoning_entries USING GIN(active_signals);
CREATE INDEX IF NOT EXISTS idx_reasoning_entries_context_filters ON aureus_reasoning_entries USING GIN(context_filters);

COMMENT ON TABLE aureus_reasoning_entries IS 'Append-only Reasoning Bank decision rows linked to trade journal lifecycle';
COMMENT ON COLUMN aureus_reasoning_entries.reasoning_text IS 'Optional strategy rationale from event payload only; no raw prompt or secrets';
COMMENT ON COLUMN aureus_reasoning_entries.reward IS 'Outcome reward, preferring pnl_pips then pnl';
