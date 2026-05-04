-- Quick 260504-pyn: remove active_signals from Reasoning Bank persistence.

DROP INDEX IF EXISTS idx_reasoning_entries_active_signals;
ALTER TABLE aureus_reasoning_entries DROP COLUMN IF EXISTS active_signals;
