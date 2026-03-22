from typing import Any, Dict, List

# Centralized mapping from transient signal tags emitted by signal layers
# to normalized AI trigger codes consumed by pulse queue orchestration.
_AI_TAG_TO_TRIGGER = {
    # Structure
    "choch_up": "CHANGE_OF_CHARACTER_BULLISH",
    "choch_down": "CHANGE_OF_CHARACTER_BEARISH",
    "bos_up": "BREAK_OF_STRUCTURE_BULLISH",
    "bos_down": "BREAK_OF_STRUCTURE_BEARISH",
    
    # OBs
    "ob_bull_new": "ORDER_BLOCK_BULLISH_NEW",
    "ob_bear_new": "ORDER_BLOCK_BEARISH_NEW",
    "ob_bull_mitigated": "ORDER_BLOCK_BULLISH_MITIGATED",
    "ob_bear_mitigated": "ORDER_BLOCK_BEARISH_MITIGATED",
    
    # FVGs
    "fvg_bull_new": "FAIR_VALUE_GAP_BULLISH_NEW",
    "fvg_bear_new": "FAIR_VALUE_GAP_BEARISH_NEW",
    "fvg_bull_mitigated": "FAIR_VALUE_GAP_BULLISH_MITIGATED",
    "fvg_bear_mitigated": "FAIR_VALUE_GAP_BEARISH_MITIGATED",
    
    # Sweep States (Bull)
    "sweep_touched_bull": "LIQUIDITY_SWEEP_TOUCHED_BULLISH",
    "sweep_sweep_bull": "LIQUIDITY_SWEEP_BULLISH",
    "sweep_broken_pending_bull": "LIQUIDITY_SWEEP_BROKEN_PENDING_BULLISH",
    "sweep_stop_hunt_bull": "LIQUIDITY_STOP_HUNT_BULLISH",
    "sweep_dead_bull": "LIQUIDITY_SWEEP_DEAD_BULLISH",
    
    # Sweep States (Bear)
    "sweep_touched_bear": "LIQUIDITY_SWEEP_TOUCHED_BEARISH",
    "sweep_sweep_bear": "LIQUIDITY_SWEEP_BEARISH",
    "sweep_broken_pending_bear": "LIQUIDITY_SWEEP_BROKEN_PENDING_BEARISH",
    "sweep_stop_hunt_bear": "LIQUIDITY_STOP_HUNT_BEARISH",
    "sweep_dead_bear": "LIQUIDITY_SWEEP_DEAD_BEARISH",
}


# Priority order controls deterministic event ordering when multiple tags
# appear in the same candle.
_TRIGGER_PRIORITY = (
    "CHANGE_OF_CHARACTER_BULLISH",
    "CHANGE_OF_CHARACTER_BEARISH",
    "BREAK_OF_STRUCTURE_BULLISH",
    "BREAK_OF_STRUCTURE_BEARISH",
    "LIQUIDITY_STOP_HUNT_BULLISH",
    "LIQUIDITY_STOP_HUNT_BEARISH",
    "LIQUIDITY_SWEEP_BULLISH",
    "LIQUIDITY_SWEEP_BEARISH",
    "LIQUIDITY_SWEEP_BROKEN_PENDING_BULLISH",
    "LIQUIDITY_SWEEP_BROKEN_PENDING_BEARISH",
    "ORDER_BLOCK_BULLISH_MITIGATED",
    "ORDER_BLOCK_BEARISH_MITIGATED",
    "FAIR_VALUE_GAP_BULLISH_MITIGATED",
    "FAIR_VALUE_GAP_BEARISH_MITIGATED",
    "LIQUIDITY_SWEEP_TOUCHED_BULLISH",
    "LIQUIDITY_SWEEP_TOUCHED_BEARISH",
    "ORDER_BLOCK_BULLISH_NEW",
    "ORDER_BLOCK_BEARISH_NEW",
    "FAIR_VALUE_GAP_BULLISH_NEW",
    "FAIR_VALUE_GAP_BEARISH_NEW",
    "LIQUIDITY_SWEEP_DEAD_BULLISH",
    "LIQUIDITY_SWEEP_DEAD_BEARISH",
)


def evaluate_ai_trigger_events(transient_signals: Any) -> List[str]:
    """Returns normalized AI trigger codes derived from transient signal tags.

    The function is intentionally side-effect free and returns de-duplicated,
    deterministic events in priority order.
    """
    if not isinstance(transient_signals, dict) or not transient_signals:
        return []

    normalized: Dict[str, bool] = {}
    for tag in transient_signals.keys():
        trigger = _AI_TAG_TO_TRIGGER.get(str(tag))
        if trigger:
            normalized[trigger] = True

    return [event for event in _TRIGGER_PRIORITY if normalized.get(event)]
