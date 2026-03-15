"""
Event Filter — logic to decide if a snapshot should be persisted.
Reduces DB writes by targeting only significant market or trade events.

Shared between Live Engine V2 and Backtest V5.
"""
import logging
from typing import Any

logger = logging.getLogger("aureus.event-filter")

# Structural signal tags that trigger a snapshot write.
# These correspond to transient_signals keys emitted by:
#   - structure.py: choch_up/down, ob_bull/bear_new/mitigated
#   - fvg.py: fvg_bull/bear_new/mitigated
#   - sweep.py: sweep_bull/bear
STRUCTURAL_TAGS = {
    "choch_up", "choch_down",
    "sweep_bull", "sweep_bear",
    "fvg_bull_new", "fvg_bear_new",
    "fvg_bull_mitigated", "fvg_bear_mitigated",
    "ob_bull_new", "ob_bear_new",
    "ob_bull_mitigated", "ob_bear_mitigated"
}

# Trade lifecycle events that trigger a snapshot write.
# These correspond to last_tick_events on the TradeManager.
TRADE_EVENT_TAGS = {
    "ORDER_OPENED",
    "SL_HIT",
    "TP_HIT"
}


def has_structural_event(c_state: Any, trade_manager: Any) -> bool:
    """
    Checks if the current tick has a significant event that warrants a DB snapshot.

    Args:
        c_state: SymbolState object with transient_signals dict.
        trade_manager: TradeManager (Live or Simulated) with last_tick_events list.

    Returns:
        True if a structural or trade event occurred this tick.
    """
    # 1. Check Transient Signals (Structural events)
    if hasattr(c_state, 'transient_signals') and c_state.transient_signals:
        if c_state.transient_signals.keys() & STRUCTURAL_TAGS:
            return True

    # 2. Check Trade Manager Events
    if hasattr(trade_manager, 'last_tick_events') and trade_manager.last_tick_events:
        for event in trade_manager.last_tick_events:
            if event in TRADE_EVENT_TAGS:
                return True

    return False

