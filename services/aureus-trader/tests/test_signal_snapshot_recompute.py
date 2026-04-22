import json

import pytest

from recompute_evaluations import recompute_batch


class MockConn:
    def __init__(self):
        self.execute_calls = []
        self.inserted_snapshots = set()

    async def fetch(self, query, *args):
        return [
            {
                "id": 101,
                "trace_id": "tr-55-001",
                "ticket": 123456789,
                "strategy_name": "chandelier_breakout",
                "symbol": "XAUUSD",
                "timeframe": "M5",
                "signal_snapshot": {"cisd_direction": "bull", "ema_21": 3345.12, "ema_55": 3338.40},
                "cisd_direction": "bull",
                "ema21": 3345.12,
                "ema55": 3338.40,
                "created_at": "2026-04-01T00:00:00Z",
                "score_breakdown": {"criteria": {"signal_quality": 0.8}},
            }
        ]

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        if "INSERT INTO aureus_trade_signal_snapshots" in query:
            key = (args[0], args[6])
            if key in self.inserted_snapshots:
                return "INSERT 0 0"
            self.inserted_snapshots.add(key)
            return "INSERT 0 1"
        if "INSERT INTO aureus_trade_evaluations" in query:
            return "INSERT 0 1"
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_recompute_signal_snapshot_append_history_and_preserve_old_version(monkeypatch):
    conn = MockConn()

    def fake_compute_trade_score(input_payload, score_version, weights_snapshot):
        return {
            "score_total": 0.812345,
            "criteria": [{"name": "signal_quality", "normalized": 0.8}],
            "weights_snapshot": weights_snapshot,
            "missing_data_policy": "impute_neutral_and_flag",
        }

    monkeypatch.setattr("recompute_evaluations.compute_trade_score", fake_compute_trade_score)

    weights = {
        "profit_outcome": 0.30,
        "signal_quality": 0.35,
        "timing_quality": 0.20,
        "volatility_session": 0.15,
    }

    stats = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=weights,
    )

    assert stats["signal_snapshot_inserted"] == 1
    snapshot_inserts = [q for q in conn.execute_calls if "INSERT INTO aureus_trade_signal_snapshots" in q[0]]
    assert len(snapshot_inserts) == 1
    assert snapshot_inserts[0][1][5] == "M5"
    assert snapshot_inserts[0][1][6] == "sig-v1.1.0"
    assert json.loads(snapshot_inserts[0][1][7])["cisd_direction"] == "bull"
    assert snapshot_inserts[0][1][9] == 3345.12
    assert snapshot_inserts[0][1][10] == 3338.40
    assert snapshot_inserts[0][1][11] == "2026-04-01T00:00:00Z"


@pytest.mark.asyncio
async def test_recompute_signal_snapshot_rerun_same_schema_version_is_idempotent(monkeypatch):
    conn = MockConn()

    def fake_compute_trade_score(input_payload, score_version, weights_snapshot):
        return {
            "score_total": 0.812345,
            "criteria": [{"name": "signal_quality", "normalized": 0.8}],
            "weights_snapshot": weights_snapshot,
            "missing_data_policy": "impute_neutral_and_flag",
        }

    monkeypatch.setattr("recompute_evaluations.compute_trade_score", fake_compute_trade_score)

    weights = {
        "profit_outcome": 0.30,
        "signal_quality": 0.35,
        "timing_quality": 0.20,
        "volatility_session": 0.15,
    }

    first = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=weights,
    )
    second = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=weights,
    )

    assert first["signal_snapshot_inserted"] == 1
    assert second["signal_snapshot_inserted"] == 0
