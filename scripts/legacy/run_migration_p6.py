
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def run_migration():
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    print(f"Connecting to {db_dsn}...")
    
    try:
        conn = await asyncpg.connect(db_dsn)
        print("Connected. Running migration...")
        
        migration_sql = """
        -- Migration for Phase 6: Algorithmic Scoring Visualization
        ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS algo_score INTEGER;
        ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS algo_breakdown JSONB;
        ALTER TABLE aureus_ai_analysis ADD COLUMN IF NOT EXISTS audit_source TEXT DEFAULT 'AI';
        """
        
        await conn.execute(migration_sql)
        print("✅ Migration applied successfully!")
        await conn.close()
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_migration())
