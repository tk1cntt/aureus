import pandas as pd
import pytest

from engine.signals.structure import StructureSignal
from engine.state import SymbolState


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"t": 1, "o": 1.0, "h": 1.2, "l": 0.9, "c": 1.1},
            {"t": 2, "o": 1.1, "h": 1.3, "l": 1.0, "c": 1.2},
            {"t": 3, "o": 1.2, "h": 1.4, "l": 1.1, "c": 1.3},
            {"t": 4, "o": 1.3, "h": 1.5, "l": 1.2, "c": 1.4},
            {"t": 5, "o": 1.4, "h": 1.6, "l": 1.3, "c": 1.5},
        ]
    )


@pytest.fixture
def sample_state() -> SymbolState:
    state = SymbolState("EURUSD")
    state.swing_points = [
        {"is_choch": False, "type": "HH", "is_high": True, "price": 1.0, "t": 1}
    ]
    state.transient_signals["x"] = {"tag": "x", "t": 5}
    state.obs.append({"top": 2.0, "bottom": 1.0, "ob_type": "BULLISH", "t_start": 1})
    return state


def test_shadow_compares_full_contract_fields() -> None:
    signal = StructureSignal()
    old_state = {
        "transient_signals": {"a": {"tag": "a", "t": 5}},
        "obs": [{"ob_type": "BULLISH", "top": 2.0, "bottom": 1.0}],
        "swing_points": [{"type": "HH", "t": 1}],
    }
    new_state = {
        "transient_signals": {"a": {"tag": "a", "t": 5}},
        "obs": [{"ob_type": "BULLISH", "top": 2.0, "bottom": 1.0}],
        "swing_points": [{"type": "HH", "t": 1}],
    }

    is_match, diff_fields = signal._compare_shadow_contract(old_state, new_state)

    assert is_match is True
    assert diff_fields == []


def test_shadow_mismatch_fallbacks_to_old(
    monkeypatch: pytest.MonkeyPatch, sample_df: pd.DataFrame, sample_state: SymbolState
) -> None:
    monkeypatch.setenv("AUREUS_STRUCTURE_OPT_MODE", "shadow")
    signal = StructureSignal()

    def fake_old(df, state_obj, **kwargs):
        return {"tag": "old", "t": 5, "value": "OLD"}

    def fake_new(df, state_obj, **kwargs):
        return {"tag": "new", "t": 5, "value": "NEW"}

    monkeypatch.setattr(signal, "_calculate_old_path", fake_old)
    monkeypatch.setattr(signal, "_calculate_optimized_path", fake_new)
    monkeypatch.setattr(signal, "_compare_shadow_contract", lambda old_s, new_s: (False, ["obs"]))

    result = signal.calculate(sample_df, sample_state)

    assert result == {"tag": "old", "t": 5, "value": "OLD"}


def test_on_mode_keeps_guard_fallback_when_mismatch(
    monkeypatch: pytest.MonkeyPatch, sample_df: pd.DataFrame, sample_state: SymbolState
) -> None:
    monkeypatch.setenv("AUREUS_STRUCTURE_OPT_MODE", "on")
    signal = StructureSignal()

    def fake_old(df, state_obj, **kwargs):
        return {"tag": "old", "t": 5, "value": "OLD"}

    def fake_new(df, state_obj, **kwargs):
        return {"tag": "new", "t": 5, "value": "NEW"}

    monkeypatch.setattr(signal, "_calculate_old_path", fake_old)
    monkeypatch.setattr(signal, "_calculate_optimized_path", fake_new)
    monkeypatch.setattr(signal, "_compare_shadow_contract", lambda old_s, new_s: (False, ["transient_signals"]))

    result = signal.calculate(sample_df, sample_state)

    assert result == {"tag": "old", "t": 5, "value": "OLD"}
