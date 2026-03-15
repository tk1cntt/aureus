import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def cleanup():
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    
    try:
        conn = await asyncpg.connect(db_dsn)
        # Delete old strategies and their associations
        await conn.execute("DELETE FROM aureus_symbol_strategies WHERE strategy_id IN (1, 2, 3)")
        await conn.execute("DELETE FROM aureus_strategy_templates WHERE id IN (1, 2, 3)")
        print("✅ Cleanup of legacy strategies (IDs 1, 2, 3) complete.")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup())
