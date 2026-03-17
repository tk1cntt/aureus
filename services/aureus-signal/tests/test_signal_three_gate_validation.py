import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.signals.qualification import evaluate_three_gates


def test_signal_must_pass_all_three_gates():
    candidate = {
        "structural_pass": True,
        "momentum_volatility_pass": True,
        "risk_pass": False,
    }

    out = evaluate_three_gates(candidate)
    assert out["qualified"] is False
    assert out["failed_gate"] == "risk"
