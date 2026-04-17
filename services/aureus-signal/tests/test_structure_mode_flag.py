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
    return state


@pytest.mark.parametrize("mode", ["off", "shadow", "on"])
def test_mode_accepts_whitelist(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("AUREUS_STRUCTURE_OPT_MODE", mode)
    signal = StructureSignal()

    assert signal._get_structure_opt_mode() == mode


def test_mode_invalid_falls_back_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUREUS_STRUCTURE_OPT_MODE", "invalid")
    signal = StructureSignal()

    assert signal._get_structure_opt_mode() == "off"


def test_mode_missing_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUREUS_STRUCTURE_OPT_MODE", raising=False)
    signal = StructureSignal()

    assert signal._get_structure_opt_mode() == "off"


def test_mode_off_runs_old_path_only(
    monkeypatch: pytest.MonkeyPatch, sample_df: pd.DataFrame, sample_state: SymbolState
) -> None:
    monkeypatch.setenv("AUREUS_STRUCTURE_OPT_MODE", "off")
    signal = StructureSignal()

    calls = {"old": 0, "new": 0}

    def fake_old(df, state_obj, **kwargs):
        calls["old"] += 1
        return {"tag": "old", "t": 5}

    def fake_new(df, state_obj, **kwargs):
        calls["new"] += 1
        return {"tag": "new", "t": 5}

    monkeypatch.setattr(signal, "_calculate_old_path", fake_old)
    monkeypatch.setattr(signal, "_calculate_optimized_path", fake_new)

    result = signal.calculate(sample_df, sample_state)

    assert result == {"tag": "old", "t": 5}
    assert calls == {"old": 1, "new": 0}
