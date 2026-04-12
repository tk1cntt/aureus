"""Tests for SignalType enum and classification on all signal classes."""
from engine.signals.base import SignalType, BaseSignal
from engine.signals.ema import EMASignal
from engine.signals.atr import ATRSignal
from engine.signals.volume_sma import VolumeSMASignal
from engine.signals.trend import TrendSignal
from engine.signals.session import SessionSignal
from engine.signals.pivots import PivotSignal
from engine.signals.structure import StructureSignal
from engine.signals.sweep import SweepSignal
from engine.signals.fvg import FVGSignal
from engine.signals.fvg_up import FVGUpSignal
from engine.signals.fvg_down import FVGDownSignal
from engine.signals.choch_up import CHOCHUpSignal
from engine.signals.choch_down import CHOCHDownSignal
from engine.signals.sweep_bull import SweepBullSignal
from engine.signals.sweep_bear import SweepBearSignal
import pytest


def test_signal_type_enum_values():
    """Verify SignalType has correct string values."""
    assert SignalType.INDICATOR.value == "indicator"
    assert SignalType.EVENT.value == "event"


def test_base_signal_defaults_to_indicator():
    """Verify BaseSignal.signal_type defaults to INDICATOR (D-02 safe default)."""
    assert BaseSignal.signal_type == SignalType.INDICATOR
    assert BaseSignal.get_signal_type() == SignalType.INDICATOR


# INDICATOR signals (D-03)
@pytest.mark.parametrize("cls", [
    EMASignal, ATRSignal, VolumeSMASignal,
    TrendSignal, SessionSignal, PivotSignal,
])
def test_indicator_signals(cls):
    """Verify indicator signals return INDICATOR."""
    assert cls.get_signal_type() == SignalType.INDICATOR, f"{cls.__name__} should be INDICATOR"


# EVENT signals (D-03)
@pytest.mark.parametrize("cls", [
    StructureSignal, SweepSignal, FVGSignal,
    FVGUpSignal, FVGDownSignal, CHOCHUpSignal,
    CHOCHDownSignal, SweepBullSignal, SweepBearSignal,
])
def test_event_signals(cls):
    """Verify event signals return EVENT."""
    assert cls.get_signal_type() == SignalType.EVENT, f"{cls.__name__} should be EVENT"


def test_all_15_signal_classes_classified():
    """Verify total count: 6 indicators + 9 events = 15 signal classes."""
    indicator_classes = [EMASignal, ATRSignal, VolumeSMASignal, TrendSignal, SessionSignal, PivotSignal]
    event_classes = [StructureSignal, SweepSignal, FVGSignal, FVGUpSignal, FVGDownSignal, CHOCHUpSignal, CHOCHDownSignal, SweepBullSignal, SweepBearSignal]
    for cls in indicator_classes:
        assert cls.get_signal_type() == SignalType.INDICATOR
    for cls in event_classes:
        assert cls.get_signal_type() == SignalType.EVENT
    assert len(indicator_classes) == 6
    assert len(event_classes) == 9


def test_signal_type_not_breaking_calculate_signature():
    """Verify backward compatibility: signal_type attribute does not break calculate() instantiation (D-04)."""
    ema = EMASignal(21)
    assert ema.signal_type == SignalType.INDICATOR
    assert hasattr(ema, 'calculate')
    assert callable(ema.calculate)
