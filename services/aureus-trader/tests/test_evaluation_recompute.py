import pytest

from recompute_evaluations import recompute_batch


class MockConn:
    def __init__(self):
        self.fetch_calls = []
        self.execute_calls = []
        self.inserted_eval = set()

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return [
            {
                "id": 101,
                "trace_id": "tr-55-001",
                "ticket": 123456789,
                "strategy_name": "chandelier_breakout",
                "symbol": "XAUUSD",
                "timeframe": "M5",
                "score_breakdown": {"criteria": {"signal_quality": 0.8}},
            }
        ]

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        if "INSERT INTO aureus_trade_evaluations" in query:
            key = (args[0], args[3])
            if key in self.inserted_eval:
                return "INSERT 0 0"
            self.inserted_eval.add(key)
            return "INSERT 0 1"
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_recompute_evaluation_append_history_and_flip_is_current(monkeypatch):
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

    assert stats["evaluation_inserted"] == 1
    eval_inserts = [q for q in conn.execute_calls if "INSERT INTO aureus_trade_evaluations" in q[0]]
    assert len(eval_inserts) == 1
    assert eval_inserts[0][1][3] == "scor-v1.1.0"

    demote_updates = [q for q in conn.execute_calls if "SET is_current = FALSE" in q[0]]
    promote_updates = [q for q in conn.execute_calls if "SET is_current = TRUE" in q[0]]
    assert len(demote_updates) == 1
    assert len(promote_updates) == 1


@pytest.mark.asyncio
async def test_recompute_evaluation_rerun_same_version_is_idempotent(monkeypatch):
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

    assert first["evaluation_inserted"] == 1
    assert second["evaluation_inserted"] == 0
