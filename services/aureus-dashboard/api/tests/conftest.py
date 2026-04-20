import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from main import app
import main as main_module


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value


class FakeConn:
    def __init__(self, trades, snapshots):
        self.trades = trades
        self.snapshots = snapshots

    async def fetchval(self, query, status, symbol, strategy_id, start_dt, end_dt):
        rows = self._filter_trades(status, symbol, strategy_id, start_dt, end_dt)
        return len(rows)

    async def fetch(self, query, *args):
        q = " ".join(query.lower().split())

        if "from aureus_trades" in q and "count(*)" not in q and "limit" in q:
            status, symbol, strategy_id, start_dt, end_dt, page_size, page = args
            rows = self._filter_trades(status, symbol, strategy_id, start_dt, end_dt)
            rows = sorted(rows, key=lambda x: x["filled_at"], reverse=True)
            offset = (page - 1) * page_size
            return rows[offset:offset + page_size]

        if "from aureus_trades" in q and "sum(profit) over" in q:
            start_dt, end_dt = args
            rows = [r for r in self.trades if r["status"] == "CLOSED"]
            rows = [r for r in rows if (start_dt is None or r["filled_at"] >= start_dt) and (end_dt is None or r["filled_at"] <= end_dt)]
            rows = sorted(rows, key=lambda x: x["filled_at"])
            cumulative = 0.0
            out = []
            for r in rows:
                cumulative += float(r["profit"])
                out.append({"time": r["filled_at"], "cumulative_pnl": cumulative})
            return out

        if "from aureus_trades" in q and "select profit, filled_at" in q:
            symbol, strategy_id, start_dt, end_dt = args
            rows = self._filter_trades("CLOSED", symbol, strategy_id, start_dt, end_dt)
            rows = sorted(rows, key=lambda x: x["filled_at"])
            return [{"profit": r["profit"], "filled_at": r["filled_at"]} for r in rows]

        if "from aureus_account_snapshots" in q:
            start_dt, end_dt = args
            return [
                r
                for r in self.snapshots
                if (start_dt is None or r["event_time"] >= start_dt)
                and (end_dt is None or r["event_time"] <= end_dt)
            ]

        return []

    async def fetchrow(self, query, symbol, strategy_id, start_dt, end_dt):
        rows = self._filter_trades("CLOSED", symbol, strategy_id, start_dt, end_dt)
        if not rows:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "net_pnl": 0,
                "gross_profit": 0,
                "gross_loss": 0,
                "avg_rr": None,
                "avg_profit": 0,
            }

        wins = len([r for r in rows if r["profit"] > 0])
        losses = len([r for r in rows if r["profit"] <= 0])
        net_pnl = sum(float(r["profit"]) for r in rows)
        gross_profit = sum(float(r["profit"]) for r in rows if r["profit"] > 0)
        gross_loss = abs(sum(float(r["profit"]) for r in rows if r["profit"] < 0))
        avg_profit = net_pnl / len(rows)
        avg_rr_values = []
        for r in rows:
            risk = abs(float(r["entry_price"]) - float(r["sl"]))
            if risk <= 0:
                risk = 0.01
            if r["direction"] == "BUY":
                reward = float(r["exit_price"]) - float(r["entry_price"])
            else:
                reward = float(r["entry_price"]) - float(r["exit_price"])
            avg_rr_values.append(reward / risk)

        avg_rr = sum(avg_rr_values) / len(avg_rr_values) if avg_rr_values else None

        return {
            "total_trades": len(rows),
            "wins": wins,
            "losses": losses,
            "net_pnl": net_pnl,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "avg_rr": avg_rr,
            "avg_profit": avg_profit,
        }

    def _filter_trades(self, status, symbol, strategy_id, start_dt, end_dt):
        rows = [r for r in self.trades if r["status"] == status]
        if symbol is not None:
            rows = [r for r in rows if r["symbol"] == symbol]
        if strategy_id is not None:
            rows = [r for r in rows if r["strategy_id"] == strategy_id]
        if start_dt is not None:
            rows = [r for r in rows if r["filled_at"] >= start_dt]
        if end_dt is not None:
            rows = [r for r in rows if r["filled_at"] <= end_dt]
        return rows


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, trades, snapshots):
        self.conn = FakeConn(trades, snapshots)

    def acquire(self):
        return _Acquire(self.conn)


@pytest.fixture
def deterministic_data():
    tz = timezone.utc
    trades = [
        {
            "id": 1,
            "trace_id": "t-1",
            "ticket": 1001,
            "symbol": "XAUUSD",
            "strategy_id": 10,
            "strategy_name": "MeanReversion",
            "direction": "BUY",
            "entry_price": 2000.0,
            "exit_price": 2002.0,
            "sl": 1998.0,
            "tp": 2004.0,
            "volume": 0.1,
            "profit": 20.0,
            "commission": -0.5,
            "swap": -0.1,
            "filled_at": datetime(2026, 1, 1, 10, 0, tzinfo=tz),
            "closed_at": datetime(2026, 1, 1, 11, 0, tzinfo=tz),
            "status": "CLOSED",
        },
        {
            "id": 2,
            "trace_id": "t-2",
            "ticket": 1002,
            "symbol": "XAUUSD",
            "strategy_id": 10,
            "strategy_name": "MeanReversion",
            "direction": "SELL",
            "entry_price": 2003.0,
            "exit_price": 2005.0,
            "sl": 2006.0,
            "tp": 2000.0,
            "volume": 0.1,
            "profit": -15.0,
            "commission": -0.5,
            "swap": -0.1,
            "filled_at": datetime(2026, 1, 1, 12, 0, tzinfo=tz),
            "closed_at": datetime(2026, 1, 1, 13, 0, tzinfo=tz),
            "status": "CLOSED",
        },
        {
            "id": 3,
            "trace_id": "t-3",
            "ticket": 1003,
            "symbol": "XAUUSD",
            "strategy_id": 20,
            "strategy_name": "Breakout",
            "direction": "BUY",
            "entry_price": 2001.0,
            "exit_price": 2004.0,
            "sl": 1999.0,
            "tp": 2008.0,
            "volume": 0.2,
            "profit": 30.0,
            "commission": -0.5,
            "swap": -0.1,
            "filled_at": datetime(2026, 1, 2, 9, 0, tzinfo=tz),
            "closed_at": datetime(2026, 1, 2, 10, 0, tzinfo=tz),
            "status": "CLOSED",
        },
    ]

    snapshots = [
        {
            "event_time": datetime(2026, 1, 1, 10, 0, tzinfo=tz),
            "equity": 10020.0,
            "realized_pnl": 20.0,
            "unrealized_pnl": 0.0,
        },
        {
            "event_time": datetime(2026, 1, 1, 12, 0, tzinfo=tz),
            "equity": 10005.0,
            "realized_pnl": 5.0,
            "unrealized_pnl": 0.0,
        },
        {
            "event_time": datetime(2026, 1, 2, 9, 0, tzinfo=tz),
            "equity": 10035.0,
            "realized_pnl": 35.0,
            "unrealized_pnl": 0.0,
        },
    ]

    return {"trades": trades, "snapshots": snapshots}


@pytest.fixture
def client(deterministic_data):
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    app.state.pg_pool = FakePool(deterministic_data["trades"], deterministic_data["snapshots"])
    main_module.redis_client = FakeRedis()

    with TestClient(app) as test_client:
        yield test_client
