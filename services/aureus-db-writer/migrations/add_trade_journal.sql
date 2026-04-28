-- Phase 37: Trade Execution Journal
-- Tracks full lifecycle: strategy trigger → MT5 order → close for analysis
-- Integration: trace_id FK → aureus_trades (ON DELETE CASCADE)
-- Analysis: GIN indexes on active_signals, context_filters for JSONB queries

CREATE TABLE IF NOT EXISTS aureus_trade_journal (
    id              SERIAL PRIMARY KEY,
    trace_id        TEXT NOT NULL REFERENCES aureus_trades(trace_id) ON DELETE CASCADE,
    
    -- Trade plan (created at strategy match time)
    status          VARCHAR(30) DEFAULT 'TRIGGERED',
    strategy_name   TEXT NOT NULL,
    strategy_id     BIGINT,
    direction       VARCHAR(10) NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    symbol          TEXT NOT NULL,
    score           DOUBLE PRECISION,
    
    -- Signal context (why this trade was triggered)
    active_signals  JSONB,
    context_filters JSONB,
    origin_timestamp TIMESTAMP WITH TIME ZONE,
    
    -- Order details (pending placement and filled MT5 execution)
    ticket          BIGINT,
    pending_order_id BIGINT,
    entry_deal_ticket BIGINT,
    cmd_id          TEXT,
    mt5_comment     TEXT,
    entry_price     DOUBLE PRECISION,
    entry_time      TIMESTAMP WITH TIME ZONE,
    position_id     BIGINT,
    lot_size        DOUBLE PRECISION,
    sl_initial      DOUBLE PRECISION,
    tp_initial      DOUBLE PRECISION,
    
    -- Exit details (filled at MT5 close)
    exit_price      DOUBLE PRECISION,
    exit_time       TIMESTAMP WITH TIME ZONE,
    exit_reason     VARCHAR(50),
    duration_seconds BIGINT,
    pnl             DOUBLE PRECISION,
    pnl_pips        DOUBLE PRECISION,
    commission      DOUBLE PRECISION DEFAULT 0,
    swap            DOUBLE PRECISION DEFAULT 0,
    
    -- Computed analysis fields
    result          VARCHAR(10) CHECK (result IS NULL OR result IN ('WIN', 'LOSS', 'BE')),
    
    -- Metadata
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- B-tree indexes for analytical queries
CREATE INDEX idx_journal_strategy ON aureus_trade_journal(strategy_id, direction);
CREATE INDEX idx_journal_symbol ON aureus_trade_journal(symbol);
CREATE INDEX idx_journal_status ON aureus_trade_journal(status);
CREATE INDEX idx_journal_created_at ON aureus_trade_journal(created_at DESC);
CREATE INDEX idx_journal_result ON aureus_trade_journal(result);
CREATE INDEX idx_journal_pending_order_id ON aureus_trade_journal(pending_order_id);
CREATE INDEX idx_journal_entry_deal_ticket ON aureus_trade_journal(entry_deal_ticket);
CREATE INDEX idx_journal_cmd_id ON aureus_trade_journal(cmd_id);

-- GIN indexes for JSONB containment queries
CREATE INDEX idx_journal_active_signals ON aureus_trade_journal USING GIN(active_signals);
CREATE INDEX idx_journal_context_filters ON aureus_trade_journal USING GIN(context_filters);

-- Comments for documentation
COMMENT ON TABLE aureus_trade_journal IS 'Trade execution journal for strategy analysis';
COMMENT ON COLUMN aureus_trade_journal.trace_id IS 'FK to aureus_trades — links journal entry to trade lifecycle';
COMMENT ON COLUMN aureus_trade_journal.status IS 'TRIGGERED → EXECUTED → CLOSED';
COMMENT ON COLUMN aureus_trade_journal.active_signals IS 'Signal sequence: [{tag, weight, status, time}, ...]';
COMMENT ON COLUMN aureus_trade_journal.context_filters IS 'Market conditions: {htf_trend, session, ob_alignment, ema_trend}';
COMMENT ON COLUMN aureus_trade_journal.exit_reason IS 'TP_HIT, SL_HIT, TRAILING_STOP, MANUAL_CLOSE, SIGNAL_EXIT';
COMMENT ON COLUMN aureus_trade_journal.result IS 'Auto-computed: WIN (pnl>0), LOSS (pnl<0), BE (pnl≈0)';
COMMENT ON COLUMN aureus_trade_journal.duration_seconds IS 'Computed: entry_time to exit_time in seconds';
