import asyncpg
import asyncio

async def run():
    try:
        conn = await asyncpg.connect('postgresql://aureus:aureus_password@localhost:5432/aureus')
        count = await conn.fetchval('SELECT count(*) FROM aureus_swing_points;')
        print(f'Swing Points Count: {count}')
        
        # Also check for recent CHOCH
        choch_count = await conn.fetchval("SELECT count(*) FROM aureus_swing_points WHERE is_choch = true;")
        print(f'CHOCH Count: {choch_count}')
        
        bos_count = await conn.fetchval("SELECT count(*) FROM aureus_swing_points WHERE is_bos = true;")
        print(f'BOS Count: {bos_count}')
        
        # Check for HH/LL
        hh_ll_count = await conn.fetchval("SELECT count(*) FROM aureus_swing_points WHERE type IN ('HH', 'LL');")
        print(f'HH/LL Count: {hh_ll_count}')
        
        await conn.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(run())
