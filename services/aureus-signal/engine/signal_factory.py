"""
Signal Factory — Creates the full set of signal calculators for a symbol.
Shared between: live engine (main.py), signal_computer.py, and recovery (recalculate_all_signals).
"""
import logging
from typing import Any, Dict

from engine.signals.pivots import PivotSignal
from engine.signals.structure import StructureSignal
from engine.signals.volume_sma import VolumeSMASignal
from engine.signals.trend import TrendSignal
from engine.signals.session import SessionSignal
from engine.signals.choch_up import CHOCHUpSignal
from engine.signals.choch_down import CHOCHDownSignal
from engine.signals.sweep import SweepSignal
from engine.signals.sweep_bull import SweepBullSignal
from engine.signals.sweep_bear import SweepBearSignal
from engine.signals.ema import EMASignal

logger = logging.getLogger("aureus-signal.signal-factory")


def _missing_state(reason: str = "NOT_AVAILABLE") -> Dict[str, Any]:
    return {
        "status": "MISSING",
        "reason": reason,
    }


def _extract_signal_source(signal_obj: Any) -> Dict[str, Any]:
    if signal_obj is None:
        return _missing_state("SIGNAL_OBJECT_NOT_FOUND")

    params: Dict[str, Any] = {}
    for key, value in vars(signal_obj).items():
        if isinstance(value, (int, float, str, bool, type(None))):
            params[key] = value

    return {
        "status": "OK",
        "signal_class": signal_obj.__class__.__name__,
        "params": params,
    }


def build_normalized_signal_snapshot(signals: Dict[str, Any], state: Any = None) -> Dict[str, Any]:
    """
    Builds a normalized signal contract payload with mandatory top-level keys.

    Required keys:
      - zigzag_state
      - ob_state
      - choch_state
      - fvg_state
      - trend_filter_state
    """
    state = state or object()
    transient_signals = getattr(state, "transient_signals", {}) or {}

    zigzag_value = transient_signals.get("zigzag_state")
    ob_value = transient_signals.get("ob_state")
    choch_value = transient_signals.get("choch_state")
    fvg_value = transient_signals.get("fvg_state")
    trend_value = transient_signals.get("trend_filter_state")

    return {
        "zigzag_state": zigzag_value if zigzag_value is not None else {
            "status": "MISSING",
            "source": _extract_signal_source(signals.get("pivots")),
        },
        "ob_state": ob_value if ob_value is not None else {
            "status": "MISSING",
            "source": _extract_signal_source(signals.get("structure_processor")),
        },
        "choch_state": choch_value if choch_value is not None else {
            "status": "MISSING",
            "source": {
                "up": _extract_signal_source(signals.get("choch_up")),
                "down": _extract_signal_source(signals.get("choch_down")),
            },
        },
        "fvg_state": fvg_value if fvg_value is not None else _missing_state("FVG_NOT_IMPLEMENTED"),
        "trend_filter_state": trend_value if trend_value is not None else {
            "status": "MISSING",
            "source": _extract_signal_source(signals.get("trend")),
        },
    }


def create_signal_set(symbol: str, symbol_config: dict = None) -> dict:
    """
    Creates the full set of signal calculators for a given symbol.

    Args:
        symbol: Symbol name (e.g. "XAUUSD")
        symbol_config: Optional symbol-specific config dict from symbols.json.
                       If None, uses default params.
    Returns:
        Dict[str, BaseSignal] — tag -> signal calculator instance
    """
    logger.info(f"[{symbol}] [create_signal_set] 1... Creating signal set")
    cfg = symbol_config or {}

    # PivotSignal needs symbol-specific params
    p_cfg = cfg.get("pivots", {})
    pivots_sig = PivotSignal(
        ext_period=p_cfg.get("ext_period", 5),
        min_amplitude=p_cfg.get("min_amplitude", 100),
        min_amplitude_pct=p_cfg.get("min_amplitude_pct"),
        min_motion=p_cfg.get("min_motion", 1),
        point=cfg.get("point", 0.01),
        digits=cfg.get("digits", 2)
    )

    # ⚠️ CRITICAL: Order matters! "structure_processor" MUST be before outlet signals
    # (choch_up, choch_down) because it writes to transient_signals
    # which the outlets consume. Python 3.7+ guarantees dict insertion order.
    return {
        "vol_sma": VolumeSMASignal(20),
        "trend": TrendSignal(200),
        "session": SessionSignal(gmt_user=7),
        "pivots": pivots_sig,
        "structure_processor": StructureSignal(),
        "sweep_processor": SweepSignal(),
        "choch_up": CHOCHUpSignal(),
        "choch_down": CHOCHDownSignal(),
        "sweep_bull": SweepBullSignal(),
        "sweep_bear": SweepBearSignal(),
        "ema_21": EMASignal(21),
        "ema_34": EMASignal(34),
        "ema_55": EMASignal(55),
        "ema_89": EMASignal(89),
        "ema_100": EMASignal(100),
        "ema_200": EMASignal(200),
    }
