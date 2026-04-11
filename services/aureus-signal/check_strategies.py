import asyncio
import asyncpg
import json

async def main():
    conn = await asyncpg.connect(
        'postgresql://aureus:aureus_password@localhost:5432/aureus',
        ssl='prefer'
    )

    # Get active strategies for XAUUSD
    rows = await conn.fetch(
        "SELECT t.id, t.name, t.min_score, t.config FROM aureus_strategy_templates t JOIN aureus_symbol_strategies ss ON t.id = ss.strategy_id WHERE ss.symbol = $1 AND ss.is_active = true",
        'XAUUSD'
    )
    print(f"Found {len(rows)} active strategies for XAUUSD:")
    for r in rows:
        config = json.loads(r["config"]) if isinstance(r["config"], str) else r["config"]
        print(f"  ID={r['id']} name={r['name']} min_score={r['min_score']}")
        print(f"    context_filters={config.get('context_filters', [])}")
        seq = config.get('sequence', [])
        print(f"    sequence={[s.get('tag') for s in seq]}")
        print(f"    trade_execution.direction={config.get('trade_execution', {}).get('direction')}")

    # Also check which symbols have strategies
    sym_rows = await conn.fetch(
        "SELECT ss.symbol, COUNT(*) FROM aureus_symbol_strategies ss WHERE ss.is_active = true GROUP BY ss.symbol"
    )
    print("\nSymbol strategy counts:")
    for r in sym_rows:
        print(f"  {r['symbol']}: {r['count']}")

    await conn.close()

asyncio.run(main())
