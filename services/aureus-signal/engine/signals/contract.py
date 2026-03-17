from typing import Any, Dict

MANDATORY_FIELDS = {
    "signal_id",
    "decision_id",
    "run_id",
    "signal_seq",
    "symbol",
    "timeframe",
    "ts",
    "strategy_id",
    "signal_type",
    "confidence",
    "metadata",
}


def validate_signal_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = [field for field in MANDATORY_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing mandatory fields: {missing}")
    return payload
