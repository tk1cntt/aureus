from typing import Dict, Any
from .base import BaseGate, GateResult

class RiskRewardGate(BaseGate):
    """
    Gate that verifies if the setup has a minimum acceptable Risk/Reward ratio.
    """
    def __init__(self, min_rr: float = 1.5):
        super().__init__("RiskRewardGate")
        self.min_rr = min_rr

    def check(self, state_obj: Any, context: Dict[str, Any]) -> GateResult:
        # In a real scenario, we'd calculate RR based on Entry, SL (Pivot), and TP (Next OB)
        # For POC, we look for 'rr' in context or assume valid if enough distance exists
        
        rr = context.get('estimated_rr', 0.0)
        
        if rr >= self.min_rr:
            return GateResult(
                is_passed=True, 
                reason=f"Risk/Reward {rr:.2f} >= {self.min_rr}",
                metadata={"rr": rr}
            )
        
        return GateResult(
            is_passed=False, 
            reason=f"Insufficient Risk/Reward: {rr:.2f} (Min required: {self.min_rr})",
            metadata={"rr": rr}
        )

class SpreadGate(BaseGate):
    """
    Gate that ensures market spread is within acceptable limits.
    """
    def __init__(self, max_spread_pct: float = 0.05):
        super().__init__("SpreadGate")
        self.max_spread_pct = max_spread_pct

    def check(self, state_obj: Any, context: Dict[str, Any]) -> GateResult:
        # Simplified spread check for POC
        spread_pct = context.get('current_spread_pct', 0.01)
        
        if spread_pct <= self.max_spread_pct:
            return GateResult(is_passed=True, reason=f"Spread {spread_pct:.3f}% is acceptable")
            
        return GateResult(
            is_passed=False, 
            reason=f"Spread too high: {spread_pct:.3f}% (Max: {self.max_spread_pct}%)"
        )
