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
                "atr": 1.23,
                "ema_21": 3345.12,
                "ema_34": 3343.12,
                "ema_55": 3338.40,
                "ema_89": 3335.0,
                "ema_100": 3332.0,
                "ema_200": 3320.0,
                "vol_sma_20": 2000.0,
                "session": 2,
                "candle_color_d1": 1,
                "candle_color_h1": -1,
                "candle_color_m30": 1,
                "candle_color_m15": 1,
                "candle_color_m5": -1,
                "bb_m1_up": 3350.1,
                "bb_m1_dn": 3340.1,
                "bb_m5_up": 3360.1,
                "bb_m5_dn": 3330.1,
                "bb_m15_up": 3370.1,
                "bb_m15_dn": 3320.1,
                "bb_m30_up": 3380.1,
                "bb_m30_dn": 3310.1,
                "bb_h1_up": 3390.1,
                "bb_h1_dn": 3300.1,
                "cisd_m5": 1,
                "cisd_m15": -1,
                "cisd_m30": 1,
                "cisd_h1": -1,
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
        if "INSERT INTO removed_evaluation_table" in query:
            return "INSERT 0 1"
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_recompute_signal_snapshot_append_history_and_preserve_old_version():
    conn = MockConn()

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
    assert snapshot_inserts[0][1][8] == 3345.12
    assert snapshot_inserts[0][1][10] == 3338.40


@pytest.mark.asyncio
async def test_recompute_signal_snapshot_rerun_same_schema_version_is_idempotent():
    conn = MockConn()

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
