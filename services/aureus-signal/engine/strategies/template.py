import json
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from .base import BaseStrategy


class TemplateStrategy(BaseStrategy):
    """Advanced strategy based on a weighted sequence of signal tags.

    Answers 3 pillars of a complete strategy:
      1. WHAT (context_filters)  — Pre-conditions on market state
      2. WHEN (sequence)         — Ordered tag events that trigger entry
      3. HOW  (trade_execution)  — Risk sizing, SL, TP, trailing, early exits
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            config["name"],
            strategy_id=config.get("id", 0),
            weight=config.get("weight", 1.0),
        )
        self.min_score = config.get("min_score_threshold", 10.0)
        self.sequence = config.get("sequence", [])  # List of {tag, weight, required}
        self.exit_config = config.get("exit_config", {})
        self.context_filters = config.get("context_filters", [])  # Pillar 1: WHAT
        self.trade_execution = config.get("trade_execution", {})  # Pillar 3: HOW

    # ------------------------------------------------------------------ #
    # Pillar 1: WHAT — Context Pre-condition Evaluator
    # ------------------------------------------------------------------ #
    def _evaluate_context(self, state_obj: Any) -> Dict[str, Any]:
        """Evaluate all context_filters against the current state.

        Returns {"passed": bool, "failed_filters": [...], "details": [...]}
        """
        if not self.context_filters:
            return {"passed": True, "failed_filters": [], "details": []}

        failed: List[str] = []
        details: List[str] = []

        for f in self.context_filters:
            f_type = f.get("type", "")

            if f_type == "trend_alignment":
                required = f.get("required_trend", "BULLISH")
                actual = getattr(state_obj, "htf_trend", "NEUTRAL")
                if actual != required:
                    failed.append(f"trend_alignment:{required}")
                    details.append(f"Trend mismatch: need {required}, got {actual}")
                else:
                    details.append(f"Trend OK: {actual}")

            elif f_type == "session_active":
                allowed = f.get("allowed", [])
                actual = getattr(state_obj, "current_session", "UNKNOWN")
                if actual not in allowed:
                    failed.append(f"session_active:{actual}")
                    details.append(f"Session rejected: {actual} not in {allowed}")
                else:
                    details.append(f"Session OK: {actual}")

            elif f_type == "ob_imbalance":
                min_ratio = f.get("min_ratio", 3.0)
                obs = getattr(state_obj, "obs", [])
                lookback = f.get("lookback", 10)
                recent = obs[-lookback:] if obs else []
                bull = sum(1 for ob in recent if ob.get("ob_type") == "BULLISH")
                bear = sum(1 for ob in recent if ob.get("ob_type") == "BEARISH")
                if bear == 0 and bull > 0:
                    ratio = float(bull)
                elif bull == 0 and bear > 0:
                    ratio = float(bear)
                elif bull > 0 and bear > 0:
                    ratio = max(bull, bear) / min(bull, bear)
                else:
                    ratio = 0.0
                if ratio < min_ratio:
                    failed.append(f"ob_imbalance:{ratio:.1f}<{min_ratio}")
                    details.append(f"OB imbalance too low: {ratio:.1f} < {min_ratio}")
                else:
                    details.append(f"OB imbalance OK: {ratio:.1f}")

            elif f_type == "ema_alignment":
                required_slope = f.get("required_slope", "POSITIVE")
                period = f.get("period", 21)
                emas = getattr(state_obj, "emas", {})
                ema_data = emas.get(period, {})
                slope_val = ema_data.get("slope", 0) if isinstance(ema_data, dict) else 0
                slope_ok = (required_slope == "POSITIVE" and slope_val > 0) or \
                           (required_slope == "NEGATIVE" and slope_val < 0)
                if not slope_ok:
                    failed.append(f"ema_alignment:period={period}")
                    details.append(f"EMA({period}) slope mismatch: need {required_slope}, slope={slope_val}")
                else:
                    details.append(f"EMA({period}) slope OK: {slope_val}")

        return {
            "passed": len(failed) == 0,
            "failed_filters": failed,
            "details": details,
        }

    def _evaluate_sequence(self, df: pd.DataFrame, state_obj: Any) -> Dict[str, Any]:
        if not hasattr(state_obj, "strategy_progress"):
            state_obj.strategy_progress = {}
        
        state = state_obj.strategy_progress.get(self.name, {})
        current_step_index = state.get("current_step_index", 0)
        origin_timestamp = state.get("origin_timestamp", None)
        matched_timestamps = state.get("matched_timestamps", [])
        sequence_progress = state.get("sequence", [])
        last_matched_candle_idx = state.get("last_matched_candle_idx", -1)
        last_processed_index = state.get("last_processed_index", -1)
        internal_candle_counter = state.get("internal_candle_counter", 0)
        
        if not sequence_progress:
            for step in self.sequence:
                sequence_progress.append({
                    "tag": step["tag"],
                    "weight": step["weight"],
                    "required": step.get("required", False),
                    "max_wait": step.get("max_wait", 0),
                    "reset_signals": step.get("reset_signals", []),
                    "status": "waiting" if step.get("required", False) else "missed",
                    "time": None,
                })

        internal_candle_counter += 1

        # 1. Global Timeout Check
        if 0 < current_step_index < len(self.sequence):
            step = self.sequence[current_step_index]
            max_wait = step.get("max_wait", 0)
            if max_wait > 0 and last_matched_candle_idx != -1:
                # Difference in processed candles
                if (internal_candle_counter - last_matched_candle_idx) > max_wait:
                    current_step_index = 0
                    origin_timestamp = None
                    matched_timestamps = []
                    last_matched_candle_idx = -1
                    for s in sequence_progress:
                        s["status"] = "waiting" if s.get("required", False) else "missed"
                        s["time"] = None

        history = getattr(state_obj, "signal_history", [])
        current_history_idx = len(history) - 1

        # 2. Process new signals
        if history and current_history_idx > last_processed_index:
            for index in range(last_processed_index + 1, current_history_idx + 1):
                latest_signal = history[index]
                latest_tag = latest_signal["tag"]
                latest_time = latest_signal["t"]
                
                # Check for matching steps
                while current_step_index < len(self.sequence):
                    step = self.sequence[current_step_index]
                    tag = step["tag"]
                    reset_tags = step.get("reset_signals", [])
                    required = step.get("required", False)

                    # Reset condition has priority
                    if latest_tag in reset_tags:
                        current_step_index = 0
                        origin_timestamp = None
                        matched_timestamps = []
                        last_matched_candle_idx = -1
                        for s in sequence_progress:
                            s["status"] = "waiting" if s.get("required", False) else "missed"
                            s["time"] = None
                        break  # Halt matching loop, start fresh

                    # Match condition
                    if latest_tag == tag:
                        if current_step_index == 0:
                            origin_timestamp = latest_time
                        
                        matched_timestamps.append(latest_time)
                        last_matched_candle_idx = internal_candle_counter
                        sequence_progress[current_step_index]["status"] = "matched"
                        sequence_progress[current_step_index]["time"] = latest_time
                        current_step_index += 1
                        break  # Consumed the signal
                    else:
                        if not required:
                            sequence_progress[current_step_index]["status"] = "missed"
                            current_step_index += 1
                            continue # Try next step with the SAME signal
                        else:
                            break # Step is required, wait for next event
            
            last_processed_index = current_history_idx

        # Compute results
        matched_steps = 0
        missing_required = False
        total_score = 0.0
        details = []

        for i, s in enumerate(sequence_progress):
            if s["status"] == "matched":
                matched_steps += 1
                total_score += s["weight"]
                details.append(f"Found {s['tag']}")
            elif s["required"] and current_step_index <= i:
                missing_required = True
                details.append(f"Missing {s['tag']}")
        
        progress_data = {
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "progress_pct": (matched_steps / len(self.sequence)) * 100 if self.sequence else 0,
            "origin_timestamp": origin_timestamp,
            "sequence": sequence_progress,
            "t": int(df.iloc[-1]["t"]) if df is not None and not df.empty else 0,
            
            # State elements to persist
            "current_step_index": current_step_index,
            "matched_timestamps": matched_timestamps,
            "last_matched_candle_idx": last_matched_candle_idx,
            "last_processed_index": last_processed_index,
            "internal_candle_counter": internal_candle_counter
        }
        
        state_obj.strategy_progress[self.name] = progress_data

        return {
            "missing_required": missing_required,
            "score": total_score,
            "origin_timestamp": origin_timestamp,
            "details": details,
            "progress_data": progress_data,
            "matched_steps": matched_steps,
        }

    def evaluate(self, df: pd.DataFrame, signals: Dict[str, Any], state_obj: Any) -> Optional[Dict[str, Any]]:
        core = self._evaluate_sequence(df, state_obj)
        if core["missing_required"]:
            return None

        if core["score"] >= self.min_score:
            return {
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "origin_timestamp": core["origin_timestamp"],
                "score": core["score"],
                "details": json.dumps(core["details"]),
                "progress": json.dumps(core["progress_data"]),
                "t": int(df.iloc[-1]["t"]),
                "msg": f"Strategy {self.name} triggered with score {core['score']}",
                "exit_config": self.exit_config,
            }

        return None

    def on_bar_close(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = context.get("df")
        state_obj = context.get("state")

        if df is None or state_obj is None:
            return {
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "reason_code": "INVALID_CONTEXT",
                "is_actionable": False,
                "evaluated_rules": ["CONTEXT_PRESENT"],
                "evidence_refs": [],
                "t": 0,
            }

        bar_ts = int(df.iloc[-1]["t"])
        backfill_status = context.get("backfill_status", "READY")
        if backfill_status != "READY":
            return {
                "intent_id": f"{self.name}:{self.strategy_id}:{bar_ts}",
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "direction": "BUY",
                "reason_code": "BACKFILL_NOT_READY",
                "is_actionable": False,
                "evaluated_rules": ["BACKFILL_READY"],
                "evidence_refs": [{"type": "backfill_status", "value": backfill_status}],
                "t": bar_ts,
            }

        # Pillar 1: Evaluate context pre-conditions FIRST
        ctx = self._evaluate_context(state_obj)

        core = self._evaluate_sequence(df, state_obj)

        # Determine reason_code: context must pass AND sequence must match
        if not ctx["passed"]:
            reason_code = "CONTEXT_FILTER_FAILED"
        elif core["missing_required"] or core["score"] < self.min_score:
            reason_code = "SEQUENCE_NOT_MATCHED"
        else:
            reason_code = "OK"

        return {
            "intent_id": f"{self.name}:{self.strategy_id}:{bar_ts}",
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "direction": "BUY",
            "reason_code": reason_code,
            "is_actionable": reason_code == "OK",
            "score": core["score"],
            "origin_timestamp": core["origin_timestamp"],
            "evaluated_rules": [
                {
                    "rule": "CONTEXT_FILTER",
                    "passed": ctx["passed"],
                    "failed_filters": ctx["failed_filters"],
                },
                {
                    "rule": "SEQUENCE_MATCH",
                    "passed": not core["missing_required"],
                    "matched_steps": core["matched_steps"],
                },
                {
                    "rule": "MIN_SCORE_THRESHOLD",
                    "passed": core["score"] >= self.min_score,
                    "score": core["score"],
                    "min_score": self.min_score,
                },
            ],
            "evidence_refs": [
                {"type": "strategy_progress", "ref": self.name},
                {"type": "sequence", "value": core["progress_data"].get("sequence", [])},
                {"type": "context_details", "value": ctx["details"]},
            ],
            "legacy_result": self.evaluate(df, context.get("signals", {}), state_obj),
            "exit_config": self.exit_config,
            "t": bar_ts,
        }

    def validate_entry(self, intent: Optional[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        if not intent:
            return {
                "is_valid": False,
                "failed_rules": ["INTENT_MISSING"],
                "reason_code": "NO_INTENT",
                "evaluated_rules": [{"rule": "INTENT_PRESENT", "passed": False}],
            }

        if intent.get("reason_code") == "BACKFILL_NOT_READY":
            return {
                "is_valid": False,
                "failed_rules": ["BACKFILL_NOT_READY"],
                "reason_code": "BACKFILL_NOT_READY",
                "evaluated_rules": [{"rule": "BACKFILL_READY", "passed": False}],
            }

        if not intent.get("is_actionable"):
            return {
                "is_valid": False,
                "failed_rules": ["SEQUENCE_NOT_MATCHED"],
                "reason_code": "SEQUENCE_NOT_MATCHED",
                "evaluated_rules": [{"rule": "SEQUENCE_MATCH", "passed": False}],
            }

        return {
            "is_valid": True,
            "failed_rules": [],
            "reason_code": "OK",
            "evaluated_rules": [
                {"rule": "INTENT_PRESENT", "passed": True},
                {"rule": "ACTIONABLE_INTENT", "passed": True},
            ],
        }

    def build_order_plan(self, intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Pillar 3: HOW — Build order plan from trade_execution config + exit_config fallback."""
        exit_config = intent.get("exit_config") or self.exit_config or {}
        te = self.trade_execution  # trade_execution takes priority
        size_from_env = float(os.getenv("SIGNAL_ORDER_SIZE", "1.0"))

        # Size: trade_execution > exit_config > env
        size = float(te.get("size", exit_config.get("size", size_from_env)))

        # SL: trade_execution > exit_config
        sl = te.get("sl") or exit_config.get("sl")

        # TP: trade_execution > exit_config
        tp = te.get("tp") or exit_config.get("tp")

        # Trailing: trade_execution > exit_config
        trailing = te.get("trailing") or exit_config.get("trailing")

        # Early exits (force close tags)
        early_exits = te.get("early_exits", [])

        # Capital risk percentage (for downstream position sizing)
        capital_risk_pct = te.get("capital_risk_pct")

        return {
            "intent_id": intent.get("intent_id"),
            "entry_type": te.get("entry_type", exit_config.get("entry_type", "MARKET")),
            "entry_policy": te.get("entry_policy", exit_config.get("entry_policy", "IMMEDIATE")),
            "direction": intent.get("direction", "BUY"),
            "size": size,
            "sl": sl,
            "tp": tp,
            "trailing": trailing,
            "early_exits": early_exits,
            "capital_risk_pct": capital_risk_pct,
            "expiry": te.get("expiry", exit_config.get("expiry")),
            "reason_code": intent.get("reason_code", "OK"),
            "evaluated_rules": [{"rule": "ORDER_PLAN_BUILT", "passed": True}],
            "evidence_refs": intent.get("evidence_refs", []),
        }
