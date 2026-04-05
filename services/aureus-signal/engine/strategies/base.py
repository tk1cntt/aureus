from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Sequence

import pandas as pd


class BaseStrategy(ABC):
    """Base class for all strategy evaluators.

    Phase 6 introduces a phased contract (`on_bar_close` -> `validate_entry` ->
    `build_order_plan`) while retaining backward compatibility with legacy
    `evaluate(...)` implementations.
    """

    def __init__(
        self,
        name: str,
        strategy_id: int = 0,
        weight: float = 1.0,
        strategy_version: str = "v1",
        spec_compatibility: Optional[Sequence[str]] = None,
    ):
        self.name = name
        self.strategy_id = strategy_id
        self.weight = weight
        self.strategy_version = strategy_version or "v1"
        self.spec_compatibility = tuple(spec_compatibility or ("v1",))
        self.magic_number = 0

    @abstractmethod
    def evaluate(
        self,
        df: pd.DataFrame,
        signals: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Legacy single-phase evaluate contract.

        Existing strategy classes still implement this method. New runtime flow
        should use phased methods below, which adapt from this output by default.
        """

    def on_bar_close(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Phase 1: produce an intent from a closed candle context.

        Default behavior adapts legacy `evaluate(...)` output into an intent-like
        structure to preserve compatibility during phased migration.
        """

        df = context.get("df")
        signals = context.get("signals", {})
        state = context.get("state", {})

        legacy_result = self.evaluate(df, signals, state)
        if not legacy_result:
            return None

        candle_ts = int(legacy_result.get("t") or context.get("bar_ts") or 0)
        intent_id = f"{self.name}:{self.strategy_id}:{candle_ts}"

        return {
            "intent_id": intent_id,
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "direction": legacy_result.get("direction", "BUY"),
            "reason_code": "LEGACY_EVALUATE_MATCH",
            "legacy_result": legacy_result,
            "t": candle_ts,
        }

    def validate_entry(self, intent: Optional[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2: validate generated intent against entry rules."""

        if not intent:
            return {
                "is_valid": False,
                "failed_rules": ["INTENT_MISSING"],
                "reason_code": "NO_INTENT",
            }

        return {
            "is_valid": True,
            "failed_rules": [],
            "reason_code": "OK",
        }

    def build_order_plan(self, intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 3: construct order plan from validated intent."""

        legacy_result = intent.get("legacy_result", {}) if isinstance(intent, dict) else {}
        direction = intent.get("direction") or legacy_result.get("direction") or "BUY"

        return {
            "intent_id": intent.get("intent_id"),
            "entry_type": "MARKET",
            "entry_policy": "IMMEDIATE",
            "direction": direction,
            "size": 1.0,
            "size_value": 1.0,
            "size_mode": "FIXED_UNITS",
            "magic_number": self.magic_number,
            "sl": None,
            "tp": None,
            "trailing": None,
            "expiry": None,
            "reason_code": "OK",
        }
