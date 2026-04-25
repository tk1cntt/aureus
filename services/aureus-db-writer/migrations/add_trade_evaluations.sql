CREATE TABLE IF NOT EXISTS aureus_trade_signal_snapshots (
    id BIGSERIAL PRIMARY KEY,
    trade_journal_id BIGINT NOT NULL REFERENCES aureus_trade_journal(id) ON DELETE CASCADE,
    trace_id TEXT NOT NULL,
    ticket BIGINT,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    atr DOUBLE PRECISION,
    ema_21 DOUBLE PRECISION,
    ema_34 DOUBLE PRECISION,
    ema_55 DOUBLE PRECISION,
    ema_89 DOUBLE PRECISION,
    ema_100 DOUBLE PRECISION,
    ema_200 DOUBLE PRECISION,
    vol_sma_20 DOUBLE PRECISION,
    session INTEGER,
    candle_color_d1 INTEGER,
    candle_color_h1 INTEGER,
    candle_color_m30 INTEGER,
    candle_color_m15 INTEGER,
    candle_color_m5 INTEGER,
    bb_m1_up DOUBLE PRECISION,
    bb_m1_dn DOUBLE PRECISION,
    bb_m5_up DOUBLE PRECISION,
    bb_m5_dn DOUBLE PRECISION,
    bb_m15_up DOUBLE PRECISION,
    bb_m15_dn DOUBLE PRECISION,
    bb_m30_up DOUBLE PRECISION,
    bb_m30_dn DOUBLE PRECISION,
    bb_h1_up DOUBLE PRECISION,
    bb_h1_dn DOUBLE PRECISION,
    cisd_m5 INTEGER,
    cisd_m15 INTEGER,
    cisd_m30 INTEGER,
    cisd_h1 INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_trade_signal_snapshot_trade UNIQUE (trade_journal_id)
);

CREATE INDEX idx_trade_signal_snapshot_symbol_created_at
    ON aureus_trade_signal_snapshots(symbol, created_at DESC);

CREATE INDEX idx_trade_signal_snapshot_symbol_session_created_at
    ON aureus_trade_signal_snapshots(symbol, session, created_at DESC);

CREATE INDEX idx_trade_signal_snapshot_created_at_brin
    ON aureus_trade_signal_snapshots USING BRIN(created_at);
