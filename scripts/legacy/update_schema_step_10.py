
import asyncio
import asyncpg

POSTGRES_URL = "postgres://aureus:aureus_password@localhost:5432/aureus"

async def main():
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        # Check if column exists first
        exists = await conn.fetchval("""
            SELECT count(*) 
            FROM information_schema.columns 
            WHERE table_name = 'aureus_strategy_templates' AND column_name = 'symbol'
        """)
        
        if exists == 0:
            print("Adding column 'symbol' to 'aureus_strategy_templates'...")
            await conn.execute("ALTER TABLE aureus_strategy_templates ADD COLUMN symbol TEXT;")
            print("Success.")
        else:
            print("Column 'symbol' already exists.")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
