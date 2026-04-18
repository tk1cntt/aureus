import copy
import os
import sys
import time
from typing import Any, Dict, List

import pandas as pd
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.signals.structure import StructureSignal
from engine.state import SymbolState


SYMBOL = "EURUSD"
BASE_T = 1700000000


def _build_replay_df(size: int = 1800) -> pd.DataFrame:
    rows: List[Dict[str, float]] = []
    for i in range(size):
        t = BASE_T + (i * 60)
        base = 1.10 + (i % 17) * 0.0001
        high = base + 0.0009 + ((i % 5) * 0.00005)
        low = base - 0.0009 - ((i % 7) * 0.00004)
        close = base + (((i % 9) - 4) * 0.00007)
        rows.append(
            {
                "t": t,
                "o": base,
                "h": high,
                "l": low,
                "c": close,
            }
        )
    return pd.DataFrame(rows)


def _build_state(df: pd.DataFrame) -> SymbolState:
    state = SymbolState(SYMBOL)
    points = []
    for i in range(30, len(df), 30):
        row = df.iloc[i]
        points.append(
            {
                "t": int(row["t"]),
                "price": float(row["h"] if (i // 30) % 2 == 0 else row["l"]),
                "type": "HH" if (i // 30) % 2 == 0 else "LL",
                "is_high": (i // 30) % 2 == 0,
                "is_choch": False,
            }
        )
    state.swing_points = points
    return state


def _snapshot_contract(state: SymbolState, result: Dict[str, Any] | None) -> Dict[str, Any]:
    return {
        "transient_signals": copy.deepcopy(state.transient_signals),
        "obs": copy.deepcopy(state.obs),
        "swing_points": copy.deepcopy(state.swing_points),
        "result": copy.deepcopy(result),
    }


def _run_and_measure(signal: StructureSignal, fn_name: str, df: pd.DataFrame, loops: int = 6):
    timings: List[float] = []
    final_contract = None
    for _ in range(loops):
        state = _build_state(df)
        fn = getattr(signal, fn_name)
        started = time.perf_counter()
        result = fn(df, state)
        timings.append((time.perf_counter() - started) * 1000)
        final_contract = _snapshot_contract(state, result)
    return sum(timings) / len(timings), final_contract


def _find_diff_fields(old_contract: Dict[str, Any], new_contract: Dict[str, Any]) -> List[str]:
    fields = ["transient_signals", "obs", "swing_points", "result"]
    return [f for f in fields if old_contract.get(f) != new_contract.get(f)]


def test_replay_parity_full_contract_identical() -> None:
    df = _build_replay_df()
    signal = StructureSignal()

    _, old_contract = _run_and_measure(signal, "_calculate_old_path", df)
    _, new_contract = _run_and_measure(signal, "_calculate_optimized_path", df)

    diff_fields = _find_diff_fields(old_contract, new_contract)
    assert diff_fields == [], (
        f"Parity mismatch symbol={SYMBOL} t={int(df.iloc[-1]['t'])} diff_fields={diff_fields}"
    )


def test_replay_perf_gate_optimized_must_reduce_40_percent() -> None:
    df = _build_replay_df()
    signal = StructureSignal()

    old_avg_ms, _ = _run_and_measure(signal, "_calculate_old_path", df)
    new_avg_ms, _ = _run_and_measure(signal, "_calculate_optimized_path", df)

    assert new_avg_ms <= old_avg_ms * 0.60, (
        f"Perf gate failed symbol={SYMBOL} t={int(df.iloc[-1]['t'])} "
        f"old_avg_ms={old_avg_ms:.3f} optimized_avg_ms={new_avg_ms:.3f} "
        f"required_max={old_avg_ms * 0.60:.3f}"
    )


def test_replay_mismatch_reports_symbol_time_and_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    df = _build_replay_df(300)
    signal = StructureSignal()

    original = signal._calculate_optimized_path

    def _drifted(df_arg, state_arg, **kwargs):
        result = original(df_arg, state_arg, **kwargs)
        state_arg.transient_signals["forced_drift"] = {"tag": "forced", "t": int(df_arg.iloc[-1]["t"])}
        return result

    monkeypatch.setattr(signal, "_calculate_optimized_path", _drifted)

    _, old_contract = _run_and_measure(signal, "_calculate_old_path", df, loops=1)
    _, new_contract = _run_and_measure(signal, "_calculate_optimized_path", df, loops=1)
    diff_fields = _find_diff_fields(old_contract, new_contract)

    assert diff_fields == [], (
        f"Parity mismatch symbol={SYMBOL} t={int(df.iloc[-1]['t'])} diff_fields={diff_fields}"
    )
