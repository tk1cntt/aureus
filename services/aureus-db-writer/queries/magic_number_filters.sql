-- ============================================================================
-- Magic Number Filter Queries
-- ============================================================================
-- Purpose: Distinguish bot trades (matching aureus_strategy_templates.magic_number)
--          from manual trades (magic_number exists but NOT in templates).
-- ============================================================================

-- Query 1: Bot trades only
-- Use case: Performance metrics for automated strategy trades
-- Returns all CLOSED trades whose magic_number matches a strategy template
SELECT * FROM aureus_trades
WHERE magic_number IN (
    SELECT magic_number FROM aureus_strategy_templates WHERE magic_number IS NOT NULL
)
AND status = 'CLOSED'
ORDER BY created_at DESC;

-- Query 2: Manual trades only
-- Use case: Separate manual trading performance from bot performance
-- Returns CLOSED trades with magic_number that does NOT match any strategy template
SELECT * FROM aureus_trades
WHERE magic_number IS NOT NULL
AND magic_number NOT IN (
    SELECT magic_number FROM aureus_strategy_templates WHERE magic_number IS NOT NULL
)
AND status = 'CLOSED'
ORDER BY created_at DESC;

-- Query 3: All trades with bot/manual classification
-- Use case: Combined view with classification column
SELECT
    t.*,
    CASE
        WHEN t.magic_number IN (SELECT magic_number FROM aureus_strategy_templates WHERE magic_number IS NOT NULL)
        THEN 'bot'
        ELSE 'manual'
    END AS trade_origin
FROM aureus_trades t
WHERE t.magic_number IS NOT NULL
ORDER BY t.created_at DESC;

-- Query 4: Count bot vs manual trades
-- Use case: Dashboard summary statistics
SELECT
    CASE
        WHEN magic_number IN (SELECT magic_number FROM aureus_strategy_templates WHERE magic_number IS NOT NULL)
        THEN 'bot'
        ELSE 'manual'
    END AS trade_origin,
    COUNT(*) as trade_count,
    SUM(profit) as total_profit,
    AVG(profit) as avg_profit
FROM aureus_trades
WHERE magic_number IS NOT NULL AND status = 'CLOSED'
GROUP BY trade_origin;
