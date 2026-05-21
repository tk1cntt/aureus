import asyncio
import ast
import inspect
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.live_engine import run_signal_engine
from engine.state import SymbolState
from engine.strategies.registry import StrategyRegistry
from engine.strategies.template import TemplateStrategy
from engine.strategy_executor import run_strategy_executor
from engine.strategies.seed_strategies import seed_system_strategies
from scripts.strategy_seed_sync_dryrun import _run


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

        if "SELECT symbol, strategy_id, is_active FROM aureus_symbol_strategies" in normalized:
            rows = []
            for (symbol, strategy_id), assignment in sorted(self.assignments.items()):
                rows.append(
                    {
                        "symbol": symbol,
                        "strategy_id": strategy_id,
                        "is_active": assignment.get("is_active", True),
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

    async def close(self):
        return None


class GuardedPool(FakePool):
    def __init__(self, conn):
        super().__init__(conn)
        self.acquire_calls = 0

    def acquire(self):
        self.acquire_calls += 1
        if self.acquire_calls > 1:
            raise AssertionError("dry-run must not acquire a second connection")
        return super().acquire()


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn
        self.started = False
        self.rolled_back = False
        self._templates_snapshot = None
        self._assignments_snapshot = None

    async def start(self):
        self.started = True
        self._templates_snapshot = json.loads(json.dumps(self.conn.templates))
        self._assignments_snapshot = {
            key: value.copy() for key, value in self.conn.assignments.items()
        }

    async def rollback(self):
        self.rolled_back = True
        if self._templates_snapshot is not None:
            self.conn.templates = json.loads(json.dumps(self._templates_snapshot))
        if self._assignments_snapshot is not None:
            self.conn.assignments = {
                key: value.copy() for key, value in self._assignments_snapshot.items()
            }


class DryRunConn(FakeConn):
    def __init__(self, templates=None, assignments=None):
        super().__init__(templates=templates, assignments=assignments)
        self.tx = FakeTransaction(self)

    def transaction(self):
        return self.tx


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


@pytest.mark.asyncio
async def test_dryrun_transaction_uses_same_connection_and_rolls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = DryRunConn()
    guarded_pool = GuardedPool(conn)

    async def fake_create_pool(*args, **kwargs):
        return guarded_pool

    monkeypatch.setattr("scripts.strategy_seed_sync_dryrun.asyncpg.create_pool", fake_create_pool)
    monkeypatch.setattr("scripts.strategy_seed_sync_dryrun.load_dotenv", lambda: None)

    baseline_templates = len(conn.templates)
    baseline_assignments = len(conn.assignments)

    code = await _run(str(tmp_path / "dryrun-report.json"))

    assert code == 0
    assert guarded_pool.acquire_calls == 1
    assert conn.tx.started is True
    assert conn.tx.rolled_back is True
    assert len(conn.templates) == baseline_templates
    assert len(conn.assignments) == baseline_assignments


@pytest.mark.asyncio
async def test_seed_sync_requires_pool_or_conn():
    with pytest.raises(ValueError, match="requires pool or conn"):
        await seed_system_strategies()


def test_seed_catalog_declares_is_active_flags():
    source = inspect.getsource(seed_system_strategies)
    total_names = source.count('"name":')
    total_is_active = source.count('"is_active": True') + source.count('"is_active": False')

    assert total_names >= 10
    assert source.count('"is_active": True') >= 10
    assert total_names == total_is_active


def test_seed_sync_assignments_use_active_strategy_names():
    source = inspect.getsource(seed_system_strategies)
    assert 'active_strategy_names = [item["name"] for item in strategies if item.get("is_active", True)]' in source
    assert 'for strategy_name in active_strategy_names:' in source


@pytest.mark.asyncio
async def test_seed_sync_empty_symbols_env_defaults_to_xauusd(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "")
    conn = FakeConn()
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    assert conn.assignments
    assert all(symbol == "XAUUSD" for symbol, _ in conn.assignments.keys())


@pytest.mark.asyncio
async def test_trend_cont_market_filters_db_backed_seed_path(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    assert conn.templates["TREND_CONT_BULL"]["config"]["context_filters"] == [
        {"type": "trend_cont_poc_cisd", "direction": "bullish"}
    ]
    assert conn.templates["TREND_CONT_BEAR"]["config"]["context_filters"] == [
        {"type": "trend_cont_poc_cisd", "direction": "bearish"}
    ]
    for name in ("TREND_CONT_LIMIT_BULL", "TREND_CONT_LIMIT_BEAR", "TREND_CONT_FVG_BULL", "TREND_CONT_FVG_BEAR"):
        assert conn.templates[name]["config"]["context_filters"] == []


@pytest.mark.asyncio
async def test_limit_ema_touch_bull_filters_normal_case(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    bull = conn.templates["LIMIT_EMA_TOUCH_BULL"]
    filters = bull["config"]["context_filters"]

    assert len(filters) == 3
    assert {f["type"] for f in filters} == {"ema_alignment", "ema_relation"}
    assert {f["period"] for f in filters if f["type"] == "ema_alignment"} == {21, 55}
    assert all(
        f.get("required_slope") == "POSITIVE"
        for f in filters
        if f["type"] == "ema_alignment"
    )
    relation = next(f for f in filters if f["type"] == "ema_relation")
    assert relation["fast_period"] == 21
    assert relation["slow_period"] == 55
    assert relation["operator"] == ">"


@pytest.mark.asyncio
async def test_limit_ema_touch_bear_filters_abnormal_guard(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    bear = conn.templates["LIMIT_EMA_TOUCH_BEAR"]
    filters = bear["config"]["context_filters"]

    assert len(filters) == 3
    assert {f["period"] for f in filters if f["type"] == "ema_alignment"} == {21, 55}
    assert all(
        f.get("required_slope") == "NEGATIVE"
        for f in filters
        if f["type"] == "ema_alignment"
    )
    relation = next(f for f in filters if f["type"] == "ema_relation")
    assert relation["fast_period"] == 21
    assert relation["slow_period"] == 55
    assert relation["operator"] == "<"

    # Abnormal guard: không cho cấu hình ngược chiều
    assert relation["operator"] != ">"
    assert not any(
        f.get("required_slope") == "POSITIVE"
        for f in filters
        if f["type"] == "ema_alignment"
    )


def test_seed_catalog_buy_sell_symmetry_lint():
    seed_file = Path(__file__).resolve().parents[1] / "engine/strategies/seed_strategies.py"
    module = ast.parse(seed_file.read_text(encoding="utf-8"))

    strategies = None
    for node in ast.walk(module):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "strategies":
                    strategies = ast.literal_eval(node.value)
                    break
        if strategies is not None:
            break

    assert strategies is not None, "Cannot parse strategies list from seed_strategies.py"

    by_name = {item["name"]: item for item in strategies}
    pairs = []
    for name in sorted(by_name):
        if name.endswith("_BULL"):
            bear_name = name[:-5] + "_BEAR"
            if bear_name in by_name:
                pairs.append((name, bear_name))

    assert pairs, "No _BULL/_BEAR strategy pairs found"

    for bull_name, bear_name in pairs:
        bull = by_name[bull_name]
        bear = by_name[bear_name]

        bull_exec = bull.get("config", {}).get("trade_execution", {})
        bear_exec = bear.get("config", {}).get("trade_execution", {})

        assert bull_exec.get("direction") == "BUY", f"{bull_name}: direction must be BUY"
        assert bear_exec.get("direction") == "SELL", f"{bear_name}: direction must be SELL"

        bull_trailing = (bull_exec.get("trailing") or {}).get("type")
        bear_trailing = (bear_exec.get("trailing") or {}).get("type")
        if bull_trailing == "SWING_LOW":
            assert bear_trailing == "SWING_HIGH", (
                f"{bull_name}/{bear_name}: trailing mismatch, expected SWING_HIGH for bear"
            )

        bull_exits = set(bull_exec.get("early_exits", []))
        bear_exits = set(bear_exec.get("early_exits", []))
        if "choch_down" in bull_exits:
            assert "choch_up" in bear_exits, (
                f"{bull_name}/{bear_name}: bear must contain choch_up in early_exits"
            )


@pytest.mark.asyncio
async def test_trend_cont_limit_seed_declarations_match_runtime_contract(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    for name, direction, required_tag, exit_tag in (
        ("TREND_CONT_LIMIT_BULL", "BUY", "choch_up", "choch_down"),
        ("TREND_CONT_LIMIT_BEAR", "SELL", "choch_down", "choch_up"),
    ):
        assert name in conn.templates
        config = conn.templates[name]["config"]
        execution = config["trade_execution"]
        sequence_tags = {step["tag"] for step in config["sequence"] if step.get("required")}

        assert execution["direction"] == direction
        assert execution["entry_type"] == "LIMIT"
        assert execution["entry_method"] == "ENTRY_PIVOT_LIMIT"
        assert execution["entry_value"] == "PIVOT"
        assert execution["size_mode"] == "RISK_FIXED_AMOUNT"
        assert execution["size_value"] > 0
        assert execution["sl"]["type"] == "PIVOT_POINT"
        assert execution["tp"]["type"] == "RR_RATIO"
        assert execution["trailing"]["type"] in {"SWING_LOW", "SWING_HIGH"}
        assert required_tag in sequence_tags
        assert exit_tag in execution["early_exits"]


@pytest.mark.asyncio
async def test_trend_cont_fvg_seed_declarations_match_runtime_contract(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    await seed_system_strategies(pool)

    for name, direction, required_tag, exit_tag in (
        ("TREND_CONT_FVG_BULL", "BUY", "choch_up", "choch_down"),
        ("TREND_CONT_FVG_BEAR", "SELL", "choch_down", "choch_up"),
    ):
        assert name in conn.templates
        assert conn.templates[name]["description"]
        assert "FVG" in conn.templates[name]["description"]
        config = conn.templates[name]["config"]
        execution = config["trade_execution"]
        sequence_tags = {step["tag"] for step in config["sequence"] if step.get("required")}

        assert execution["direction"] == direction
        assert execution["entry_type"] == "LIMIT"
        assert execution["entry_method"] == "ENTRY_FVG_FROM_CHOCH_PIVOT"
        assert execution["size_mode"] == "RISK_FIXED_AMOUNT"
        assert execution["size_value"] > 0
        assert execution["sl"]["type"] == "PIVOT_POINT"
        assert execution["tp"]["type"] == "RR_RATIO"
        assert execution["trailing"]["type"] in {"SWING_LOW", "SWING_HIGH"}
        assert required_tag in sequence_tags
        assert exit_tag in execution["early_exits"]

    assert conn.templates["TREND_CONT_BULL"]["config"]["trade_execution"]["entry_type"] == "MARKET"
    assert conn.templates["TREND_CONT_BULL"]["config"]["trade_execution"]["entry_method"] == "CURRENT"
    assert conn.templates["TREND_CONT_BEAR"]["config"]["trade_execution"]["entry_type"] == "MARKET"
    assert conn.templates["TREND_CONT_BEAR"]["config"]["trade_execution"]["entry_method"] == "CURRENT"


def test_trend_cont_bull_and_limit_bull_match_same_snapshot_before_executor(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    pool = FakePool(conn)

    asyncio.run(seed_system_strategies(pool))

    registry = StrategyRegistry()
    for name in ("TREND_CONT_BULL", "TREND_CONT_LIMIT_BULL"):
        config = dict(conn.templates[name]["config"])
        config["id"] = conn.templates[name]["id"]
        config["name"] = name
        config["min_score_threshold"] = conn.templates[name]["min_score"]
        assert registry.register(TemplateStrategy(config))

    state = SymbolState("XAUUSD")
    state.last_candle = {"c": 110.0}
    state.prev_candle = {"c": 105.0}
    state.tpo_profile = {"tpo_d0": {"POC": 100.0}, "tpo_d1": {"POC": 100.0}}
    state.transient_signals = {"cisd_h1_bullish": True}
    state.log_signal_normalize.append(
        {
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch_up", "price": 2400.0},
                ]
            },
        }
    )
    df = pd.DataFrame([{"t": 1000}])

    accepted = registry.evaluate_all(df, {}, state)
    accepted_by_name = {item["strategy"]: item for item in accepted}

    assert set(accepted_by_name) == {"TREND_CONT_BULL", "TREND_CONT_LIMIT_BULL"}
    assert accepted_by_name["TREND_CONT_BULL"]["side"] == "BUY"
    assert accepted_by_name["TREND_CONT_BULL"]["entry_type"] == "MARKET"
    assert accepted_by_name["TREND_CONT_BULL"]["order_plan"]["entry_method"] == "CURRENT"
    assert accepted_by_name["TREND_CONT_LIMIT_BULL"]["side"] == "BUY"
    assert accepted_by_name["TREND_CONT_LIMIT_BULL"]["entry_type"] == "LIMIT"
    assert accepted_by_name["TREND_CONT_LIMIT_BULL"]["order_plan"]["entry_method"] == "ENTRY_PIVOT_LIMIT"
    assert accepted_by_name["TREND_CONT_LIMIT_BULL"]["order_plan"]["entry_value"] == "PIVOT"
    assert registry.get_rejections() == []
    assert state.strategy_progress["TREND_CONT_BULL"]["triggered_t"] == 1000
    assert state.strategy_progress["TREND_CONT_LIMIT_BULL"]["triggered_t"] == 1000


def test_runbook_contract():
    repo_root = Path(__file__).resolve().parents[3]
    runbook = repo_root / ".planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md"
    assert runbook.exists(), "missing runbook"
    content = runbook.read_text(encoding="utf-8")

    assert "## Pre-check" in content
    assert "## Rollout" in content
    assert "## Rollback" in content

    assert "strategy_seed_sync_dryrun.py" in content
    assert "strategy_seed_sync_rollback.py --snapshot" in content
    assert "--apply" in content

