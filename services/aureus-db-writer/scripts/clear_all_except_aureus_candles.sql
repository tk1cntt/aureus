-- Clear all data in current database except `public.aureus_candles`
-- Usage:
--   psql "$DATABASE_URL" -f services/aureus-db-writer/scripts/clear_all_except_aureus_candles.sql
--
-- WARNING: Destructive operation. This keeps table structures, only deletes rows.

BEGIN;

DO $$
DECLARE
    tbl RECORD;
BEGIN
    FOR tbl IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename <> 'aureus_candles'
        ORDER BY tablename
    LOOP
        EXECUTE format('TRUNCATE TABLE public.%I RESTART IDENTITY CASCADE;', tbl.tablename);
        RAISE NOTICE 'Cleared table: public.%', tbl.tablename;
    END LOOP;
END $$;

COMMIT;

-- Optional quick check:
-- SELECT schemaname, relname AS table_name, n_live_tup AS estimated_rows
-- FROM pg_stat_user_tables
-- ORDER BY relname;
