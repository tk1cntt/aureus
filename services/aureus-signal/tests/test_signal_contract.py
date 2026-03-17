import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.signals.contract import validate_signal_event


def test_signal_event_contract_requires_mandatory_fields():
    payload = {
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "ts": 1710000000,
        "strategy_id": "smc_trend_scalping",
    }

    with pytest.raises(ValueError):
        validate_signal_event(payload)


def test_signal_event_contract_accepts_valid_payload():
    payload = {
        "signal_id": "XAUUSD-M1-1710000000-choch_up",
        "decision_id": "XAUUSD-1710000000-decision",
        "run_id": "live",
        "signal_seq": 1,
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "ts": 1710000000,
        "strategy_id": "smc_trend_scalping",
        "signal_type": "choch_up",
        "confidence": 0.82,
        "metadata": {"source": "structure_processor"},
    }

    validated = validate_signal_event(payload)
    assert validated["signal_type"] == "choch_up"
