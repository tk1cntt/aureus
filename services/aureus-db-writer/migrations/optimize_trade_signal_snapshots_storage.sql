CREATE TABLE IF NOT EXISTS aureus_trade_signal_snapshots (
    id BIGSERIAL PRIMARY KEY,
    trade_journal_id BIGINT NOT NULL REFERENCES aureus_trade_journal(id) ON DELETE CASCADE,
    trace_id TEXT NOT NULL,
    ticket BIGINT,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    signal_schema_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_trade_signal_snapshot_trade_schema UNIQUE (trade_journal_id, signal_schema_version)
);

CREATE INDEX IF NOT EXISTS idx_trade_signal_snapshot_symbol_tf_created_at
    ON aureus_trade_signal_snapshots(symbol, timeframe, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_trade_signal_snapshot_created_at_brin
    ON aureus_trade_signal_snapshots USING BRIN(created_at);

ALTER TABLE aureus_trade_signal_snapshots
    ADD COLUMN IF NOT EXISTS timeframe TEXT,
    ADD COLUMN IF NOT EXISTS signal_schema_version TEXT;

ALTER TABLE aureus_trade_signal_snapshots
    DROP COLUMN IF EXISTS signal_snapshot,
    DROP COLUMN IF EXISTS cisd_direction,
    DROP COLUMN IF EXISTS ema21,
    DROP COLUMN IF EXISTS ema55;

UPDATE aureus_trade_signal_snapshots
SET
    timeframe = COALESCE(timeframe, 'M15'),
    signal_schema_version = COALESCE(signal_schema_version, 'sig-v2.0.0')
WHERE timeframe IS NULL
   OR signal_schema_version IS NULL;

ALTER TABLE aureus_trade_signal_snapshots
    ALTER COLUMN timeframe SET NOT NULL,
    ALTER COLUMN signal_schema_version SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_trade_signal_snapshot_trade_schema'
          AND conrelid = 'aureus_trade_signal_snapshots'::regclass
    ) THEN
        ALTER TABLE aureus_trade_signal_snapshots
            ADD CONSTRAINT uq_trade_signal_snapshot_trade_schema
            UNIQUE (trade_journal_id, signal_schema_version);
    END IF;
END;
$$;


CREATE TABLE IF NOT EXISTS aureus_trade_signal_snapshots_archive (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT,
    trade_journal_id BIGINT NOT NULL,
    trace_id TEXT NOT NULL,
    ticket BIGINT,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    signal_schema_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_trade_signal_snapshot_archive_trade_schema_created UNIQUE (trade_journal_id, signal_schema_version, created_at)
);

CREATE INDEX IF NOT EXISTS idx_trade_signal_snapshot_archive_symbol_tf_archived_at
    ON aureus_trade_signal_snapshots_archive(symbol, timeframe, archived_at DESC);

CREATE INDEX IF NOT EXISTS idx_trade_signal_snapshot_archive_archived_at_brin
    ON aureus_trade_signal_snapshots_archive USING BRIN(archived_at);

ALTER TABLE aureus_trade_signal_snapshots_archive
    DROP COLUMN IF EXISTS signal_snapshot,
    DROP COLUMN IF EXISTS cisd_direction,
    DROP COLUMN IF EXISTS ema21,
    DROP COLUMN IF EXISTS ema55;

CREATE OR REPLACE FUNCTION aureus_archive_and_prune_trade_signal_snapshots(
    p_now TIMESTAMPTZ DEFAULT now(),
    p_batch_size INTEGER DEFAULT 5000
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    moved_rows INTEGER := 0;
BEGIN
    WITH candidates AS (
        SELECT id
        FROM aureus_trade_signal_snapshots
        WHERE created_at < (p_now - interval '90 days')
        ORDER BY created_at ASC
        LIMIT 5000
    ), archived AS (
        INSERT INTO aureus_trade_signal_snapshots_archive (
            snapshot_id, trade_journal_id, trace_id, ticket, strategy_name, symbol,
            timeframe, signal_schema_version, created_at
        )
        SELECT
            s.id, s.trade_journal_id, s.trace_id, s.ticket, s.strategy_name, s.symbol,
            s.timeframe, s.signal_schema_version, s.created_at
        FROM aureus_trade_signal_snapshots s
        JOIN candidates c ON c.id = s.id
        ON CONFLICT DO NOTHING
        RETURNING snapshot_id
    ), deleted AS (
        DELETE FROM aureus_trade_signal_snapshots s
        USING candidates c
        WHERE s.id = c.id
        RETURNING s.id
    )
    SELECT COUNT(*) INTO moved_rows FROM deleted;

    RETURN moved_rows;
END;
$$;
