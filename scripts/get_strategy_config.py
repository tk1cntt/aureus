import asyncpg
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    conn = await asyncpg.connect(db_dsn)
    
    try:
        row = await conn.fetchrow(
            "SELECT config FROM aureus_strategy_templates WHERE name = $1",
            "ORDER_FLOW_BULL"
        )
        
        if row:
            config = row["config"]
            if isinstance(config, str):
                config = json.loads(config)
            
            print("="*80)
            print("ORDER_FLOW_BULL Strategy Configuration")
            print("="*80)
            print(f"\nName: {config.get('name')}")
            print(f"Min Score: {config.get('min_score_threshold')}")
            print(f"\nSequence:")
            for i, step in enumerate(config.get('sequence', [])):
                print(f"  {i}. tag={step['tag']}, weight={step['weight']}, required={step.get('required', False)}")
            
            print(f"\nFull Config:")
            print(json.dumps(config, indent=2))
        else:
            print("Strategy ORDER_FLOW_BULL not found!")
    finally:
        await conn.close()

asyncio.run(main())
