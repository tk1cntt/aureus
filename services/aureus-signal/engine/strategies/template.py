import json
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from .base import BaseStrategy


class TemplateStrategy(BaseStrategy):
    """Advanced strategy based on a weighted sequence of signal tags."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            config["name"],
            strategy_id=config.get("id", 0),
            weight=config.get("weight", 1.0),
        )
        self.min_score = config.get("min_score_threshold", 10.0)
        self.sequence = config.get("sequence", [])  # List of {tag, weight, required}
        self.exit_config = config.get("exit_config", {})

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

        core = self._evaluate_sequence(df, state_obj)
        reason_code = "OK" if (not core["missing_required"] and core["score"] >= self.min_score) else "SEQUENCE_NOT_MATCHED"

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
        exit_config = intent.get("exit_config") or self.exit_config or {}
        size_from_env = float(os.getenv("SIGNAL_ORDER_SIZE", "1.0"))

        return {
            "intent_id": intent.get("intent_id"),
            "entry_type": exit_config.get("entry_type", "MARKET"),
            "entry_policy": exit_config.get("entry_policy", "IMMEDIATE"),
            "direction": intent.get("direction", "BUY"),
            "size": float(exit_config.get("size", size_from_env)),
            "sl": exit_config.get("sl"),
            "tp": exit_config.get("tp"),
            "trailing": exit_config.get("trailing"),
            "expiry": exit_config.get("expiry"),
            "reason_code": intent.get("reason_code", "OK"),
            "evaluated_rules": [{"rule": "ORDER_PLAN_BUILT", "passed": True}],
            "evidence_refs": intent.get("evidence_refs", []),
        }
