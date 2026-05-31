import json
import os
import sys

import asyncpg
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.strategies.seed_strategies import seed_system_strategies


FZ_NAMES = ("FZ_CONT_BULL", "FZ_CONT_BEAR")
TEST_SYMBOL = "PYTEST_FZ_CONT"


def _db_dsn():
    return os.getenv(
        "AUREUS_TEST_DB_DSN",
        os.getenv(
            "DATABASE_URL",
            "postgresql://aureus:aureus_password@localhost:5433/aureus",
        ),
    )


@pytest.mark.asyncio
async def test_seed_system_strategies_creates_active_fz_rows(monkeypatch):
    monkeypatch.setenv("SYMBOLS", TEST_SYMBOL)
    conn = await asyncpg.connect(_db_dsn())
    try:
        template_ids = await conn.fetch(
            "SELECT id FROM aureus_strategy_templates WHERE name = ANY($1::text[])",
            list(FZ_NAMES),
        )
        if template_ids:
            await conn.execute(
                "DELETE FROM aureus_symbol_strategies WHERE symbol = $1 AND strategy_id = ANY($2::int[])",
                TEST_SYMBOL,
                [row["id"] for row in template_ids],
            )

        await seed_system_strategies(conn=conn)

        rows = await conn.fetch(
            """
            SELECT t.name, t.config, ss.symbol, ss.is_active
            FROM aureus_strategy_templates t
            JOIN aureus_symbol_strategies ss ON ss.strategy_id = t.id
            WHERE t.name = ANY($1::text[]) AND ss.symbol = $2
            ORDER BY t.name
            """,
            list(FZ_NAMES),
            TEST_SYMBOL,
        )
        by_name = {row["name"]: row for row in rows}

        assert set(by_name) == set(FZ_NAMES)
        for name in FZ_NAMES:
            assert by_name[name]["symbol"] == TEST_SYMBOL
            assert by_name[name]["is_active"] is True

        bull_config = by_name["FZ_CONT_BULL"]["config"]
        bear_config = by_name["FZ_CONT_BEAR"]["config"]
        if isinstance(bull_config, str):
            bull_config = json.loads(bull_config)
        if isinstance(bear_config, str):
            bear_config = json.loads(bear_config)

        assert bull_config["sequence"] == [
            {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
            {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30},
        ]
        assert bull_config["trade_execution"]["direction"] == "BUY"
        assert bull_config["trade_execution"]["entry_type"] == "LIMIT"
        assert bull_config["trade_execution"]["entry_method"] == "FIRST_HIGH_LOW_PIVOT"
        assert bull_config["trade_execution"]["sl"]["type"] == "SECOND_HIGH_LOW_PIVOT"
        assert bull_config["trade_execution"]["early_exits"] == ["choch_down"]

        assert bear_config["sequence"] == [
            {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30},
            {"tag": "bos_down", "weight": 4.0, "required": True, "max_wait": 30},
        ]
        assert bear_config["trade_execution"]["direction"] == "SELL"
        assert bear_config["trade_execution"]["entry_type"] == "LIMIT"
        assert bear_config["trade_execution"]["entry_method"] == "FIRST_LOW_HIGH_PIVOT"
        assert bear_config["trade_execution"]["sl"]["type"] == "SECOND_LOW_HIGH_PIVOT"
        assert bear_config["trade_execution"]["early_exits"] == ["choch_up"]
    finally:
        await conn.close()
