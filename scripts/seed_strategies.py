import asyncio
import os
from pathlib import Path
import importlib.util
import asyncpg
from dotenv import load_dotenv


# Wrapper script: dùng chung source seed chính trong service để tránh drift metadata/sequence.
_SERVICE_SEED_PATH = Path(__file__).resolve().parents[1] / "services" / "aureus-signal" / "engine" / "strategies" / "seed_strategies.py"
_spec = importlib.util.spec_from_file_location("aureus_signal_seed_strategies", _SERVICE_SEED_PATH)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)
seed_system_strategies = _module.seed_system_strategies

if __name__ == "__main__":
    # For manual testing
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    
    async def run():
        pool = await asyncpg.create_pool(db_dsn)
        await seed_system_strategies(pool)
        await pool.close()
        
    asyncio.run(run())
