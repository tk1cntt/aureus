-- 1. Find journal tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_name LIKE '%journal%' 
   OR table_name LIKE '%trade%' 
ORDER BY table_name;

-- 2. If aureus_trade_journal exists, check columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'aureus_trade_journal' 
ORDER BY ordinal_position;

-- 3. Row count
SELECT 'aureus_trade_journal' as table_name, COUNT(*) as row_count 
FROM aureus_trade_journal;

-- 4. Latest 5 entries (using actual column names)
SELECT trace_id, strategy_name, symbol, direction, status, ticket, entry_price, entry_time, pnl, exit_reason, created_at
FROM aureus_trade_journal 
ORDER BY created_at DESC 
LIMIT 5;

-- 5. Check aureus_trades table
SELECT trace_id, symbol, strategy_name, direction, status, entry_price, ticket, created_at
FROM aureus_trades
ORDER BY created_at DESC
LIMIT 5;
