import logging
from typing import Any, Dict, List, Optional, Tuple, Type

from .base import BaseStrategy

logger = logging.getLogger("aureus-signal.strategy-registry")


class StrategyRegistry:
    """Registry for managing and executing trading strategies.

    Phase 8 responsibilities:
    - enforce metadata/spec compatibility checks,
    - orchestrate phased strategy contract execution,
    - retain backward-compatible `evaluate_all(...)` accepted output for callers.
    """

    def __init__(self, active_spec_version: str = "v1"):
        self.active_spec_version = (active_spec_version or "v1").strip().lower()
        self._strategies: Dict[str, BaseStrategy] = {}
        self._rejections: List[Dict[str, Any]] = []

    def clear(self):
        """Clears all registered strategies and rejection records."""
        self._strategies = {}
        self._rejections = []

    def _record_rejection(
        self,
        *,
        strategy_name: str,
        strategy_id: int,
        phase: str,
        reason_code: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "status": "REJECTED",
            "strategy": strategy_name,
            "strategy_id": strategy_id,
            "phase": phase,
            "reason_code": reason_code,
            "spec_version": self.active_spec_version,
            "details": details or {},
        }
        self._rejections.append(payload)
        return payload

    def get_rejections(self, clear: bool = False) -> List[Dict[str, Any]]:
        """Returns captured rejections; optionally clears the internal buffer."""
        out = list(self._rejections)
        if clear:
            self._rejections = []
        return out

    def _validate_compatibility(self, strategy: BaseStrategy) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        strategy_version = getattr(strategy, "strategy_version", None)
        strategy_spec = tuple(
            str(v).strip().lower()
            for v in (getattr(strategy, "spec_compatibility", ()) or ())
            if str(v).strip()
        )

        if not isinstance(strategy_version, str) or not strategy_version.strip():
            return False, "INVALID_STRATEGY_VERSION", {
                "strategy_version": strategy_version,
                "spec_compatibility": list(strategy_spec),
            }

        if self.active_spec_version not in strategy_spec:
            return False, "SPEC_VERSION_INCOMPATIBLE", {
                "strategy_version": strategy_version,
                "spec_compatibility": list(strategy_spec),
                "required_spec_version": self.active_spec_version,
            }

        return True, None, {
            "strategy_version": strategy_version,
            "spec_compatibility": list(strategy_spec),
        }

    def register(self, strategy: BaseStrategy) -> bool:
        """Registers a strategy instance if compatible; fail-fast otherwise."""
        strategy_name = getattr(strategy, "name", "UNKNOWN")
        strategy_id = int(getattr(strategy, "strategy_id", 0) or 0)

        is_valid, reason_code, details = self._validate_compatibility(strategy)
        if not is_valid:
            self._record_rejection(
                strategy_name=strategy_name,
                strategy_id=strategy_id,
                phase="register",
                reason_code=reason_code or "UNKNOWN_REJECTION",
                details=details,
            )
            logger.warning(
                f"[GLOBAL] [register] Strategy rejected name={strategy_name} "
                f"id={strategy_id} reason={reason_code}"
            )
            return False

        self._strategies[strategy_name] = strategy
        logger.info(f"[GLOBAL] [register] 1... Strategy registered: {strategy_name}")
        return True

    async def load_from_db(self, db, symbol: str):
        """
        Loads active strategies for a symbol from PostgreSQL.
        Supports both TemplateStrategy and specialized classes.
        """
        query = """
            SELECT t.id
            FROM aureus_strategy_templates t
            JOIN aureus_symbol_strategies ss ON t.id = ss.strategy_id
            WHERE ss.symbol = $1 AND ss.is_active = true
        """
        rows = await db.fetch(query, symbol)
        strategy_ids = [r["id"] for r in rows]
        await self.load_by_ids(db, symbol, strategy_ids)

    async def load_by_ids(self, db, symbol: str, strategy_ids: List[int]):
        """
        Loads strategies by their template IDs, regardless of 'active' status for the symbol.
        Uses template defaults if no symbol-specific override is found.
        """
        from .order_flow_dominance import OrderFlowDominanceStrategy
        from .template import TemplateStrategy
        from .trend_continuation import TrendContinuationStrategy
        import json

        # Mapping of Template Name to Strategy Class
        strategy_map: Dict[str, Type[BaseStrategy]] = {
            "TREND_CONT": TrendContinuationStrategy,
            "SESSION_SWEEP": TrendContinuationStrategy,
            "ORDER_FLOW_DOM": OrderFlowDominanceStrategy,
        }

        if not strategy_ids:
            self.clear()
            return

        # Query templates and join with symbol-specific overrides (if they exist)
        query = """
            SELECT t.id, t.name, t.config, t.min_score
            FROM aureus_strategy_templates t
            LEFT JOIN aureus_symbol_strategies ss ON t.id = ss.strategy_id AND ss.symbol = $1
            WHERE t.id = ANY($2)
        """
        rows = await db.fetch(query, symbol, strategy_ids)

        self.clear()
        for r in rows:
            name = r["name"]
            config = json.loads(r["config"]) if isinstance(r["config"], str) else r["config"]
            config["id"] = r["id"]
            config["name"] = name
            config["min_score_threshold"] = r["min_score"]

            # Select class based on map, fallback to TemplateStrategy
            strat_class = strategy_map.get(name, TemplateStrategy)
            strat = strat_class(config)
            self.register(strat)

        logger.info(
            f"[{symbol}] [load_by_ids] 1... Loaded={len(self._strategies)} "
            f"Rejected={len(self._rejections)} (Target IDs: {strategy_ids})"
        )

    def evaluate_all(self, df, signals, state_obj) -> List[Dict[str, Any]]:
        """Evaluates registered strategies via phased orchestration.

        Returns only ACCEPTED decisions to preserve existing callers.
        Rejections are captured internally and retrievable via `get_rejections()`.
        """
        accepted: List[Dict[str, Any]] = []
        bar_ts = int(df.iloc[-1]["t"]) if df is not None and len(df) > 0 and "t" in df.columns else 0
        context = {
            "df": df,
            "signals": signals,
            "state": state_obj,
            "bar_ts": bar_ts,
        }

        for name, strategy in self._strategies.items():
            strategy_id = int(getattr(strategy, "strategy_id", 0) or 0)
            try:
                is_valid, reason_code, details = self._validate_compatibility(strategy)
                if not is_valid:
                    self._record_rejection(
                        strategy_name=name,
                        strategy_id=strategy_id,
                        phase="compatibility",
                        reason_code=reason_code or "UNKNOWN_REJECTION",
                        details=details,
                    )
                    continue

                intent = strategy.on_bar_close(context)
                if not intent:
                    # No trigger is not a rejection; strategy simply did not emit intent.
                    continue

                validation = strategy.validate_entry(intent, context)
                if not validation.get("is_valid", False):
                    self._record_rejection(
                        strategy_name=name,
                        strategy_id=strategy_id,
                        phase="validate_entry",
                        reason_code=validation.get("reason_code", "VALIDATION_REJECTED"),
                        details={
                            "failed_rules": validation.get("failed_rules", []),
                            "evaluated_rules": validation.get("evaluated_rules", []),
                            "intent_id": intent.get("intent_id"),
                            "t": intent.get("t", bar_ts),
                        },
                    )
                    continue

                order_plan = strategy.build_order_plan(intent, context)
                if not isinstance(order_plan, dict):
                    self._record_rejection(
                        strategy_name=name,
                        strategy_id=strategy_id,
                        phase="build_order_plan",
                        reason_code="ORDER_PLAN_INVALID_SHAPE",
                        details={
                            "intent_id": intent.get("intent_id"),
                            "returned_type": type(order_plan).__name__,
                        },
                    )
                    continue

                plan_reason = str(order_plan.get("reason_code", "OK")).strip().upper()
                if plan_reason not in {"", "OK"}:
                    self._record_rejection(
                        strategy_name=name,
                        strategy_id=strategy_id,
                        phase="build_order_plan",
                        reason_code=plan_reason,
                        details={
                            "intent_id": intent.get("intent_id"),
                            "evaluated_rules": order_plan.get("evaluated_rules", []),
                        },
                    )
                    continue

                accepted.append(
                    {
                        "strategy": name,
                        "strategy_id": strategy_id,
                        "strategy_version": getattr(strategy, "strategy_version", "v1"),
                        "spec_version": self.active_spec_version,
                        "reason_code": "OK",
                        "t": int(intent.get("t", bar_ts) or bar_ts),
                        "origin_timestamp": intent.get("origin_timestamp", intent.get("t", bar_ts)),
                        "side": order_plan.get("direction", intent.get("direction", "BUY")),
                        "entry_type": order_plan.get("entry_type", "MARKET"),
                        "entry_policy": order_plan.get("entry_policy", "IMMEDIATE"),
                        "size": order_plan.get("size"),
                        "sl": order_plan.get("sl"),
                        "tp": order_plan.get("tp"),
                        "trailing": order_plan.get("trailing"),
                        "expiry": order_plan.get("expiry"),
                        "exit_config": intent.get("exit_config", {}),
                        "intent": intent,
                        "validation": validation,
                        "order_plan": order_plan,
                    }
                )
            except Exception as e:
                self._record_rejection(
                    strategy_name=name,
                    strategy_id=strategy_id,
                    phase="orchestration",
                    reason_code="STRATEGY_EVALUATION_ERROR",
                    details={"error": str(e)},
                )
                logger.error(f"[GLOBAL] [evaluate_all] Error: Evaluating strategy {name}: {e}")

        return accepted

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        return list(self._strategies.keys())
