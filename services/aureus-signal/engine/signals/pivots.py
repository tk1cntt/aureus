from .base import BaseSignal
import logging
from engine.logging_common import get_logger
import pandas as pd
import asyncio
from typing import Dict, Any, Optional

logger = get_logger(__name__)
# Use the strict 1:1 MQL5 port (zigzag_pro2.py)
from ..common.zigzag_pro2 import ZigZagPro, get_confirmed_pivots, label_pivots_pro


class PivotSignal(BaseSignal):
    """
    Identifies and labels local swing points (HH, LL, LH, HL).
    Uses the stateful ZigZagPro engine — strict 1:1 port of MQL5.

    NON-REPAINTING: Only emits "confirmed" pivots. A pivot is confirmed
    when a subsequent pivot of the opposite type appears after it.
    The last (tentative) pivot is always skipped until confirmed by
    subsequent price action, preventing ghost/duplicate pivots.

    Args:
        ext_period:     iExtPeriod — Window size for extremum detection (min 2).
        min_amplitude:  iMinAmplitude — Min amplitude in broker POINTS (Static).
        min_amplitude_pct: Dynamic amplitude as % of current price (Overrides min_amplitude).
        min_motion:     iMinMotion — Min motion in POINTS for recalc optimization.
        use_smaller_tf: iUseSmallerTFforEB — Use sub-TF for Outside Bar analysis.
        point:          _Point — Broker's point value.
        digits:         _Digits — Decimal digits.
        timeframe:      Timeframe of the data.
    """
    TAG = "pivots"

    def __init__(
        self,
        ext_period: int = 5,
        min_amplitude: int = 100,
        min_amplitude_pct: Optional[float] = None,
        min_motion: int = 1,
        use_smaller_tf: bool = True,
        point: float = 0.01,
        digits: int = 2,
        timeframe: str = "M1"
    ):
        super().__init__("Professional ZigZag Pivots")
        self.ext_period = ext_period
        self.min_amplitude = min_amplitude
        self.min_amplitude_pct = min_amplitude_pct
        self.min_motion = min_motion
        self.use_smaller_tf = use_smaller_tf
        self.point = point
        self.digits = digits
        self.timeframe = timeframe

    def calculate(self, df: pd.DataFrame, state_obj: Any,
                  sub_candles_by_tf: dict = None,
                  redis_client: Any = None, symbol: str = None,
                  **kwargs) -> Optional[Dict[str, Any]]:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return None

        required_cols = {"t", "c", "h", "l"}
        if not required_cols.issubset(df.columns):
            logger.warning(
                "[%s] [calculate] Missing required columns for pivots: %s",
                symbol or "UNKNOWN",
                sorted(required_cols.difference(set(df.columns))),
            )
            return None

        # --- DEFENSIVE GUARDS: Clean malformed input ---
        if df[list(required_cols)].isna().any().any():
            df = df.dropna(subset=list(required_cols)).copy()

        if df.empty:
            return None

        if not df['t'].is_monotonic_increasing or df['t'].duplicated().any():
            logger.warning("[%s] [calculate] df['t'] is not sorted or has duplicates. Repairing.", symbol or "UNKNOWN")
            df = df.drop_duplicates(subset=['t'], keep='last').sort_values(by='t').reset_index(drop=True)
        # --- END DEFENSIVE GUARDS ---

        try:
            last_val = int(df.iloc[-1]["t"])
            tail_vals = df["t"].tail(5).tolist()
        except Exception as e:
            # Degrade gracefully: keep processing even if debug-tail extraction is malformed.
            last_val = "UNKNOWN"
            tail_vals = []
            logger.warning(
                "[%s] [calculate] Tail timestamp parse failed, continuing safely: %s",
                symbol or "UNKNOWN",
                e,
            )

        logger.debug(
            f"[t={last_val}] [{symbol}] [calculate] 1... Entering PivotSignal.calculate "
            f"{symbol} last_t={last_val} df_len={len(df)} tail_ts={tail_vals}"
        )

        # 1. Initialize engine in state if not present
        if not hasattr(state_obj, "zigzag_engine") or state_obj.zigzag_engine is None:
            state_obj.zigzag_engine = ZigZagPro(
                ext_period=self.ext_period,
                min_amplitude=self.min_amplitude,
                min_motion=self.min_motion,
                use_smaller_tf=self.use_smaller_tf,
                point=self.point,
                digits=self.digits,
            )

        if not hasattr(state_obj, "tracking_vars") or not isinstance(getattr(state_obj, "tracking_vars", None), dict):
            state_obj.tracking_vars = {}

        if not hasattr(state_obj, "swing_points") or not isinstance(getattr(state_obj, "swing_points", None), list):
            state_obj.swing_points = []

        # 1b. Update parameters dynamically if using percentage
        if self.min_amplitude_pct is not None:
            try:
                last_close = float(df.iloc[-1]["c"])
                dynamic_amp_points = int(round((last_close * self.min_amplitude_pct / 100) / self.point))
                dynamic_amp_points = max(1, dynamic_amp_points)
                state_obj.zigzag_engine.update_params(min_amplitude=dynamic_amp_points)
            except Exception as e:
                logger.warning(f"[{symbol}] [calculate] Dynamic amplitude update skipped: {e}")

        # 2. Run stateful calculation (updates internal buffers)
        buffers = state_obj.zigzag_engine.update(
            df,
            timeframe=self.timeframe,
            sub_candles_by_tf=sub_candles_by_tf,
            incremental=True,
        )

        # 3. Extract ALL pivots from buffers
        raw_pivots = get_confirmed_pivots(buffers["up"], buffers["dn"], buffers["type"], df["t"].tolist())
        if not raw_pivots:
            return None

        # 4. Label pivots (HH, LL, LH, HL)
        labeled_pivots = label_pivots_pro(raw_pivots)
        if not labeled_pivots:
            return None

        # 5. NON-REPAINT: Skip unconfirmed pivots at the end.
        last_pivot_index = labeled_pivots[-1]["index"]
        confirmed_pivots = [p for p in labeled_pivots if p["index"] < last_pivot_index]
        if not confirmed_pivots:
            return None

        # 6. Synchronize with state_obj.swing_points
        existing_swing_points_raw = state_obj.swing_points
        existing_swing_points = []
        dropped_invalid = 0

        for p in existing_swing_points_raw:
            if not isinstance(p, dict):
                dropped_invalid += 1
                continue

            t_val = p.get("t")
            is_high = p.get("is_high")

            # Continuity fallback: infer `is_high` from structure label if possible.
            if is_high is None:
                pivot_type = p.get("type")
                if pivot_type in {"HH", "LH"}:
                    is_high = True
                elif pivot_type in {"LL", "HL"}:
                    is_high = False

            if t_val is None or is_high is None or is_high not in (True, False):
                dropped_invalid += 1
                continue

            if p.get("is_high") is None:
                p = {**p, "is_high": is_high}

            existing_swing_points.append(p)

        if dropped_invalid > 0:
            logger.warning(
                "[%s] [calculate] Dropped %s invalid historical swing points (kept=%s raw=%s)",
                symbol or "UNKNOWN",
                dropped_invalid,
                len(existing_swing_points),
                len(existing_swing_points_raw),
            )

        earliest_new_t = labeled_pivots[0].get("t")
        if earliest_new_t is None and confirmed_pivots:
            earliest_new_t = confirmed_pivots[0].get("t")

        if earliest_new_t is None:
            logger.warning(
                "[%s] [calculate] Unable to determine earliest_new_t, preserving existing swing_points",
                symbol or "UNKNOWN",
            )
            earliest_new_t = max((p.get("t", 0) for p in existing_swing_points), default=0) + 1

        # STEP A: Keep historical pivots strictly before the new window
        historical_pivots = [p for p in existing_swing_points if p.get("t") < earliest_new_t]

        # STEP B: Merge historical and new pivots
        merged_raw = historical_pivots + labeled_pivots

        # STEP C: Re-label HH/LL/LH/HL across the merged boundary for consistency
        merged_labeled = label_pivots_pro(merged_raw)

        # STEP D: Preserve Metadata (is_choch, ob, fvg, breakout_t, etc.)
        existing_meta = {
            p["t"]: p
            for p in existing_swing_points
            if any(p.get(k) for k in ["broken", "is_choch", "ob", "fvg", "breakout_t"])
        }

        for p in merged_labeled:
            meta = existing_meta.get(p.get("t"))
            # Only restore if it's the same extreme type (High vs Low)
            if meta and p.get("is_high") == meta.get("is_high"):
                p.update(
                    {
                        "is_choch": meta.get("is_choch"),
                        "breakout_t": meta.get("breakout_t"),
                        "broken": meta.get("broken"),
                        "choch_type": meta.get("choch_type"),
                        "chochConfirmingPointIndex": meta.get("chochConfirmingPointIndex"),
                        "chochZoneBasePointIndex": meta.get("chochZoneBasePointIndex"),
                        "ob": meta.get("ob"),
                        "fvg": meta.get("fvg"),
                        "structure_label": meta.get("structure_label"),
                    }
                )

        state_obj.swing_points = merged_labeled

        logger.debug(
            "[%s] [calculate] Swing merge completed: historical=%s new=%s merged=%s",
            symbol or "UNKNOWN",
            len(historical_pivots),
            len(labeled_pivots),
            len(state_obj.swing_points),
        )

        # Limit memory (keep enough history for CHOCH/OB to function)
        if len(state_obj.swing_points) > 500:
            state_obj.swing_points = state_obj.swing_points[-500:]

        # Return latest for signaling/strategies
        if state_obj.swing_points:
            # --- DB Persistence Logic ---
            if redis_client and symbol and len(state_obj.swing_points) >= 3:
                stable_pivot = state_obj.swing_points[-3]

                # Check if we've already synced this stable pivot
                last_db_time = int(state_obj.tracking_vars.get("last_db_pivot_time", 0))
                if stable_pivot["t"] > last_db_time:
                    stream_key = f"aureus:stream:{symbol}:swing_point"
                    logger.debug(
                        f"[t={stable_pivot['t']}] [{symbol}] [calculate] 2... PivotSignal sync stable pivot "
                        f"{symbol} t={stable_pivot['t']} price={stable_pivot['price']} type={stable_pivot.get('type')}"
                    )
                    asyncio.create_task(
                        redis_client.xadd(
                            stream_key,
                            {
                                "t": str(stable_pivot["t"]),
                                "price": str(stable_pivot["price"]),
                                "is_high": "true" if stable_pivot["is_high"] else "false",
                                "type": stable_pivot["type"],
                            },
                        )
                    )

                    state_obj.tracking_vars["last_db_pivot_time"] = stable_pivot["t"]

            latest = state_obj.swing_points[-1]
            return {
                "tag": str(latest.get("type", "")).lower(),
                "price": float(latest.get("price", 0.0)),
                "t": int(latest.get("t", 0)),
                "is_high": bool(latest.get("is_high", False)),
            }

        return None
