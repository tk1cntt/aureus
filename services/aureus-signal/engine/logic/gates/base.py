from dataclasses import dataclass, field
from typing import Dict, Any
from abc import ABC, abstractmethod

@dataclass
class GateResult:
    is_passed: bool
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseGate(ABC):
    """
    Base class for Boolean Filter Gates.
    A gate returns either Pass or Fail (REJECT).
    """
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def check(self, state_obj: Any, context: Dict[str, Any]) -> GateResult:
        """
        Evaluate market conditions.
        Returns GateResult.
        """
        pass
