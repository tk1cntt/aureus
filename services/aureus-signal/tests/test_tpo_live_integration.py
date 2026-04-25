import os
import sys
from types import SimpleNamespace

import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.live_engine import _maybe_emit_tpo_strategy_tags
from engine.signal_factory import create_signal_set
from engine.signals.tpo import TPOSignal


def _tpo_value():
    return {
        "tpo_d1": {"POC": 100.0, "VAH": 110.0, "VAL": 90.0, "shape": "D", "shape_confidence_pct": 80.0},
        "tpo_h1": {"POC": 100.0, "VAH": 106.0, "VAL": 96.0, "shape": "b", "shape_confidence_pct": 80.0},
        "tpo_m30": {"POC": 101.0, "VAH": 107.0, "VAL": 97.0, "shape": "D", "shape_confidence_pct": 80.0},
    }


def test_live_tpo_raw_profile_emits_strategy_transient_tag():
    state = SimpleNamespace(transient_signals={})
    df = pd.DataFrame({"t": [1, 2], "c": [95.5, 96.5]})

    _maybe_emit_tpo_strategy_tags(_tpo_value(), df, state, "BTCUSD")

    assert "tpo_va_breakout_bear" in state.transient_signals
    assert state.transient_signals["tpo_va_breakout_bear"]["category"] == "tpo_strategy"


def test_tpo_signal_caps_large_level_count():
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.01)
    sig.max_levels = 100
    df = pd.DataFrame(
        {
            "t": [1, 2],
            "o": [100.0, 100.0],
            "h": [200.0, 200.0],
            "l": [100.0, 100.0],
            "c": [150.0, 150.0],
            "v": [1, 1],
        }
    )

    levels, counts = sig._build_levels_and_counts(df)

    assert len(levels) == 100
    assert len(counts) == 100
    assert sum(counts) > 0


def test_tpo_uses_symbol_specific_tick_floor_for_large_range():
    btc_sig = TPOSignal(value_area_pct=0.7, tick_size=0.01, symbol="BTCUSD")
    fx_sig = TPOSignal(value_area_pct=0.7, tick_size=0.01, symbol="EURUSD")
    btc_sig.max_levels = 5000
    fx_sig.max_levels = 5000

    assert btc_sig._effective_tick_size(80000.0, 79000.0, symbol="BTCUSD") == 1.0
    assert fx_sig._effective_tick_size(1.2, 1.1, symbol="EURUSD") == 0.01


def test_create_signal_set_passes_symbol_to_tpo(monkeypatch):
    monkeypatch.setenv("AUREUS_ENABLE_TPO_SIGNAL", "1")

    signals = create_signal_set("BTCUSD", {"point": 0.01})

    assert signals["tpo"].symbol == "BTCUSD"


def test_create_signal_set_can_disable_tpo(monkeypatch):
    monkeypatch.setenv("AUREUS_ENABLE_TPO_SIGNAL", "0")

    signals = create_signal_set("BTCUSD", {"point": 0.01})

    assert "tpo" not in signals
