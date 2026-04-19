import asyncio
import inspect
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.live_engine import run_signal_engine
from engine.strategy_executor import run_strategy_executor
from engine.strategies.seed_strategies import seed_system_strategies


class FakeConn:
    def __init__(self, templates=None, assignments=None):
        self.templates = templates or {}
        self.assignments = assignments or {}

    async def execute(self, query, *args):
        normalized = " ".join(query.split())

        if "INSERT INTO aureus_strategy_templates" in normalized:
            name, description, config_raw, min_score = args
            config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
            existing = self.templates.get(name)
            if existing:
                template_id = existing["id"]
            else:
                template_id = len(self.templates) + 1
            self.templates[name] = {
                "id": template_id,
                "name": name,
                "description": description,
                "config": config,
                "min_score": min_score,
            }
            return "INSERT 0 1"

        if "INSERT INTO aureus_symbol_strategies" in normalized:
            symbol, strategy_id = args
            key = (symbol, strategy_id)
            current = self.assignments.get(key)
            self.assignments[key] = {
                "symbol": symbol,
                "strategy_id": strategy_id,
                "is_active": True,
                "created": current is None,
            }
            return "INSERT 0 1"

        if "UPDATE aureus_symbol_strategies" in normalized and "is_active = false" in normalized:
            symbol = args[0]
            active_ids = set(args[1])
            changed = 0
            for (sym, sid), record in self.assignments.items():
                if sym == symbol and sid not in active_ids and record.get("is_active", True):
                    record["is_active"] = False
                    changed += 1
            return f"UPDATE {changed}"

        raise AssertionError(f"Unsupported query for execute: {normalized}")

    async def fetch(self, query, *args):
        normalized = " ".join(query.split())

        if "SELECT id, name FROM aureus_strategy_templates WHERE name = ANY($1::text[])" in normalized:
            names = set(args[0])
            rows = []
            for name, item in sorted(self.templates.items()):
                if name in names:
                    rows.append({"id": item["id"], "name": name})
            return rows

        if "SELECT id, name FROM aureus_strategy_templates" in normalized:
            rows = []
            for name, item in sorted(self.templates.items()):
                rows.append({"id": item["id"], "name": name})
            return rows

        if "SELECT ss.symbol, t.id as strategy_id, t.name as strategy_name" in normalized:
            symbols = list(args[0])
            rows = []
            by_id = {item["id"]: item for item in self.templates.values()}
            for (symbol, strategy_id), assignment in sorted(self.assignments.items()):
                if symbol in symbols and assignment.get("is_active", True):
                    rows.append(
                        {
                            "symbol": symbol,
                            "strategy_id": strategy_id,
                            "strategy_name": by_id[strategy_id]["name"],
                            "is_active": True,
                        }
                    )
            return rows

        raise AssertionError(f"Unsupported query for fetch: {normalized}")

    async def fetchval(self, query, *args):
        normalized = " ".join(query.split())
        if "SELECT COUNT(*) FROM aureus_symbol_strategies" in normalized:
            return len(self.assignments)
        raise AssertionError(f"Unsupported query for fetchval: {normalized}")


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)


@pytest.mark.asyncio
async def test_seed_sync_idempotent(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD,EURUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    await seed_system_strategies(pool)
    first_templates = len(conn.templates)
    first_assignments = len(conn.assignments)

    await seed_system_strategies(pool)
    second_templates = len(conn.templates)
    second_assignments = len(conn.assignments)

    assert first_templates > 0
    assert first_templates == second_templates
    assert first_assignments == second_assignments


@pytest.mark.asyncio
async def test_seed_sync_deactivate_removed_pairs(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")

    conn = FakeConn(
        templates={
            "TREND_CONT_BULL": {
                "id": 1,
                "name": "TREND_CONT_BULL",
                "description": "old",
                "config": {},
                "min_score": 0,
            },
            "LEGACY_ONLY": {
                "id": 2,
                "name": "LEGACY_ONLY",
                "description": "old",
                "config": {},
                "min_score": 0,
            },
        },
        assignments={
            ("XAUUSD", 1): {"symbol": "XAUUSD", "strategy_id": 1, "is_active": True},
            ("XAUUSD", 2): {"symbol": "XAUUSD", "strategy_id": 2, "is_active": True},
        },
    )
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    assert conn.assignments[("XAUUSD", 1)]["is_active"] is True
    assert conn.assignments[("XAUUSD", 2)]["is_active"] is False


@pytest.mark.asyncio
async def test_seed_sync_reactivate_reintroduced_pair(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")

    conn = FakeConn(
        templates={
            "TREND_CONT_BULL": {
                "id": 1,
                "name": "TREND_CONT_BULL",
                "description": "old",
                "config": {},
                "min_score": 0,
            }
        },
        assignments={
            ("XAUUSD", 1): {"symbol": "XAUUSD", "strategy_id": 1, "is_active": False},
        },
    )
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    assert conn.assignments[("XAUUSD", 1)]["is_active"] is True


def test_startup_reload_order():
    source_signal = inspect.getsource(run_signal_engine)
    assert source_signal.index("await seed_system_strategies(db_pool)") < source_signal.index(
        "await symbol_strategies[symbol].load_from_db(db_pool, symbol)"
    )

    source_executor = inspect.getsource(run_strategy_executor)
    assert source_executor.index("await seed_system_strategies(db_pool)") < source_executor.index(
        "await symbol_strategies[symbol].load_from_db(db_pool, symbol)"
    )
    assert source_executor.index("await seed_system_strategies(db_pool)") < source_executor.index(
        "await symbol_strategies[s].load_from_db(db_pool, s)"
    )


@pytest.mark.asyncio
async def test_sync_summary_log(monkeypatch, caplog):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    with caplog.at_level("INFO"):
        await seed_system_strategies(pool)

    logs = "\n".join(record.message for record in caplog.records)
    assert "sync_summary" in logs
    assert "activated=" in logs
    assert "deactivated=" in logs
    assert "unchanged=" in logs


def test_load_active_only():
    source = inspect.getsource(run_strategy_executor)
    assert "load_from_db" in source
    assert "ss.is_active = true" in inspect.getsource(__import__("engine.strategies.registry", fromlist=["StrategyRegistry"]).StrategyRegistry.load_from_db)
