import asyncio
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.strategies.seed_strategies import seed_system_strategies
from engine.strategies.template import TemplateStrategy


class FakeConn:
    def __init__(self):
        self.templates = {}
        self.assignments = {}

    async def execute(self, query, *args):
        normalized = " ".join(query.split())
        if "INSERT INTO aureus_strategy_templates" in normalized:
            name, description, config_raw, min_score = args
            template_id = self.templates.get(name, {}).get("id", len(self.templates) + 1)
            import json
            self.templates[name] = {
                "id": template_id,
                "name": name,
                "description": description,
                "config": json.loads(config_raw),
                "min_score": min_score,
            }
            return "INSERT 0 1"
        if "INSERT INTO aureus_symbol_strategies" in normalized:
            symbol, strategy_id = args
            self.assignments[(symbol, strategy_id)] = {"symbol": symbol, "strategy_id": strategy_id, "is_active": True}
            return "INSERT 0 1"
        if "UPDATE aureus_symbol_strategies" in normalized:
            return "UPDATE 0"
        raise AssertionError(f"Unsupported execute query: {normalized}")

    async def fetch(self, query, *args):
        normalized = " ".join(query.split())
        if "SELECT id, name FROM aureus_strategy_templates WHERE name = ANY($1::text[])" in normalized:
            names = set(args[0])
            return [{"id": item["id"], "name": name} for name, item in self.templates.items() if name in names]
        if "SELECT ss.symbol, t.id as strategy_id, t.name as strategy_name" in normalized:
            return []
        raise AssertionError(f"Unsupported fetch query: {normalized}")


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


class MockState:
    def __init__(self):
        self.signal_history = []
        self.log_signal_normalize = []
        self.strategy_progress = {}
        self.symbol = "XAUUSD"


def _df(t_val):
    return pd.DataFrame([{"t": t_val}])


def _append_event(state, t_val, tag):
    state.log_signal_normalize.append({"t": t_val, "signals": {"events": [{"tag": tag}]}})


def _seeded_strategy(name, monkeypatch):
    monkeypatch.setenv("SYMBOLS", "XAUUSD")
    conn = FakeConn()
    asyncio.run(seed_system_strategies(FakePool(conn)))
    template = conn.templates[name]
    config = dict(template["config"])
    config["id"] = template["id"]
    config["name"] = name
    config["min_score_threshold"] = template["min_score"]
    return TemplateStrategy(config), config


def _assert_two_step_runtime(name, first_tag, second_tag, wrong_tag, direction, entry_method, sl_type, early_exit, monkeypatch):
    strategy, config = _seeded_strategy(name, monkeypatch)

    assert config["sequence"] == [
        {"tag": first_tag, "weight": 4.0, "required": True, "max_wait": 30},
        {"tag": second_tag, "weight": 4.0, "required": True, "max_wait": 30},
    ]
    execution = config["trade_execution"]
    assert execution["direction"] == direction
    assert execution["entry_type"] == "LIMIT"
    assert execution["entry_method"] == entry_method
    assert execution["sl"]["type"] == sl_type
    assert execution["early_exits"] == [early_exit]

    state = MockState()
    _append_event(state, 1000, first_tag)
    assert strategy.evaluate(_df(1000), {}, state) is None

    _append_event(state, 1060, second_tag)
    intent = strategy.on_bar_close({"df": _df(1060), "state": state, "backfill_status": "READY"})
    assert intent["reason_code"] == "OK"
    assert intent["is_actionable"] is True
    order_plan = strategy.build_order_plan(intent, {})
    assert order_plan["direction"] == direction
    assert order_plan["entry_type"] == "LIMIT"
    assert order_plan["entry_method"] == entry_method
    assert order_plan["sl"]["type"] == sl_type
    assert order_plan["early_exits"] == [early_exit]

    strategy_missing, _ = _seeded_strategy(name, monkeypatch)
    state_missing = MockState()
    _append_event(state_missing, 1000, first_tag)
    _append_event(state_missing, 1060, "noise")
    assert strategy_missing.evaluate(_df(1060), {}, state_missing) is None

    strategy_wrong, _ = _seeded_strategy(name, monkeypatch)
    state_wrong = MockState()
    _append_event(state_wrong, 1000, first_tag)
    _append_event(state_wrong, 1060, wrong_tag)
    assert strategy_wrong.evaluate(_df(1060), {}, state_wrong) is None


def test_fz_cont_bull_seed_config_and_runtime(monkeypatch):
    _assert_two_step_runtime(
        name="FZ_CONT_BULL",
        first_tag="choch_up",
        second_tag="bos_up",
        wrong_tag="bos_down",
        direction="BUY",
        entry_method="FIRST_HIGH_LOW_PIVOT",
        sl_type="SECOND_HIGH_LOW_PIVOT",
        early_exit="choch_down",
        monkeypatch=monkeypatch,
    )


def test_fz_cont_bear_seed_config_and_runtime(monkeypatch):
    _assert_two_step_runtime(
        name="FZ_CONT_BEAR",
        first_tag="choch_down",
        second_tag="bos_down",
        wrong_tag="bos_up",
        direction="SELL",
        entry_method="FIRST_LOW_HIGH_PIVOT",
        sl_type="SECOND_LOW_HIGH_PIVOT",
        early_exit="choch_up",
        monkeypatch=monkeypatch,
    )
