def evaluate_three_gates(candidate: dict) -> dict:
    if not candidate.get("structural_pass"):
        return {"qualified": False, "failed_gate": "structural"}

    if not candidate.get("momentum_volatility_pass"):
        return {"qualified": False, "failed_gate": "momentum_volatility"}

    if not candidate.get("risk_pass"):
        return {"qualified": False, "failed_gate": "risk"}

    return {"qualified": True, "failed_gate": None}
