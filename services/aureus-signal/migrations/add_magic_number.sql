-- Phase 26: Add magic_number column for MT5 order tracking (STRAT-04)
ALTER TABLE aureus_strategy_templates
  ADD COLUMN IF NOT EXISTS magic_number BIGINT;

-- Default: strategy_id * 1000 for existing rows
UPDATE aureus_strategy_templates
  SET magic_number = id * 1000
  WHERE magic_number IS NULL;

COMMENT ON COLUMN aureus_strategy_templates.magic_number IS 'Static MT5 magic number per strategy for order tracking';
