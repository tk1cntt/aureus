import asyncpg
import asyncio

async def migrate():
    try:
        conn = await asyncpg.connect('postgresql://aureus:aureus_password@localhost:5432/aureus')
        
        # Migration to add CHOCH and BOS columns to aureus_swing_points
        await conn.execute("""
        ALTER TABLE aureus_swing_points ADD COLUMN IF NOT EXISTS is_choch BOOLEAN DEFAULT FALSE;
        ALTER TABLE aureus_swing_points ADD COLUMN IF NOT EXISTS breakout_t TIMESTAMPTZ;
        ALTER TABLE aureus_swing_points ADD COLUMN IF NOT EXISTS choch_type TEXT;
        ALTER TABLE aureus_swing_points ADD COLUMN IF NOT EXISTS is_bos BOOLEAN DEFAULT FALSE;
        ALTER TABLE aureus_swing_points ADD COLUMN IF NOT EXISTS bos_type TEXT;
        """)
        
        print("Schema migration for aureus_swing_points COMPLETED.")
        await conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
