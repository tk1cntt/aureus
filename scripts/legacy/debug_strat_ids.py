
import asyncio
import asyncpg
import json

async def debug():
    POSTGRES_URL = "postgresql://aureus:aureus@localhost:5432/aureus"
    conn = await asyncpg.connect(POSTGRES_URL)
    
    symbol = "XAUUSD"
    query = """
        SELECT t.id, t.name, t.config, t.min_score
        FROM aureus_strategy_templates t
        JOIN aureus_symbol_strategies ss ON t.id = ss.strategy_id
        WHERE ss.symbol = $1 AND ss.is_active = true
    """
    rows = await conn.fetch(query, symbol)
    print(f"Found {len(rows)} strategies")
    for r in rows:
        print(f"ID: {r['id']} (type: {type(r['id'])}), Name: {r['name']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(debug())
