from .base import BaseSignal
import logging
import pandas as pd
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("aureus-pivots")

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
                  redis_client: Any = None, symbol: str = None) -> Optional[Dict[str, Any]]:
        # Find if this symbol's last received T is in this DF
        if not df.empty:
            last_val = df.iloc[-1]['t']
            tail_vals = df['t'].tail(5).tolist()
            logger.info(f"====>3. Entering PivotSignal.calculate {symbol} last_t={last_val} df_len={len(df)} tail_ts={tail_vals}")

        # 1. Initialize engine in state if not present
        if not hasattr(state_obj, 'zigzag_engine') or state_obj.zigzag_engine is None:            
            state_obj.zigzag_engine = ZigZagPro(
                ext_period=self.ext_period,
                min_amplitude=self.min_amplitude,
                min_motion=self.min_motion,
                use_smaller_tf=self.use_smaller_tf,
                point=self.point,
                digits=self.digits
            )

        # 1b. Update parameters dynamically if using percentage
        if self.min_amplitude_pct is not None and len(df) > 0:
            last_close = float(df.iloc[-1]['c'])
            # Calculate dynamic amplitude in points
            # Formula: (Price * Pct / 100) / Point
            dynamic_amp_points = int(round((last_close * self.min_amplitude_pct / 100) / self.point))
            
            # Ensure it doesn't fall below a sane minimum (e.g. 1 point)
            dynamic_amp_points = max(1, dynamic_amp_points)
            
            state_obj.zigzag_engine.update_params(min_amplitude=dynamic_amp_points)

        # 2. Run stateful calculation (updates internal buffers)
        # O(1) Optimization: Always use incremental mode
        buffers = state_obj.zigzag_engine.update(
            df, timeframe=self.timeframe, sub_candles_by_tf=sub_candles_by_tf,
            incremental=True
        )

        # 3. Extract ALL pivots from buffers
        raw_pivots = get_confirmed_pivots(buffers['up'], buffers['dn'], buffers['type'], df['t'].tolist())
        if not raw_pivots:
            return None

        # 4. Label pivots (HH, LL, LH, HL)
        labeled_pivots = label_pivots_pro(raw_pivots)

        # 5. NON-REPAINT: Skip unconfirmed pivots at the end.
        #    The ZigZag's last pivot is ALWAYS tentative — it can move
        #    to the next bar as price extends. Only pivots that have a
        #    subsequent pivot after them are "confirmed" and stable.
        #    For Outside Bars (two pivots at the same index), skip both.
        if labeled_pivots:
            last_pivot_index = labeled_pivots[-1]['index']
            confirmed_pivots = [p for p in labeled_pivots if p['index'] < last_pivot_index]
        else:
            confirmed_pivots = []

        if not confirmed_pivots:
            return None

        # 6. Synchronize with state_obj.swing_points
        existing_swing_points = getattr(state_obj, 'swing_points', [])
        
        # We already know confirmed_pivots has data if we reached here, 
        # but labeled_pivots contains the full window (including tentative last pivot).
        # We merge with labeled_pivots to ensure the tentative end is updated too.
        earliest_new_t = labeled_pivots[0]['t']
        
        # STEP A: Keep historical pivots strictly before the new window
        historical_pivots = [p for p in existing_swing_points if p['t'] < earliest_new_t]
        
        # STEP B: Merge historical and new pivots
        merged_raw = historical_pivots + labeled_pivots
            
        # STEP C: Re-label HH/LL/LH/HL across the merged boundary for consistency
        merged_labeled = label_pivots_pro(merged_raw)
        
        # STEP D: Preserve Metadata (is_choch, ob, fvg, breakout_t, etc.)
        # Build lookup for all relevant metadata-carrying pivots
        existing_meta = {
            p['t']: p for p in existing_swing_points 
            if any(p.get(k) for k in ['broken', 'is_choch', 'ob', 'fvg', 'breakout_t'])
        }
        
        for p in merged_labeled:
            meta = existing_meta.get(p['t'])
            # Only restore if it's the same extreme type (High vs Low)
            if meta and p['is_high'] == meta['is_high']:
                p.update({
                    'is_choch': meta.get('is_choch'),
                    'breakout_t': meta.get('breakout_t'),
                    'broken': meta.get('broken'),
                    'choch_type': meta.get('choch_type'),
                    'chochConfirmingPointIndex': meta.get('chochConfirmingPointIndex'),
                    'chochZoneBasePointIndex': meta.get('chochZoneBasePointIndex'),
                    'ob': meta.get('ob'),
                    'fvg': meta.get('fvg'),
                    'structure_label': meta.get('structure_label')
                })
        
        state_obj.swing_points = merged_labeled

        # Limit memory (keep enough history for CHOCH/OB to function)
        if len(state_obj.swing_points) > 500:
            state_obj.swing_points = state_obj.swing_points[-500:]

        # Return latest for signaling/strategies
        if state_obj.swing_points:
            # --- DB Persistence Logic ---
            # The last pivot is ALWAYS tentative (repainting). 
            # The second-to-last might still adjust slightly in extreme outside-bar cases.
            # The 3rd-to-last pivot is completely mathematically locked.
            if redis_client and symbol and len(state_obj.swing_points) >= 3:
                stable_pivot = state_obj.swing_points[-3]
                
                # Check if we've already synced this stable pivot
                last_db_time = int(state_obj.tracking_vars.get('last_db_pivot_time', 0))
                if stable_pivot['t'] > last_db_time:
                    # Sync to Writer via robust stream
                    stream_key = f"aureus:stream:{symbol}:swing_point"
                    logger.info(f"====>5. PivotSignal sync stable pivot {symbol} t={stable_pivot['t']} price={stable_pivot['price']} type={stable_pivot.get('type')}")
                    asyncio.create_task(redis_client.xadd(stream_key, {
                        "t": str(stable_pivot['t']),
                        "price": str(stable_pivot['price']),
                        "is_high": "true" if stable_pivot['is_high'] else "false",
                        "type": stable_pivot['type']
                    }))
                    
                    state_obj.tracking_vars['last_db_pivot_time'] = stable_pivot['t']

            latest = state_obj.swing_points[-1]
            return {
                "tag": latest['type'].lower(),
                "price": latest['price'],
                "t": latest['t'],
                "is_high": latest['is_high']
            }

        return None
