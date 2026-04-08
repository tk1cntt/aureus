-- Migration: Add missing columns to aureus_ai_analysis
-- Run: docker exec aureus_timescaledb_dev psql -U aureus -d aureus -f /tmp/fix_ai_analysis.sql

ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS aci INTEGER;
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS sentiment TEXT;
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS narrative TEXT;
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS debate_log JSONB;
ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS analysis_type TEXT;

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'aureus_ai_analysis' 
ORDER BY ordinal_position;
