from dataclasses import dataclass, field
from typing import Dict, Any
from abc import ABC, abstractmethod

@dataclass
class JudgeResult:
    score: float  # 0.0 to 1.0
    confidence: float = 1.0
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    can_override: bool = False # New: Ability to bypass vetos if score is exceptional

class BaseJudge(ABC):
    """
    Base class for Algorithmic Judges.
    A judge provides a qualitative score for a specific technical aspect.
    """
    def __init__(self, name: str, weight: float = 1.0, can_veto: bool = False, veto_threshold: float = 0.3):
        self.name = name
        self.weight = weight
        self.can_veto = can_veto
        self.veto_threshold = veto_threshold

    @abstractmethod
    def evaluate(self, state_obj: Any, trigger: Dict[str, Any]) -> JudgeResult:
        """
        Perform complex evaluation on state data.
        Returns JudgeResult.
        """
        pass

    def supports_tag(self, tag: str) -> bool:
        """
        Returns True if this judge handles the given signal tag.
        Default is True for backward compatibility.
        """
        return True
