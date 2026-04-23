import pytest

from recompute_evaluations import recompute_batch


class CaptureWarningLogger:
    def __init__(self):
        self.calls = []

    def warning(self, message, *args):
        self.calls.append((message, args))


class MockConn:
    def __init__(self, rows=None):
        self.fetch_calls = []
        self.execute_calls = []
        self.inserted_eval = set()
        self.rows = rows or [
            {
                "id": 101,
                "trace_id": "tr-55-001",
                "ticket": 123456789,
                "strategy_name": "chandelier_breakout",
                "symbol": "XAUUSD",
                "lineage_timeframe": "M5",
                "journal_timeframe": "M15",
                "snapshot_timeframe": "H1",
                "signal_snapshot": {},
                "cisd_direction": None,
                "ema21": None,
                "ema55": None,
                "created_at": None,
                "score_breakdown": {"criteria": {"signal_quality": 0.8}},
            }
        ]

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self.rows

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        if "INSERT INTO aureus_trade_evaluations" in query:
            key = (args[0], args[3])
            if key in self.inserted_eval:
                return "INSERT 0 0"
            self.inserted_eval.add(key)
            return "INSERT 0 1"
        if "INSERT INTO aureus_trade_signal_snapshots" in query:
            return "INSERT 0 1"
        return "UPDATE 1"


def _fake_compute_trade_score(input_payload, score_version, weights_snapshot):
    return {
        "score_total": 0.812345,
        "criteria": [{"name": "signal_quality", "normalized": 0.8}],
        "weights_snapshot": weights_snapshot,
        "missing_data_policy": "impute_neutral_and_flag",
    }


def _weights():
    return {
        "profit_outcome": 0.30,
        "signal_quality": 0.35,
        "timing_quality": 0.20,
        "volatility_session": 0.15,
    }


@pytest.mark.asyncio
async def test_recompute_prefers_canonical_lineage_timeframe(monkeypatch):
    conn = MockConn()
    monkeypatch.setattr("recompute_evaluations.compute_trade_score", _fake_compute_trade_score)
    warning_logger = CaptureWarningLogger()
    monkeypatch.setattr("recompute_evaluations.logger", warning_logger)

    stats = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=_weights(),
    )

    assert stats["evaluation_inserted"] == 1
    eval_inserts = [q for q in conn.execute_calls if "INSERT INTO aureus_trade_evaluations" in q[0]]
    assert eval_inserts[0][1][10] == "M5"
    assert warning_logger.calls == []


@pytest.mark.asyncio
async def test_recompute_fallback_emits_structured_warning(monkeypatch):
    conn = MockConn(
        rows=[
            {
                "id": 202,
                "trace_id": "tr-55-fallback",
                "ticket": 123456789,
                "strategy_name": "chandelier_breakout",
                "symbol": "XAUUSD",
                "lineage_timeframe": None,
                "journal_timeframe": None,
                "snapshot_timeframe": None,
                "signal_snapshot": {},
                "cisd_direction": None,
                "ema21": None,
                "ema55": None,
                "created_at": None,
                "score_breakdown": {"criteria": {"signal_quality": 0.8}},
            }
        ]
    )
    monkeypatch.setattr("recompute_evaluations.compute_trade_score", _fake_compute_trade_score)
    warning_logger = CaptureWarningLogger()
    monkeypatch.setattr("recompute_evaluations.logger", warning_logger)

    stats = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=_weights(),
    )

    assert stats["evaluation_inserted"] == 1
    eval_inserts = [q for q in conn.execute_calls if "INSERT INTO aureus_trade_evaluations" in q[0]]
    assert eval_inserts[0][1][10] == "M1"

    rendered = [msg % args if args else msg for msg, args in warning_logger.calls]
    assert any("TIMEFRAME_LINEAGE_FALLBACK" in msg for msg in rendered)
    assert any("trace_id=tr-55-fallback" in msg for msg in rendered)
    assert any("trade_journal_id=202" in msg for msg in rendered)
    assert any("fallback_source=default_M1" in msg for msg in rendered)


@pytest.mark.asyncio
async def test_recompute_evaluation_append_history_and_flip_is_current(monkeypatch):
    conn = MockConn()
    monkeypatch.setattr("recompute_evaluations.compute_trade_score", _fake_compute_trade_score)

    stats = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=_weights(),
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
    monkeypatch.setattr("recompute_evaluations.compute_trade_score", _fake_compute_trade_score)

    first = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=_weights(),
    )
    second = await recompute_batch(
        conn=conn,
        score_version="scor-v1.1.0",
        signal_schema_version="sig-v1.1.0",
        start="2026-04-01T00:00:00Z",
        end="2026-04-30T23:59:59Z",
        batch_size=500,
        weights_snapshot=_weights(),
    )

    assert first["evaluation_inserted"] == 1
    assert second["evaluation_inserted"] == 0
