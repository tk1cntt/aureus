import json
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from engine.logging_common import get_logger
from engine.snapshot_utils import VALID_ENTRY_TYPES, VALID_SIZE_MODES

from .base import BaseStrategy

logger = get_logger(__name__)
PIPELINE_LOG_PREFIX = "[PIPELINE]"


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
        self.magic_number = config.get("magic_number", self.strategy_id * 1000)

        # Direction must be explicitly configured in trade_execution
        direction = str(self.trade_execution.get("direction", "")).strip().upper()
        if direction not in ("BUY", "SELL"):
            raise ValueError(
                f"Strategy '{self.name}': 'direction' must be 'BUY' or 'SELL' in trade_execution config. "
                f"Got: {self.trade_execution.get('direction')!r}"
            )
        self.direction = direction

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
        last_processed_t = state.get("last_processed_t", 0)
        last_processed_record_index = state.get("last_processed_record_index", -1)  # ← NEW: Track by index instead of timestamp
        internal_candle_counter = state.get("internal_candle_counter", 0)
        triggered_t = state.get("triggered_t", 0)  # Timestamp of last successful trigger

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

        normalized_log = getattr(state_obj, "log_signal_normalize", [])

        # DEBUG LOGGING: Trace event processing
        symbol = getattr(state_obj, "symbol", "UNKNOWN")
        logger.debug(
            f"[{symbol}] [{self.name}] [_evaluate_sequence] "
            f"Processing {len(normalized_log)} log entries, "
            f"last_processed_t={last_processed_t}, "
            f"last_processed_record_index={last_processed_record_index}, "
            f"current_step_index={current_step_index}"
        )

        # We now STRICTLY rely on normalized signal events. No fallback to raw history.
        source_records = normalized_log if isinstance(normalized_log, list) else []

        # 2. Process new signals/events
        # BUG FIX: Use BOTH record index AND timestamp to:
        #   - Avoid skipping records with same timestamp (use index)
        #   - Only process RECENT events (use timestamp for max_wait checks)
        # Old logic: `rec_t > last_processed_t` would skip records with same timestamp
        # New logic: Process all records after last_processed_record_index
        pending_records = []
        for idx, rec in enumerate(source_records):
            if not isinstance(rec, dict):
                continue
            if idx > last_processed_record_index:
                pending_records.append((idx, rec))  # ← Store index with record

        if pending_records:
            # Sort by timestamp while preserving index
            pending_records.sort(key=lambda x: x[1].get("t", 0))

            for record_idx, record in pending_records:
                events_to_process: List[Dict[str, Any]] = []

                if isinstance(record, dict):
                    record_time = record.get("t")
                    signals_obj = record.get("signals") if isinstance(record.get("signals"), dict) else {}
                    events_obj = signals_obj.get("events") if isinstance(signals_obj.get("events"), list) else []

                    # DEBUG: Log raw events before normalization
                    logger.debug(
                        f"[{symbol}] [{self.name}] [process_events] "
                        f"Found {len(events_obj) if events_obj else 0} raw events at t={record_time} (record_idx={record_idx})"
                    )

                    for ev in events_obj:
                        if not isinstance(ev, dict):
                            continue
                        ev_tag = ev.get("tag")
                        if ev_tag is None:
                            continue

                        ev_val = ev.get("value")
                        original_tag = ev_tag
                        if ev_val and isinstance(ev_val, str) and ev_tag in ["choch", "sweep", "ob", "fvg", "bos"]:
                            ev_tag = ev_val
                            # DEBUG: Log normalization
                            logger.debug(
                                f"[{symbol}] [{self.name}] [normalize_event] "
                                f"Normalized '{original_tag}' + '{ev_val}' → '{ev_tag}'"
                            )

                        events_to_process.append({"tag": ev_tag, "t": record_time})

                for latest_signal in events_to_process:
                    latest_tag = latest_signal.get("tag")
                    if latest_tag is None:
                        continue
                    latest_time = latest_signal.get("t")

                    # SKIP OLD EVENTS: If event time <= triggered_t, it's from a previous trigger cycle
                    # This prevents re-processing events after executor restart
                    if triggered_t > 0 and latest_time <= triggered_t:
                        logger.debug(
                            f"[{symbol}] [{self.name}] [skip_old_event] "
                            f"Event tag='{latest_tag}' at t={latest_time} <= triggered_t={triggered_t} - skipping"
                        )
                        continue

                    # DEBUG: Log each signal being processed
                    logger.debug(
                        f"[{symbol}] [{self.name}] [process_signal] "
                        f"Processing tag='{latest_tag}' at t={latest_time}, "
                        f"current_step_index={current_step_index}"
                    )

                    # Check if sequence is already completed but a new step 0 event occurs
                    if current_step_index >= len(self.sequence) and len(self.sequence) > 0:
                        first_step_tag = self.sequence[0]["tag"]
                        if latest_tag == first_step_tag:
                            logger.debug(
                                f"[{symbol}] [{self.name}] [reset_completed_sequence] "
                                f"Sequence completed, new '{first_step_tag}' event detected - resetting"
                            )
                            current_step_index = 0
                            origin_timestamp = None
                            matched_timestamps = []
                            last_matched_candle_idx = -1
                            for s in sequence_progress:
                                s["status"] = "waiting" if s.get("required", False) else "missed"
                                s["time"] = None

                    # Check for matching steps
                    while current_step_index < len(self.sequence):
                        step = self.sequence[current_step_index]
                        tag = step["tag"]
                        reset_tags = step.get("reset_signals", [])
                        required = step.get("required", False)

                        # Reset condition has priority
                        if latest_tag in reset_tags:
                            logger.debug(
                                f"[{symbol}] [{self.name}] [reset_signal_detected] "
                                f"Reset signal '{latest_tag}' matched reset_tags={reset_tags} - resetting sequence"
                            )
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
                            logger.debug(
                                f"[{symbol}] [{self.name}] [signal_matched] "
                                f"Signal '{latest_tag}' matched step {current_step_index} '{tag}'"
                            )
                            if current_step_index == 0:
                                origin_timestamp = latest_time
                                triggered_t = 0  # Clear triggered flag — new sequence cycle begins

                            matched_timestamps.append(latest_time)
                            last_matched_candle_idx = internal_candle_counter
                            sequence_progress[current_step_index]["status"] = "matched"
                            sequence_progress[current_step_index]["time"] = latest_time
                            current_step_index += 1
                            break  # Consumed the signal
                        else:
                            if not required:
                                logger.debug(
                                    f"[{symbol}] [{self.name}] [skip_optional_step] "
                                    f"Signal '{latest_tag}' != step {current_step_index} '{tag}' (optional) - skipping"
                                )
                                sequence_progress[current_step_index]["status"] = "missed"
                                current_step_index += 1
                                continue # Try next step with the SAME signal
                            else:
                                logger.debug(
                                    f"[{symbol}] [{self.name}] [waiting_for_required] "
                                    f"Signal '{latest_tag}' != required step {current_step_index} '{tag}' - waiting"
                                )
                                break # Step is required, wait for next event

            if pending_records:
                last_processed_t = pending_records[-1][1].get("t", last_processed_t)
                last_processed_record_index = pending_records[-1][0]  # ← Update index
                logger.debug(
                    f"[{symbol}] [{self.name}] [update_last_processed] "
                    f"last_processed_t={last_processed_t}, last_processed_record_index={last_processed_record_index}"
                )

        # --- Auto-reset: detect truncation stall (D-01) ---
        # Only check if we've advanced past step 0 AND have a trigger (prevents false reset during normal matching)
        if current_step_index > 0 and triggered_t > 0:
            remaining_steps = len(self.sequence) - current_step_index
            # Count usable events: those with t > triggered_t
            events_after_trigger = sum(
                1 for rec in source_records
                if isinstance(rec, dict) and rec.get("t", 0) > triggered_t
            )
            if events_after_trigger < remaining_steps:
                logger.warning(
                    f"[{symbol}] [{self.name}] [auto_reset] "
                    f"Truncation stall: only {events_after_trigger} usable events "
                    f"(t > triggered_t={triggered_t}), need {remaining_steps} steps. "
                    f"Resetting sequence to step 0."
                )
                self._reset_sequence_state(
                    state_obj,
                    triggered_t=0,
                    last_processed_t=last_processed_t,
                    internal_candle_counter=internal_candle_counter,
                )
                # Reset local variables to reflect the reset state
                current_step_index = 0
                origin_timestamp = None
                matched_timestamps = []
                last_matched_candle_idx = -1
                for s in sequence_progress:
                    s["status"] = "waiting" if s.get("required", False) else "missed"
                    s["time"] = None
                total_score = 0.0
                matched_steps = 0
                missing_required = any(s.get("required", False) for s in self.sequence)
                # Jump to compute results with reset state
                progress_data = {
                    "strategy": self.name,
                    "strategy_id": self.strategy_id,
                    "progress_pct": 0,
                    "origin_timestamp": None,
                    "sequence": sequence_progress,
                    "t": int(df.iloc[-1]["t"]) if df is not None and not df.empty else 0,
                    "current_step_index": 0,
                    "matched_timestamps": [],
                    "last_matched_candle_idx": -1,
                    "last_processed_t": last_processed_t,
                    "last_processed_record_index": last_processed_record_index,
                    "internal_candle_counter": internal_candle_counter,
                    "triggered_t": 0,
                    "sequence_completed_t": 0,
                }
                state_obj.strategy_progress[self.name] = progress_data
                return {
                    "missing_required": missing_required,
                    "score": 0.0,
                    "origin_timestamp": None,
                    "details": [f"Auto-reset: {events_after_trigger} usable events < {remaining_steps} remaining steps"],
                    "progress_data": progress_data,
                    "matched_steps": 0,
                }

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
        
        # --- Track when sequence was fully completed ---
        sequence_completed_t = 0
        if (len(self.sequence) > 0 and current_step_index >= len(self.sequence)
                and not missing_required and total_score >= self.min_score
                and matched_timestamps):
            sequence_completed_t = matched_timestamps[-1]  # Timestamp of last matched event

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
            "last_processed_t": last_processed_t,
            "last_processed_record_index": last_processed_record_index,  # ← NEW
            "internal_candle_counter": internal_candle_counter,
            "triggered_t": triggered_t,
            "sequence_completed_t": sequence_completed_t,
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

    def _reset_sequence_state(self, state_obj: Any, triggered_t: int = 0, last_processed_t: int = 0, internal_candle_counter: int = 0):
        """Reset sequence progress to clean waiting state after trigger or timeout."""
        fresh_sequence = []
        for step in self.sequence:
            fresh_sequence.append({
                "tag": step["tag"],
                "weight": step["weight"],
                "required": step.get("required", False),
                "max_wait": step.get("max_wait", 0),
                "reset_signals": step.get("reset_signals", []),
                "status": "waiting" if step.get("required", False) else "missed",
                "time": None,
            })
        state_obj.strategy_progress[self.name] = {
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "progress_pct": 0,
            "origin_timestamp": None,
            "sequence": fresh_sequence,
            "t": 0,
            "current_step_index": 0,
            "matched_timestamps": [],
            "last_matched_candle_idx": -1,
            "last_processed_t": last_processed_t,
            "last_processed_record_index": -1,  # ← Reset index tracking
            "internal_candle_counter": internal_candle_counter,
            "triggered_t": triggered_t,
        }

    def evaluate(self, df: pd.DataFrame, signals: Dict[str, Any], state_obj: Any) -> Optional[Dict[str, Any]]:
        """Legacy evaluate contract — now includes context filter checking.

        BUG FIX: Previously evaluate() skipped _evaluate_context(), which meant
        context filters were only checked in on_bar_close(). This caused inconsistency
        where evaluate() would trigger strategies that on_bar_close() would reject.

        Now both paths enforce context filters identically.
        """
        # Pillar 1: Evaluate context pre-conditions (BUG FIX - was missing)
        ctx = self._evaluate_context(state_obj)
        if not ctx["passed"]:
            logger.debug(
                f"[{getattr(state_obj, 'symbol', 'UNKNOWN')}] [evaluate][context_filter_failed] "
                f"strategy={self.name} failed_filters={ctx['failed_filters']}"
            )
            return None

        core = self._evaluate_sequence(df, state_obj)
        if core["missing_required"]:
            return None

        if core["score"] >= self.min_score:
            bar_t = int(df.iloc[-1]["t"])
            progress_data = core["progress_data"]

            # Only trigger at the EXACT candle where last event matched
            sequence_completed_t = progress_data.get("sequence_completed_t", 0)
            if progress_data.get("triggered_t", 0) > 0 or bar_t != sequence_completed_t:
                return None

            # Mark as triggered and auto-reset for next cycle
            result = {
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "origin_timestamp": core["origin_timestamp"],
                "score": core["score"],
                "details": json.dumps(core["details"]),
                "progress": json.dumps(core["progress_data"]),
                "t": bar_t,
                "msg": f"Strategy {self.name} triggered with score {core['score']}",
                "exit_config": self.exit_config,
            }

            # Auto-reset: mark triggered_t and clear sequence for next cycle
            self._reset_sequence_state(
                state_obj,
                triggered_t=bar_t,
                last_processed_t=progress_data.get("last_processed_t", 0),
                internal_candle_counter=progress_data.get("internal_candle_counter", 0),
            )

            return result

        return None

    def _build_sequence_diagnostics(self, core: Dict[str, Any]) -> Dict[str, Any]:
        progress_data = core.get("progress_data", {})
        sequence_steps = progress_data.get("sequence", [])
        current_step_index = int(progress_data.get("current_step_index", 0) or 0)
        score = float(core.get("score", 0.0) or 0.0)
        score_gap = max(0.0, float(self.min_score) - score)

        step_statuses: List[Dict[str, Any]] = []
        missing_required_tags: List[str] = []

        for idx, step in enumerate(sequence_steps):
            status = step.get("status", "unknown")
            required = bool(step.get("required", False))
            tag = str(step.get("tag", "UNKNOWN"))
            if required and status != "matched":
                missing_required_tags.append(tag)

            step_statuses.append(
                {
                    "index": idx,
                    "tag": tag,
                    "required": required,
                    "status": status,
                    "is_matched": status == "matched",
                    "is_current_expected": idx == current_step_index,
                    "weight": step.get("weight", 0),
                    "time": step.get("time"),
                    "max_wait": step.get("max_wait", 0),
                    "reset_signals": step.get("reset_signals", []),
                }
            )

        missing_required = bool(core.get("missing_required", False))
        score_below = score < float(self.min_score)

        if missing_required and score_below:
            mismatch_reason = "MISSING_REQUIRED_AND_SCORE_BELOW_THRESHOLD"
        elif missing_required:
            mismatch_reason = "MISSING_REQUIRED_STEP"
        elif score_below:
            mismatch_reason = "SCORE_BELOW_THRESHOLD"
        elif not sequence_steps:
            mismatch_reason = "NO_SEQUENCE_CONFIG"
        else:
            mismatch_reason = "UNKNOWN_SEQUENCE_MISMATCH"

        return {
            "mismatch_reason": mismatch_reason,
            "missing_required": missing_required,
            "missing_required_tags": missing_required_tags,
            "score": score,
            "min_score": float(self.min_score),
            "score_gap": score_gap,
            "current_step_index": current_step_index,
            "matched_steps": int(core.get("matched_steps", 0) or 0),
            "total_steps": len(sequence_steps),
            "step_status": step_statuses,
        }

    def on_bar_close(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = context.get("df")
        state_obj = context.get("state")
        symbol = str(getattr(state_obj, "symbol", "UNKNOWN") or "UNKNOWN")

        if df is None or state_obj is None:
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[{symbol}][A][on_bar_close][invalid_context] "
                f"strategy={self.name} strategy_id={self.strategy_id} "
                f"has_df={df is not None} has_state={state_obj is not None}"
            )
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
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[{symbol}][A][on_bar_close][backfill_not_ready] "
                f"strategy={self.name} strategy_id={self.strategy_id} bar_t={bar_ts} "
                f"backfill_status={backfill_status}"
            )
            return {
                "intent_id": f"{self.name}:{self.strategy_id}:{bar_ts}",
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "direction": self.direction,
                "reason_code": "BACKFILL_NOT_READY",
                "is_actionable": False,
                "evaluated_rules": ["BACKFILL_READY"],
                "evidence_refs": [{"type": "backfill_status", "value": backfill_status}],
                "t": bar_ts,
            }

        # Pillar 1: Evaluate context pre-conditions FIRST
        ctx = self._evaluate_context(state_obj)

        core = self._evaluate_sequence(df, state_obj)
        diagnostics = self._build_sequence_diagnostics(core)

        logger.debug(
            f"{PIPELINE_LOG_PREFIX}[{symbol}][A][on_bar_close][sequence_eval] "
            f"strategy={self.name} strategy_id={self.strategy_id} bar_t={bar_ts} "
            f"score={core.get('score')} matched_steps={core.get('matched_steps')} "
            f"missing_required={core.get('missing_required')} "
            f"origin_timestamp={core.get('origin_timestamp')} "
            f"progress_data={core.get('progress_data')}"
        )

        # Determine reason_code: context must pass AND sequence must match
        missing_required = bool(core["missing_required"])
        score_below_threshold = core["score"] < self.min_score

        if not ctx["passed"]:
            reason_code = "CONTEXT_FILTER_FAILED"
        elif missing_required or score_below_threshold:
            reason_code = "SEQUENCE_NOT_MATCHED"
        else:
            # Only trigger at the EXACT candle where last sequence event matched
            sequence_completed_t = core["progress_data"].get("sequence_completed_t", 0)
            triggered_t = core["progress_data"].get("triggered_t", 0)
            if triggered_t > 0 or bar_ts != sequence_completed_t:
                reason_code = "ALREADY_TRIGGERED"
            else:
                reason_code = "OK"

        if reason_code == "SEQUENCE_NOT_MATCHED":
            mismatch_causes: List[str] = []
            if missing_required:
                mismatch_causes.append("MISSING_REQUIRED_STEP")
            if score_below_threshold:
                mismatch_causes.append("SCORE_BELOW_THRESHOLD")

            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[{symbol}][A][on_bar_close][sequence_mismatch_detail] "
                f"strategy={self.name} strategy_id={self.strategy_id} bar_t={bar_ts} "
                f"mismatch_causes={mismatch_causes} "
                f"missing_required={missing_required} "
                f"missing_required_tags={diagnostics['missing_required_tags']} "
                f"score={core['score']} min_score={self.min_score} "
                f"score_below_threshold={score_below_threshold} score_gap={diagnostics['score_gap']} "
                f"matched_steps={core['matched_steps']} current_step_index={diagnostics['current_step_index']} "
                f"mismatch_reason={diagnostics['mismatch_reason']}"
            )

        if reason_code != "OK":
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[{symbol}][A][on_bar_close][intent_not_actionable] "
                f"strategy={self.name} strategy_id={self.strategy_id} bar_t={bar_ts} "
                f"reason_code={reason_code} score={core['score']} min_score={self.min_score} "
                f"missing_required={missing_required} failed_filters={ctx['failed_filters']} "
                f"matched_steps={core['matched_steps']} mismatch_reason={diagnostics['mismatch_reason']} "
                f"missing_required_tags={diagnostics['missing_required_tags']} "
                f"current_step_index={diagnostics['current_step_index']} "
                f"step_status={diagnostics['step_status']}"
            )

        strategy_obj = {
            "intent_id": f"{self.name}:{self.strategy_id}:{bar_ts}",
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "direction": self.direction,
            "symbol": symbol,
            "reason_code": reason_code,
            "is_actionable": reason_code == "OK",
            "score": core["score"],
            "origin_timestamp": core["origin_timestamp"],
            "sequence_diagnostics": diagnostics,
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
                    "missing_required_tags": diagnostics["missing_required_tags"],
                    "current_step_index": diagnostics["current_step_index"],
                    "step_status": diagnostics["step_status"],
                    "mismatch_reason": diagnostics["mismatch_reason"],
                },
                {
                    "rule": "MIN_SCORE_THRESHOLD",
                    "passed": core["score"] >= self.min_score,
                    "score": core["score"],
                    "min_score": self.min_score,
                    "score_gap": diagnostics["score_gap"],
                },
            ],
            "evidence_refs": [
                {"type": "strategy_progress", "ref": self.name},
                {"type": "sequence", "value": core["progress_data"].get("sequence", [])},
                {"type": "context_details", "value": ctx["details"]},
                {"type": "sequence_diagnostics", "value": diagnostics},
            ],
            "legacy_result": self.evaluate(df, context.get("signals", {}), state_obj),
            "exit_config": self.exit_config,
            "t": bar_ts,
        }

        logger.debug(
            f"{PIPELINE_LOG_PREFIX}[{symbol}][A][on_bar_close][strategy_progress] {strategy_obj}"
        )

        # Auto-reset sequence after successful trigger to prevent re-firing
        if strategy_obj.get("is_actionable"):
            self._reset_sequence_state(
                state_obj,
                triggered_t=bar_ts,
                last_processed_t=core["progress_data"].get("last_processed_t", 0),
                internal_candle_counter=core["progress_data"].get("internal_candle_counter", 0),
            )

        return strategy_obj
        

    def validate_entry(self, intent: Optional[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        if not intent:
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[B][validate_entry][reject] "
                f"strategy={self.name} strategy_id={self.strategy_id} reason_code=NO_INTENT"
            )
            return {
                "is_valid": False,
                "failed_rules": ["INTENT_MISSING"],
                "reason_code": "NO_INTENT",
                "evaluated_rules": [{"rule": "INTENT_PRESENT", "passed": False}],
            }

        intent_id = intent.get("intent_id", "N/A")
        intent_reason = intent.get("reason_code", "UNKNOWN")
        bar_t = intent.get("t", 0)

        if intent_reason == "BACKFILL_NOT_READY":
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[B][validate_entry][reject] "
                f"strategy={self.name} strategy_id={self.strategy_id} intent_id={intent_id} "
                f"t={bar_t} reason_code=BACKFILL_NOT_READY"
            )
            return {
                "is_valid": False,
                "failed_rules": ["BACKFILL_NOT_READY"],
                "reason_code": "BACKFILL_NOT_READY",
                "evaluated_rules": [{"rule": "BACKFILL_READY", "passed": False}],
            }

        if not intent.get("is_actionable"):
            propagated_reason = str(intent_reason or "NON_ACTIONABLE_INTENT").strip().upper() or "NON_ACTIONABLE_INTENT"
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[B][validate_entry][reject] "
                f"strategy={self.name} strategy_id={self.strategy_id} intent_id={intent_id} "
                f"t={bar_t} reason_code={propagated_reason} failed_rules=['{propagated_reason}']"
            )
            return {
                "is_valid": False,
                "failed_rules": [propagated_reason],
                "reason_code": propagated_reason,
                "evaluated_rules": [{"rule": "ACTIONABLE_INTENT", "passed": False}],
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
        size_value = float(te.get("size_value", te.get("size", exit_config.get("size_value", exit_config.get("size", size_from_env)))))
        size_mode = str(te.get("size_mode", exit_config.get("size_mode", "FIXED_UNITS"))).upper()
        if size_mode not in VALID_SIZE_MODES:
            size_mode = "FIXED_UNITS"

        # Entry type
        entry_type = te.get("entry_type", exit_config.get("entry_type", "MARKET"))
        if entry_type not in VALID_ENTRY_TYPES:
            entry_type = "MARKET"

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
            "entry_type": entry_type,
            "entry_policy": te.get("entry_policy", exit_config.get("entry_policy", "IMMEDIATE")),
            "direction": intent.get("direction", self.direction),
            "size": size_value,
            "size_value": size_value,
            "size_mode": size_mode,
            "magic_number": self.magic_number,
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
