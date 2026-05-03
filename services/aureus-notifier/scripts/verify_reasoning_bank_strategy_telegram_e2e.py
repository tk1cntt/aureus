"""DB/runtime E2E for strategy-scoped Reasoning Bank Telegram enrichment."""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg

SERVICES = Path(__file__).resolve().parents[2]
TRADER = SERVICES / "aureus-trader"
NOTIFIER = SERVICES / "aureus-notifier"
for path in (TRADER, NOTIFIER):
    if str(path) not in sys.path:
        sys.path.append(str(path))

from formatters import format_strategy_match
from reasoning_embeddings import fetch_strategy_reasoning_insights


def _dsn():
    return os.getenv("DATABASE_URL") or os.getenv("AUREUS_DB_DSN")


async def main():
    dsn = _dsn()
    if not dsn:
        raise SystemExit("DATABASE_URL or AUREUS_DB_DSN required")
    conn = await asyncpg.connect(dsn=dsn)
    prefix = "260503-b25-e2e"
    try:
        await conn.execute("DELETE FROM aureus_trades WHERE trace_id LIKE $1", prefix + "%")
        await conn.execute(
            """
            INSERT INTO aureus_trades (trace_id, symbol, strategy_name, direction, entry_type, status)
            VALUES ($1, 'XAUUSD', 'STRAT_A', 'BUY', 'MARKET', 'CLOSED'),
                   ($2, 'XAUUSD', 'STRAT_B', 'BUY', 'MARKET', 'CLOSED')
            """,
            prefix + "-a",
            prefix + "-b",
        )
        await conn.execute(
            """
            INSERT INTO aureus_reasoning_entries
                (trace_id, strategy_name, symbol, direction, reasoning_text, success, reward, pnl_pips, created_at, evaluated_at)
            VALUES
                ($1, 'STRAT_A', 'XAUUSD', 'BUY', 'STRAT_A lesson keep pullback tight', true, 1.5, 12.0, now(), now()),
                ($2, 'STRAT_B', 'XAUUSD', 'BUY', 'STRAT_B lesson must not leak', false, -1.0, -8.0, now(), now())
            """,
            prefix + "-a",
            prefix + "-b",
        )
        insight = await fetch_strategy_reasoning_insights(conn, "STRAT_A", symbol="XAUUSD", direction="BUY", limit=5)
        event = {
            "type": "STRATEGY_MATCH",
            "symbol": "XAUUSD",
            "t": 1712345678,
            "data": {
                "strategy": "STRAT_A",
                "strategy_id": 1,
                "side": "BUY",
                "entry_type": "MARKET",
                "sl": 1950.5,
                "tp": 1970.0,
                "size_value": 1.0,
                "reason_code": "OK",
                "reasoning_bank": insight,
            },
        }
        text = format_strategy_match(event)
        assert "Reasoning Bank" in text
        assert "STRAT_A lesson keep pullback tight" in text
        assert "STRAT_B lesson must not leak" not in text

        failure_event = dict(event)
        failure_event["data"] = dict(event["data"])
        failure_event["data"].pop("reasoning_bank")
        fallback_text = format_strategy_match(failure_event)
        assert "STRATEGY MATCH" in fallback_text
        assert "Reasoning Bank" not in fallback_text

        print("PASS: strategy-scoped Reasoning Bank Telegram E2E")
    finally:
        await conn.execute("DELETE FROM aureus_trades WHERE trace_id LIKE $1", prefix + "%")
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
