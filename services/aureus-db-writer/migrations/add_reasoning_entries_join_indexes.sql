-- Quick 260503-cc6: Reasoning Bank join reuse
-- Formalize non-destructive join indexes/FKs for reasoning -> journal/snapshot.

CREATE INDEX IF NOT EXISTS idx_reasoning_entries_trade_journal_id
    ON aureus_reasoning_entries(trade_journal_id)
    WHERE trade_journal_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reasoning_entries_signal_snapshot_id
    ON aureus_reasoning_entries(signal_snapshot_id)
    WHERE signal_snapshot_id IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_reasoning_entries_trade_journal_id'
          AND conrelid = 'aureus_reasoning_entries'::regclass
    ) THEN
        ALTER TABLE aureus_reasoning_entries
            ADD CONSTRAINT fk_reasoning_entries_trade_journal_id
            FOREIGN KEY (trade_journal_id)
            REFERENCES aureus_trade_journal(id)
            ON DELETE SET NULL
            NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM aureus_reasoning_entries re
        LEFT JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
        WHERE re.trade_journal_id IS NOT NULL
          AND tj.id IS NULL
        LIMIT 1
    ) THEN
        ALTER TABLE aureus_reasoning_entries
            VALIDATE CONSTRAINT fk_reasoning_entries_trade_journal_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_reasoning_entries_signal_snapshot_id'
          AND conrelid = 'aureus_reasoning_entries'::regclass
    ) THEN
        ALTER TABLE aureus_reasoning_entries
            ADD CONSTRAINT fk_reasoning_entries_signal_snapshot_id
            FOREIGN KEY (signal_snapshot_id)
            REFERENCES aureus_trade_signal_snapshots(id)
            ON DELETE SET NULL
            NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM aureus_reasoning_entries re
        LEFT JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id
        WHERE re.signal_snapshot_id IS NOT NULL
          AND ts.id IS NULL
        LIMIT 1
    ) THEN
        ALTER TABLE aureus_reasoning_entries
            VALIDATE CONSTRAINT fk_reasoning_entries_signal_snapshot_id;
    END IF;
END $$;
