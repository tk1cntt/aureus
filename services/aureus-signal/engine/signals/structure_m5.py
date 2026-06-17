"""
M5 Market Structure Detection - On-the-Fly Resampling Approach

Implements CHoCH/BOS/Order Block detection on M5 timeframe by resampling
from M1 candles, using separate transient ZigZag state per calculate() call.
Follows pattern from CISDMultiTFSignal for MTF handling.
"""
import logging
import numpy as np
from engine.logging_common import get_logger
from .base import BaseSignal, SignalType
from .resampler import resample_to_tf
from .pivots import get_confirmed_pivots, label_pivots_pro
from engine.common.zigzag_pro2 import ZigZagPro
from typing import Dict, Any, Optional, List

logger = get_logger(__name__)


class StructureSignalM5(BaseSignal):
    """
    Detects M5 Market Structure Shifts via on-the-fly M1->M5 resampling.

    Key features:
    - Resamples M1 candles to M5 using resample_to_tf(df, 'M5')
    - Uses private transient ZigZag instance (_zz_m5) per symbol
    - Stores swing_points in instance variable (_swing_points_m5), NOT in state_obj
    - Excludes forming candle before processing (follows cisd_mtf.py pattern)
    - Emits tags: choch_m5_up/down, bos_m5_up/down
    - OB state stored in transient_signals['ob_state_m5']
    """

    signal_type = SignalType.EVENT

    # Tags specific to M5 timeframe
    TAG_CHOCH_M5_UP = "choch_m5_up"
    TAG_CHOCH_M5_DN = "choch_m5_down"
    TAG_BOS_M5_UP = "bos_m5_up"
    TAG_BOS_M5_DN = "bos_m5_down"

    def __init__(self):
        super().__init__("Market Structure Processor M5 (On-the-Fly)")

        # Private ZigZagPro instance for M5 only
        # TODO: ZigZagPro params (ext_period=5, min_amplitude=100) copied from M1.
        #       M5 candles have larger range — may need tuning after initial testing.
        self._zz_m5 = ZigZagPro(ext_period=5, min_amplitude=100)

        # Transient M5 swing points (NOT persisted in state_obj)
        self._swing_points_m5 = []
        self._obs_m5 = []

    def calculate(self, df: object, state_obj: object, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Calculate M5 CHoCH/BOS/OB signals from M1 DataFrame.

        Args:
            df: M1 OHLCV DataFrame with columns [t, o, h, l, c]
            state_obj: SymbolState object with transient_signals dict
            kwargs: Additional arguments (ignored)

        Returns:
            Latest signal dict if detected, None otherwise
        """
        # 1. Resample M1 -> M5
        ht_df = resample_to_tf(df, 'M5')
        if ht_df is None or len(ht_df) < 5:
            return None

        # 2. Exclude forming candle (pattern from cisd_mtf.py line 86)
        df_m5_completed = ht_df.iloc[:-1]
        if len(df_m5_completed) < 3:
            return None

        # 3. Convert to numpy arrays for efficient processing
        t_values = df_m5_completed['t'].to_numpy(dtype=np.int64, copy=False)
        h_values = df_m5_completed['h'].to_numpy(dtype=np.float64, copy=False)
        l_values = df_m5_completed['l'].to_numpy(dtype=np.float64, copy=False)
        o_values = df_m5_completed['o'].to_numpy(dtype=np.float64, copy=False)
        c_values = df_m5_completed['c'].to_numpy(dtype=np.float64, copy=False)

        # Build timestamp map
        t_map = {int(t): i for i, t in enumerate(t_values)}

        # 4. Run ZigZag on completed M5 candles
        buffers = self._zz_m5.update(df_m5_completed, timeframe='M5', incremental=True)
        if buffers is None:
            return None

        # Get confirmed pivots - ZigZagPro.update() returns {'up', 'dn', 'type'}, 'times' from df
        raw_pivots = get_confirmed_pivots(
            buffers.get('up', []),
            buffers.get('dn', []),
            buffers.get('type', []),  # Not 'types' - ZigZagPro uses singular
            df_m5_completed['t'].tolist()  # Use times from df, not buffers
        )

        if not raw_pivots or len(raw_pivots) == 0:
            return None

        # 5. Label pivots (HH/LL/LH/HL)
        labeled = label_pivots_pro(raw_pivots)

        # 6. Store transient M5 swing points (NOT in state_obj!)
        self._swing_points_m5 = labeled

        # 7. Scan for CHoCH/BOS events
        new_signals = self._scan_structure_m5(labeled, t_map, t_values, o_values, h_values, l_values, c_values, state_obj)

        # 8. Update transient_signals
        transient = getattr(state_obj, 'transient_signals', None)
        if transient is not None and isinstance(transient, dict):
            transient['ob_state_m5'] = {
                'active_obs': [
                    {
                        'top': ob.get('top'),
                        'bottom': ob.get('bottom'),
                        'ob_type': ob.get('ob_type'),
                        't_start': ob.get('t_start'),
                        'status': ob.get('status', 'PENDING'),
                        'break_counter': ob.get('break_counter', 0),
                        'mitigated': ob.get('mitigated', False),
                        't_mitigation': ob.get('t_mitigation', 0),
                    }
                    for ob in self._obs_m5
                ]
            }

        # 9. Verify mitigation on M5 OBs
        self._verify_mitigations_m5(t_values, o_values, h_values, l_values, c_values, state_obj)

        if new_signals:
            return new_signals[-1]
        return None

    def _scan_structure_m5(self, points, t_map, t_values, o_values, h_values, l_values, c_values, state_obj):
        """Scan M5 pivots for CHoCH/BOS signals."""
        new_signals = []

        for pivot_idx in range(len(points)):
            p = points[pivot_idx]
            if p.get('is_choch') or p.get('is_bos'):
                continue

            if p.get('type') not in ['HH', 'LL']:
                continue

            pivot_price = float(p['price'])
            pivot_t = int(p['t'])
            pivot_t_int = pivot_t

            is_bullish = p['is_high']

            # Find breakout candle
            pivot_df_idx = t_map.get(pivot_t_int, -1)
            if pivot_df_idx == -1:
                start_idx = 0
            else:
                start_idx = pivot_df_idx + 1

            if is_bullish:
                breakout_mask = h_values[start_idx:] > pivot_price
            else:
                breakout_mask = l_values[start_idx:] < pivot_price

            breakout_positions = np.flatnonzero(breakout_mask)
            if breakout_positions.size == 0:
                continue

            k = start_idx + int(breakout_positions[0])
            breakout_t = int(t_values[k])

            # Find opposing extreme
            zone_base_idx = -1
            if is_bullish:
                min_price = float('inf')
                for m in range(pivot_idx + 1, len(points)):
                    if points[m]['type'] == 'LL' and points[m]['t'] < breakout_t:
                        if points[m]['price'] < min_price:
                            min_price = points[m]['price']
                            zone_base_idx = m
            else:
                max_price = float('-inf')
                for m in range(pivot_idx + 1, len(points)):
                    if points[m]['type'] == 'HH' and points[m]['t'] < breakout_t:
                        if points[m]['price'] > max_price:
                            max_price = points[m]['price']
                            zone_base_idx = m

            if zone_base_idx == -1:
                # BOS: Break of Structure without opposing extreme → continuation
                points[pivot_idx]['is_bos'] = True
                tag = self.TAG_BOS_M5_UP if is_bullish else self.TAG_BOS_M5_DN
                logger.info(f"[t={breakout_t}] [M5] [bos] BOS DETECTED: {tag} @ {pivot_price}")
                new_signals.append({
                    'tag': tag,
                    't': breakout_t,
                    'value': tag,
                    'data': {
                        'price': pivot_price,
                        'breakout_t': breakout_t,
                        'pivot_t': pivot_t,
                    }
                })
            else:
                # CHOCH: Valid structural break with opposing extreme → create OB
                points[pivot_idx]['is_choch'] = True

                # Find Order Block zone
                pivot_df_idx = t_map[pivot_t]
                breakout_df_idx = t_map[breakout_t]

                if not is_bullish:
                    window = h_values[pivot_df_idx: breakout_df_idx + 1]
                    extreme_idx = pivot_df_idx + int(np.argmax(window))
                else:
                    window = l_values[pivot_df_idx: breakout_df_idx + 1]
                    extreme_idx = pivot_df_idx + int(np.argmin(window))

                candle_h = float(h_values[extreme_idx])
                candle_l = float(l_values[extreme_idx])
                candle_o = float(o_values[extreme_idx])
                candle_c = float(c_values[extreme_idx])
                candle_t = int(t_values[extreme_idx])

                candle_range = candle_h - candle_l
                candle_body = abs(candle_c - candle_o)
                body_ratio = (candle_body / candle_range) if candle_range > 0 else 0
                quality = "HIGH" if body_ratio > 0.8 else "MEDIUM" if body_ratio > 0.5 else "LOW"

                ob = {
                    'ob_type': "BULLISH" if is_bullish else "BEARISH",
                    'top': candle_h,
                    'bottom': candle_l,
                    't_start': candle_t,
                    'pivot_t': pivot_t,
                    't_breakout': breakout_t,
                    'quality': quality,
                    'status': "PENDING",
                    'break_counter': 0,
                    'body_ratio': round(body_ratio, 2),
                }
                self._obs_m5.append(ob)

                tag = self.TAG_CHOCH_M5_UP if is_bullish else self.TAG_CHOCH_M5_DN
                logger.info(f"[t={breakout_t}] [M5] [choch] CHOCH DETECTED: {tag} @ {pivot_price}")
                new_signals.append({
                    'tag': tag,
                    't': breakout_t,
                    'value': tag,
                    'data': {
                        'price': pivot_price,
                        'breakout_t': breakout_t,
                        'ob': ob,
                        'pivot_t': pivot_t,
                    }
                })

        return new_signals

    def _verify_mitigations_m5(self, t_values, o_values, h_values, l_values, c_values, state_obj):
        """Check M5 OBs for price touches after breakout."""
        latest_t = int(t_values[-1])

        for ob in self._obs_m5:
            if ob.get('mitigated'):
                continue

            t_breakout = ob.get('t_breakout', 0)
            if latest_t <= t_breakout:
                continue

            start_idx = int(np.searchsorted(t_values, int(t_breakout), side='right'))
            if start_idx >= len(t_values):
                continue

            is_bullish = (ob['ob_type'] == 'BULLISH')

            if is_bullish:
                touch_positions = np.flatnonzero(l_values[start_idx:] <= float(ob['top']))
            else:
                touch_positions = np.flatnonzero(h_values[start_idx:] >= float(ob['bottom']))

            if touch_positions.size == 0:
                continue

            idx = start_idx + int(touch_positions[0])
            ob['mitigated'] = True
            ob['t_mitigation'] = int(t_values[idx])
