import logging
from engine.logging_common import get_logger
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = get_logger(__name__)


class SweepSignal(BaseSignal):
    """
    Monitors identified liquidity levels (OBs) for stop hunts.
    Implements State Machine for OBs (PENDING, TOUCHED, SWEPT, BROKEN_PENDING, DEAD)
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
            if ob.get("status") == "DEAD":
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
                            ob["status"] = "DEAD"
                    else:
                        # Touches the OB again -> Trap!
                        ob["break_counter"] = 0
                        ob["status"] = "SWEPT"
                        ob["_just_swept"] = True  # Flag to trigger signal this tick
                else:
                    # Not broken yet. Check if it penetrates the bottom
                    if c_l < ob_bottom:
                        if c_c < ob_bottom:
                            ob["status"] = "BROKEN_PENDING"
                            ob["_just_swept"] = True # It broke, but it's a sweep attempt
                        else:
                            ob["status"] = "SWEPT"
                            ob["_just_swept"] = True
                    elif c_l <= ob_top:
                        ob["status"] = "TOUCHED"

            else: # BEARISH
                if status == "BROKEN_PENDING":
                    # Check for 2 candles complete outside
                    if c_l > ob_top:
                        ob["break_counter"] += 1
                        if ob["break_counter"] >= 2:
                            ob["status"] = "DEAD"
                    else:
                        # Touches the OB again -> Trap!
                        ob["break_counter"] = 0
                        ob["status"] = "SWEPT"
                        ob["_just_swept"] = True
                else:
                    # Check if it penetrates the top
                    if c_h > ob_top:
                        if c_c > ob_top:
                            ob["status"] = "BROKEN_PENDING"
                            ob["_just_swept"] = True
                        else:
                            ob["status"] = "SWEPT"
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
        regime = str(getattr(state_obj, "market_regime", "SIDEWAYS") or "SIDEWAYS")
        history = getattr(state_obj, "signal_history", [])
        history = history if isinstance(history, list) else []

        triggered_sweep = None

        obs = getattr(state_obj, "obs", [])
        for ob in obs:
            if not isinstance(ob, dict):
                continue
                
            if ob.pop("_just_swept", False):
                # Generates a signal
                is_bullish = ob.get("ob_type") == "BULLISH"
                tag = self.TAG_BULL if is_bullish else self.TAG_BEAR
                target_price = ob.get("bottom") if is_bullish else ob.get("top")
                
                # Regime Check
                valid = False
                if is_bullish and regime in ["TREND_UP", "SIDEWAYS"]: valid = True
                if not is_bullish and regime in ["TREND_DN", "SIDEWAYS"]: valid = True

                if valid:
                    already_swept = any(
                        isinstance(s, dict)
                        and s.get("tag") == tag
                        and self._to_float(s.get("price_swept")) == target_price
                        and int(s.get("t", -1)) == c_t
                        for s in history
                    )
                    
                    if not already_swept:
                        triggered_sweep = {
                            "tag": tag,
                            "t": c_t,
                            "price_swept": target_price,
                            "source_type": "OB_" + ob.get("ob_type", "UNKNOWN"),
                            "source_t": ob.get("t_start"),
                            "fidelity": 0.8,
                            "market_regime": regime,
                        }
                        logger.info(
                            f"[t={c_t}] [{symbol}] [calculate] 4... SWEEP DETECTED: {ob['status']} (Candle Close): {tag} @ {target_price}"
                        )

                        transient = getattr(state_obj, "transient_signals", None)
                        if isinstance(transient, dict):
                            transient[tag] = triggered_sweep
                            transient["ob_state"] = state_obj.obs # Emit OBs to Redis

                        request_ai_update = getattr(state_obj, "request_ai_update", None)
                        if callable(request_ai_update):
                            request_ai_update("STOP_HUNT")
                            request_ai_update("OB_STATE_CHANGE")
                        # Emitting only ONE sweep signal max per tick to match old parity
                        break 

        return triggered_sweep
