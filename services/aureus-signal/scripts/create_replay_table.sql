-- Strategy Replay Results Table
-- Stores Tier 2 baseline metrics from strategy_replay.py runs.
-- Used for regression detection when comparing Nautilus integration results.

CREATE TABLE IF NOT EXISTS aureus_strategy_replay_results (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_config JSONB,
    bar_count INT NOT NULL,
    trigger_count INT NOT NULL DEFAULT 0,
    trigger_rate FLOAT NOT NULL DEFAULT 0.0,
    reject_count INT NOT NULL DEFAULT 0,
    reject_reasons JSONB DEFAULT '{}',
    score_min FLOAT,
    score_max FLOAT,
    score_avg FLOAT,
    signal_contribution JSONB DEFAULT '{}',
    session_distribution JSONB DEFAULT '{}',
    context_filter_stats JSONB DEFAULT '{}',
    deterministic BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replay_symbol ON aureus_strategy_replay_results(symbol);
CREATE INDEX IF NOT EXISTS idx_replay_strategy ON aureus_strategy_replay_results(strategy_name);
CREATE INDEX IF NOT EXISTS idx_replay_created ON aureus_strategy_replay_results(created_at);
