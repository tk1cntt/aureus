import logging
from engine.logging_common import get_logger
from typing import List, Dict, Any

from .gates.base import BaseGate
from .judges.base import BaseJudge

logger = get_logger(__name__)
class HybridOrchestrator:
    """
    Central brain that coordinates Boolean Gates and Algorithmic Judges.
    Follows a Fail-Fast pattern for Gates, then a Weighted Scoring for Judges.
    """
    def __init__(self, gates: List[BaseGate], judges: List[BaseJudge], min_pass_score: float = 0.6):
        self.gates = gates
        self.judges = judges
        self.min_pass_score = min_pass_score

    def audit(self, state_obj: Any, trigger: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs a full audit of a trade setup.
        """
        # 1. Run Boolean Gates (Fail-Fast)
        gate_results = []
        for gate in self.gates:
            res = gate.check(state_obj, context)
            gate_results.append({
                "name": gate.name,
                "passed": res.is_passed,
                "reason": res.reason
            })
            if not res.is_passed:
                logger.info(f"Audit REJECTED by Gate: {gate.name} - {res.reason}")
                return {
                    "decision": "REJECT",
                    "aci": 0,
                    "reason": f"Gate Failure: {res.reason}",
                    "breakdown": {"gates": gate_results, "judges": []}
                }

        # 2. Run Algorithmic Judges
        judge_results = []
        total_weighted_score = 0.0
        total_weight = 0.0
        
        all_high_confidence = True
        veto_triggered = False
        veto_override = False
        veto_reason = ""
        override_reason = ""

        active_judges_count = 0
        
        for judge in self.judges:
            if not judge.supports_tag(trigger.get('tag', '')):
                continue
            
            active_judges_count += 1
            res = judge.evaluate(state_obj, trigger)
            
            # 2.2. Veto Check
            if judge.can_veto and res.score < judge.veto_threshold:
                veto_triggered = True
                veto_reason = f"VETO by {judge.name}: Score {res.score:.2f} < Threshold {judge.veto_threshold}"
                logger.warning(veto_reason)

            # 2.3. Veto Override Logic
            if res.score >= 0.9 and getattr(res, 'can_override', False):
                veto_override = True
                override_reason = f"VETO OVERRIDEN by {judge.name}: Exceptional Pattern Strength ({res.score:.2f})"
                logger.info(override_reason)

            # 2.4. Consensus Check
            if res.score < 0.7:
                all_high_confidence = False

            weighted_score = res.score * judge.weight
            
            total_weighted_score += weighted_score
            total_weight += judge.weight
            
            judge_results.append({
                "name": judge.name,
                "score": round(res.score, 2),
                "weight": judge.weight,
                "reason": res.reason,
                "evidence": res.evidence,
                "can_veto": judge.can_veto,
                "veto_triggered": judge.can_veto and res.score < judge.veto_threshold
            })

        final_score = total_weighted_score / total_weight if total_weight > 0 else 0.0
        
        # Apply Consensus Multiplier (1.1x)
        consensus_active = all_high_confidence and active_judges_count > 0
        if consensus_active:
            final_score = min(1.0, final_score * 1.1)
            logger.info(f"Consensus Bonus applied! Final Score: {final_score:.2f}")

        final_aci = int(final_score * 100)
        
        decision = "ACTIVE" if final_score >= self.min_pass_score else "REJECT"
        
        # Override decision if Veto triggered
        if veto_triggered and not veto_override:
            decision = "REJECT"
        elif veto_triggered and veto_override:
            logger.info(f"Veto BYPASSED due to {override_reason}")

        # 3. Holiday Policy (Sweep-only mode)
        if decision == "ACTIVE" and context.get('is_holiday_mode'):
            tag = trigger.get('tag', '').upper()
            if "SWEEP" not in tag:
                logger.info(f"Audit REJECTED: Holiday Mode active. Only SWEEP setups allowed. (Trigger: {tag})")
                return {
                    "decision": "REJECT",
                    "aci": 0,
                    "reason": f"Holiday Mode: Only SWEEP setups allowed. (Relevant currency has bank holiday)",
                    "breakdown": {"gates": gate_results, "judges": judge_results}
                }

        return {
            "decision": decision,
            "aci": final_aci,
            "reason": override_reason if (veto_triggered and veto_override) else (veto_reason if veto_triggered else (f"Scoring Result: {final_aci}/100" if decision == "ACTIVE" else "Insufficient confluence score")),
            "breakdown": {
                "gates": gate_results,
                "judges": judge_results,
                "final_score": round(final_score, 4),
                "veto_triggered": veto_triggered,
                "veto_override": veto_override,
                "consensus_active": consensus_active
            }
        }
