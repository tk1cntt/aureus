import logging
from engine.logging_common import get_logger
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = get_logger(__name__)


class SweepSignal(BaseSignal):
    """
    Monitors identified liquidity levels (OBs) for stop hunts.
    Implements State Machine for OBs (PENDING, TOUCHED, SWEEP, BROKEN_PENDING, STOP_HUNT, CLEAN_BREAKOUT)
    and Regime-based filtering (Trend vs Sideways).
    """

    TAG_BULL = "sweep_bull"  # Price swept BELOW a target (Bullish setup)
    TAG_BEAR = "sweep_bear"  # Price swept ABOVE a target (Bearish setup)

    def __init__(self):
        super().__init__("Stop Hunt / Sweep Monitor")

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _update_ob_states(self, state_obj: Any, candle: pd.Series):
        if not hasattr(state_obj, "obs") or not isinstance(state_obj.obs, list):
            return

        c_h = float(candle['h'])
        c_l = float(candle['l'])
        c_c = float(candle['c'])
        c_t = int(candle['t'])

        for ob in state_obj.obs:
            if not isinstance(ob, dict):
                continue
            if ob.get("status") == "CLEAN_BREAKOUT":
                continue

            # Ensure fields exist
            ob.setdefault("status", "PENDING")
            ob.setdefault("break_counter", 0)

            status = ob["status"]
            is_bullish = ob.get("ob_type") == "BULLISH"

            ob_bottom = self._to_float(ob.get("bottom"))
            ob_top = self._to_float(ob.get("top"))
            
            if ob_bottom is None or ob_top is None:
                continue

            if is_bullish:
                if status == "BROKEN_PENDING":
                    # Check for 2 candles complete outside
                    if c_h < ob_bottom:
                        ob["break_counter"] += 1
                        if ob["break_counter"] >= 2:
                            ob["status"] = "CLEAN_BREAKOUT"
                    else:
                        # Reclaim into OB in 1-2 candles -> STOP_HUNT
                        ob["break_counter"] = 0
                        ob["status"] = "STOP_HUNT"
                        ob["_just_swept"] = True  # Flag to trigger signal this tick
                else:
                    # Not broken yet. Check if it penetrates the bottom
                    if c_l < ob_bottom:
                        if c_c < ob_bottom:
                            ob["status"] = "BROKEN_PENDING"
                            ob["_just_swept"] = True # It broke, but it's a sweep attempt
                        else:
                            ob["status"] = "SWEEP"
                            ob["_just_swept"] = True
                    elif c_l <= ob_top:
                        ob["status"] = "TOUCHED"

            else: # BEARISH
                if status == "BROKEN_PENDING":
                    # Check for 2 candles complete outside
                    if c_l > ob_top:
                        ob["break_counter"] += 1
                        if ob["break_counter"] >= 2:
                            ob["status"] = "CLEAN_BREAKOUT"
                    else:
                        # Reclaim into OB in 1-2 candles -> STOP_HUNT
                        ob["break_counter"] = 0
                        ob["status"] = "STOP_HUNT"
                        ob["_just_swept"] = True
                else:
                    # Check if it penetrates the top
                    if c_h > ob_top:
                        if c_c > ob_top:
                            ob["status"] = "BROKEN_PENDING"
                            ob["_just_swept"] = True
                        else:
                            ob["status"] = "SWEEP"
                            ob["_just_swept"] = True
                    elif c_h >= ob_bottom:
                        ob["status"] = "TOUCHED"

        # Garbage Collection đã bị gỡ bỏ hoàn toàn.
        # Engine dựa vào chu kì Daily Reset (5h sáng GMT+7) thông qua lệnh RECALCULATE
        # để dọn rác 1 lần/ngày. Đảm bảo Dashboard lưu giữ toàn bộ OB màu xám lịch sử.

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if state_obj is None or df is None or len(df) == 0:
            return None

        try:
            candle = df.iloc[-1]
            c_h = float(candle["h"])
            c_l = float(candle["l"])
            c_c = float(candle["c"])
            c_t = int(candle["t"])
        except (KeyError, TypeError, ValueError):
            return None

        symbol = getattr(state_obj, "symbol", "UNKNOWN")
        logger.debug(f"[t={c_t}] [{symbol}] [calculate] 1... SWEEP Signal Start")

        # 1. Update OB States
        self._update_ob_states(state_obj, candle)

        # 2. Check for triggered sweeps
        history = getattr(state_obj, "signal_history", [])
        history = history if isinstance(history, list) else []

        triggered_sweep = None

        obs = getattr(state_obj, "obs", [])
        for ob_idx, ob in enumerate(obs):
            if not isinstance(ob, dict):
                continue

            if ob.pop("_just_swept", False):
                is_bullish = ob.get("ob_type") == "BULLISH"
                current_status = str(ob.get("status", "")).strip().upper()
                mitigated = bool(ob.get("mitigated"))
                mitigated_status = "MITIGATED" if mitigated else "NOT_MITIGATED"
                suffix = "bull" if is_bullish else "bear"
                status_tag_by_state = {
                    "TOUCHED": f"sweep_touched_{suffix}",
                    "SWEEP": f"sweep_{suffix}",
                    "BROKEN_PENDING": f"sweep_broken_pending_{suffix}",
                    "STOP_HUNT": f"stop_hunt_{suffix}",
                    "CLEAN_BREAKOUT": f"clean_breakout_{suffix}",
                }
                status_tag = status_tag_by_state.get(current_status)
                if not status_tag:
                    continue

                target_price = ob.get("bottom") if is_bullish else ob.get("top")
                target_price = self._to_float(target_price)
                if target_price is None:
                    continue

                # Rule gate: If mitigated, event valid only when c_t - t_mitigation <= 300 seconds
                mitigation_age = 0
                if mitigated:
                    t_mitigation = ob.get("t_mitigation")
                    try:
                        t_mitigation_int = int(t_mitigation)
                    except (TypeError, ValueError):
                        logger.debug(
                            f"[t={c_t}] [{symbol}] [calculate] Skip sweep emit: missing/invalid t_mitigation"
                        )
                        continue

                    mitigation_age = c_t - t_mitigation_int
                    if mitigation_age <= 0 or mitigation_age > 300:
                        logger.debug(
                            f"[t={c_t}] [{symbol}] [calculate] Skip sweep emit: mitigated age={mitigation_age}s outside <= 300s"
                        )
                        continue

                def _same_sweep_event(rec: Any) -> bool:
                    if not isinstance(rec, dict):
                        return False

                    try:
                        rec_t = int(rec.get("t", -1))
                    except (TypeError, ValueError):
                        return False
                    if rec_t != c_t:
                        return False

                    rec_tag = str(rec.get("tag", "")).strip().lower()
                    rec_data = rec.get("data") if isinstance(rec.get("data"), dict) else {}

                    rec_price_direct = self._to_float(rec.get("price_swept"))
                    rec_price_data = self._to_float(rec_data.get("price_swept"))
                    rec_price = rec_price_data if rec_price_data is not None else rec_price_direct

                    if rec_tag == "sweep":
                        rec_value = rec.get("value")
                        if rec_value is None:
                            rec_value = rec_data.get("value")
                        rec_value_str = str(rec_value or "").strip().lower()
                        return rec_value_str == status_tag and rec_price == target_price

                    # Backward compatibility for legacy history shape: tag == sweep_*.
                    return rec_tag == status_tag and rec_price == target_price

                already_swept = any(_same_sweep_event(s) for s in history)

                if not already_swept:
                    triggered_sweep = {
                        "tag": "sweep",
                        "value": status_tag,
                        "t": c_t,
                        "data": {
                            "price_swept": target_price,
                            "source_type": "OB_" + ob.get("ob_type", "UNKNOWN"),
                            "source_t": ob.get("t_start"),
                            "status": current_status,
                            "ob_type": ob.get("ob_type", "UNKNOWN"),
                            "mitigated": mitigated
                        }
                    }
                    logger.info(
                        f"[t={c_t}] [{symbol}] [calculate] [{ob_idx}] SWEEP DETECTED: {current_status}/{mitigated_status} ({mitigation_age}s) : {status_tag} @ {target_price}/{c_c}"
                    )

                    transient = getattr(state_obj, "transient_signals", None)
                    if isinstance(transient, dict):
                        transient["sweep"] = triggered_sweep
                        transient["ob_state"] = state_obj.obs  # Emit OBs to Redis

                    # AI update is orchestrated centrally in runtime engine policy.
                    # Sweep signal layer only emits domain events to transient_signals.
                    # Emitting only ONE sweep signal max per tick to match old parity
                    break

        return triggered_sweep
