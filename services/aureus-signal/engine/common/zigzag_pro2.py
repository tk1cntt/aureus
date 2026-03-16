"""
Strict 1:1 Port of AlexSTAL_ZigZagProf_Optim.mq5 (Copyright 2011, AlexSTAL)
http://www.alexstal.ru | Optimized by FAI.ABC

All arrays use ASCENDING index order (index 0 = oldest bar).
MQL5 uses DESCENDING (series) order via ArraySetAsSeries(true).
All index comparisons are carefully inverted to produce identical results.

Reference: phase-2/step-3/reference/zigzag_pro2_utf8.mq5 (495 lines)

Usage:
    from engine.common import ZigZagPro, ExtremumType, PivotState
    from engine.common import get_confirmed_pivots, label_pivots_pro
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from enum import IntEnum
import logging

logger = logging.getLogger("aureus-signal.zigzag")

from .outside_bar import OutsideBarAnalyzer, OrderFormation


# ============================================================================
# Port of enum ExtremumAnalysisResult (Lines 58-66)
# ============================================================================
class ExtremumType(IntEnum):
    NONE = 0
    PEAK = 1              # Candle is a potential peak
    TROUGH = -1           # Candle is a potential trough
    OUTSIDE_BULLISH = 2   # Low formed first, then High (bullish engulfing)
    OUTSIDE_BEARISH = -2  # High formed first, then Low (bearish engulfing)


class PivotState(IntEnum):
    UNKNOWN = 0
    LAST_PEAK = 1
    LAST_TROUGH = -1


class OBMatrixCase(IntEnum):
    NONE = 0
    PENDING = 1
    BREAKOUT_UP = 2
    BREAKOUT_DOWN = 3
    DEFAULT_EXIT = 4


def normalize_double(value: float, digits: int) -> float:
    """
    Port of MQL5's NormalizeDouble().
    Rounds a floating-point number to the specified number of decimal digits.
    """
    if digits < 0:
        return value
    factor = 10 ** digits
    return round(value * factor) / factor


class ZigZagPro:
    """
    Strict 1:1 port of AlexSTAL_ZigZagProf_Optim.mq5.

    Args:
        ext_period:     iExtPeriod  — Number of bars for extremum window (min 2). Line 29.
        min_amplitude:  iMinAmplitude — Min price amplitude in broker POINTS. Line 31.
        min_motion:     iMinMotion — Min motion in POINTS for recalc optimization. Line 33.
        use_smaller_tf: iUseSmallerTFforEB — Use sub-TF for Outside Bar. Line 35.
        point:          _Point — Broker's point value (e.g. 0.01 for XAUUSD). Line 79.
        digits:         _Digits — Decimal digits (e.g. 2 for XAUUSD). Line 79.
    """

    EMPTY_VALUE = 0.0  # MQL5 EMPTY_VALUE for DRAW_ZIGZAG buffers

    def __init__(
        self,
        ext_period: int = 3,
        min_amplitude: int = 2,
        min_motion: int = 0,
        use_smaller_tf: bool = True,
        point: float = 0.01,
        digits: int = 2
    ):
        # --- Port of OnInit() lines 72-109 ---

        # Line 73-76: ExtPeriod = max(2, iExtPeriod)
        self.ext_period: int = max(2, ext_period)

        # Lines 78-79: MP = NormalizeDouble(MinAmplitude * _Point, _Digits)
        self.mp: float = normalize_double(min_amplitude * point, digits)

        # Lines 81-85: MinMotion = max(1, iMinMotion); MM = NormalizeDouble(MinMotion * _Point, _Digits)
        _min_motion = max(1, min_motion) if min_motion >= 1 else 1
        self.mm: float = normalize_double(_min_motion * point, digits)

        self.point = point
        self.digits = digits

        # Delegate Outside Bar to dedicated module
        self.ob_analyzer = OutsideBarAnalyzer()

        # --- Indicator Buffers (ascending order) ---
        # Lines 40-43, 88-94
        self.up: List[float] = []     # UP[] buffer
        self.dn: List[float] = []     # DN[] buffer
        self.ob: List[float] = []     # OB[] buffer — caches OrderFormation results (NOT comb_res)
        self.times: List[int] = []    # T[] buffer (for sliding window stability)

        # --- State Variables ---
        # Line 46: LastBarTime
        self.last_bar_time: int = 0
        # Line 48: LastBarLastHigh, LastBarLastLow
        self.last_bar_last_high: float = 0.0
        self.last_bar_last_low: float = 0.0
        # Line 50: TimeFirstExtBar
        self.time_first_ext_bar: int = 0
        # Line 56: DownloadHistory
        self.download_history: bool = True
        # For incremental recalculation (MQL5's prev_calculated)
        self.prev_calculated: int = 0

        # Python addition: stores ExtremumType per bar for pivot ordering
        self.type_buffer: List[int] = []
        
        # O(1) Optimization: Indices of the most recent confirmed extremums
        # Story 5.1: Mother Bar Tracking & Sliding Window stability
        self.last_up_idx: int = -1
        self.last_dn_idx: int = -1
        self.last_mother_idx: int = -1
        self.valid_indices: List[int] = []
        self.first_bar_time: int = 0

        # --- Story 2.1: OB Matrix State Machine ---
        self.ob_waiting: bool = False
        self.ob_high: float = 0.0
        self.ob_low: float = 0.0
        self.ob_index: int = -1
        self.ob_count: int = 0
        self.last_piv_type: PivotState = PivotState.UNKNOWN
        self.current_ob_case: OBMatrixCase = OBMatrixCase.NONE

    def normalize_double(self, value: float) -> float:
        """Helper to call module-level normalize_double with self.digits."""
        return normalize_double(value, self.digits)

    def update_params(self, min_amplitude: Optional[int] = None, min_motion: Optional[int] = None):
        """
        Dynamically update ZigZag parameters without resetting buffers.
        Recalculates self.mp and self.mm using the same point/digits.
        """
        if min_amplitude is not None:
            self.mp = normalize_double(min_amplitude * self.point, self.digits)
        
        if min_motion is not None:
            _min_motion = max(1, min_motion) if min_motion >= 1 else 1
            self.mm = normalize_double(_min_motion * self.point, self.digits)

    def _handle_window_drift(self, df: pd.DataFrame):
        """
        Detects if the input DataFrame has shifted (sliding window).
        Adjusts internal buffers and indices to stay synchronized.
        """
        if not self.times or len(df) == 0:
            return

        new_t0 = int(df.iloc[0]['t'])
        if new_t0 == self.times[0]:
            return

        # Try to find where the new first timestamp was in our old buffer
        try:
            shift = self.times.index(new_t0)
        except ValueError:
            # Timestamp not found -> Big gap or full reload required
            self.download_history = True
            return

        if shift <= 0:
            return # Should not happen with sliding window (only forward)

        # Shift buffers
        self.up = self.up[shift:]
        self.dn = self.dn[shift:]
        self.ob = self.ob[shift:]
        self.type_buffer = self.type_buffer[shift:]
        self.times = self.times[shift:]

        # Adjust indices
        self.last_up_idx = max(-1, self.last_up_idx - shift) if self.last_up_idx != -1 else -1
        self.last_dn_idx = max(-1, self.last_dn_idx - shift) if self.last_dn_idx != -1 else -1
        self.last_mother_idx = max(-1, self.last_mother_idx - shift) if self.last_mother_idx != -1 else -1
        self.valid_indices = [idx - shift for idx in self.valid_indices if (idx - shift) >= 0]
        
        # Adjust prev_calculated
        self.prev_calculated = max(0, self.prev_calculated - shift)
        
        # If any pivot was in the dropped range, we might need a partial recalc, 
        # but for now we assume max_window is large enough.

    def _process_ob_matrix(
        self,
        df: pd.DataFrame,
        i: int,
        curr_h: float,
        curr_l: float,
        prev_h: float,
        prev_l: float,
        let: int,
        last_up: float,
        last_dn: float,
        last_up_bar: int,
        last_dn_bar: int,
        recalc_start: int
    ) -> bool:
        """
        Implementation of the OB decision matrix (Story 2.1) - POST-PROCESS MODE.
        Handles OB detection, Pending state (IB), and Breakout logic.
        
        This method runs AFTER standard MT5 logic for each bar.
        """
        # 0. Detection: Check if bar i is an Outside Bar to start waiting
        if not self.ob_waiting and i > 0:
            if curr_h > prev_h and curr_l < prev_l:
                self.ob_waiting = True
                self.ob_high = curr_h
                self.ob_low = curr_l
                self.ob_index = i
                self.ob_count = 0
                self.last_piv_type = PivotState.LAST_PEAK if let == 1 else (PivotState.LAST_TROUGH if let == -1 else PivotState.UNKNOWN)
                self.current_ob_case = OBMatrixCase.NONE 
                
                # Priority Replacement (AC: 1)
                # If OB creates a new local extreme within ext_period, update it immediately
                if let == 1 and curr_h > self.normalize_double(last_up):
                     if (i - last_up_bar) <= self.ext_period:
                         if last_up_bar != -1: self.up[last_up_bar] = self.EMPTY_VALUE
                         self.up[i] = curr_h
                         self.last_up_idx = i
                         self.type_buffer[i] = int(ExtremumType.PEAK)
                elif let == -1 and curr_l < self.normalize_double(last_dn):
                     if (i - last_dn_bar) <= self.ext_period:
                         if last_dn_bar != -1: self.dn[last_dn_bar] = self.EMPTY_VALUE
                         self.dn[i] = curr_l
                         self.last_dn_idx = i
                         self.type_buffer[i] = int(ExtremumType.TROUGH)
                return False

        if not self.ob_waiting:
            self.current_ob_case = OBMatrixCase.NONE
            return False

        # 1. Handle Pending State (Inside Bar) - WIPE standard pivots
        is_ib = curr_h <= self.ob_high and curr_l >= self.ob_low
        if is_ib and i > self.ob_index:
            self.ob_count = i - self.ob_index
            self.current_ob_case = OBMatrixCase.PENDING
            
            # WIPE: Clear any pivot standard logic might have drawn inside the OB range
            self.up[i] = self.EMPTY_VALUE
            self.dn[i] = self.EMPTY_VALUE
            self.type_buffer[i] = int(ExtremumType.NONE)
            
            # Default Exit Rule (AC: 4) after 5 candles
            if self.ob_count >= 5:
                lookback_start = max(0, i - 4)
                ib_range_h = df.iloc[lookback_start:i+1]['h'].max()
                ib_range_l = df.iloc[lookback_start:i+1]['l'].min()
                ob_range = self.ob_high - self.ob_low
                
                if (ib_range_h - ib_range_l) < (0.5 * ob_range):
                    self.current_ob_case = OBMatrixCase.DEFAULT_EXIT
                    # Trigger Double Pivot (Sóng kép)
                    if self.last_piv_type == PivotState.LAST_TROUGH:
                         # Trough -> OB High (Peak) -> current Low (Trough)
                        self.up[self.ob_index] = self.ob_high
                        self.last_up_idx = self.ob_index
                        self.dn[i] = curr_l
                        self.last_dn_idx = i
                        self.type_buffer[i] = int(ExtremumType.TROUGH)
                    else:
                        # Peak -> OB Low (Trough) -> current High (Peak)
                        self.dn[self.ob_index] = self.ob_low
                        self.last_dn_idx = self.ob_index
                        self.up[i] = curr_h
                        self.last_up_idx = i
                        self.type_buffer[i] = int(ExtremumType.PEAK)
                    
                    self.ob_waiting = False
                    return True
            return False

        # 2. Handle Breakout (AC: 3) - OVERRIDE standard pivots if needed
        broke_h = curr_h > self.ob_high
        broke_l = curr_l < self.ob_low
        
        if broke_h or broke_l:
            self.current_ob_case = OBMatrixCase.BREAKOUT_UP if broke_h else OBMatrixCase.BREAKOUT_DOWN
            
            if self.last_piv_type == PivotState.LAST_TROUGH:
                if broke_l:
                    self.up[self.ob_index] = self.ob_high
                    self.last_up_idx = self.ob_index
                    self.dn[i] = curr_l
                    self.last_dn_idx = i
                    self.type_buffer[i] = int(ExtremumType.TROUGH)
                elif broke_h:
                    self.dn[self.ob_index] = self.ob_low
                    self.last_dn_idx = self.ob_index
                    self.up[i] = curr_h
                    self.last_up_idx = i
                    self.type_buffer[i] = int(ExtremumType.PEAK)
            elif self.last_piv_type == PivotState.LAST_PEAK:
                if broke_h:
                    self.dn[self.ob_index] = self.ob_low
                    self.last_dn_idx = self.ob_index
                    self.up[i] = curr_h
                    self.last_up_idx = i
                    self.type_buffer[i] = int(ExtremumType.PEAK)
                elif broke_l:
                    self.up[self.ob_index] = self.ob_high
                    self.last_up_idx = self.ob_index
                    self.dn[i] = curr_l
                    self.last_dn_idx = i
                    self.type_buffer[i] = int(ExtremumType.TROUGH)
            elif self.last_piv_type == PivotState.UNKNOWN:
                if broke_h:
                    self.dn[self.ob_index] = self.ob_low
                    self.up[i] = curr_h
                    self.last_up_idx = i
                else:
                    self.up[self.ob_index] = self.ob_high
                    self.dn[i] = curr_l
                    self.last_dn_idx = i
            
            self.ob_waiting = False
            return True

        return False

    def _comb(
        self,
        df: pd.DataFrame,
        i: int,
        h: float, l: float,
        fup: float, fdn: float,
        high_idx: int, low_idx: int,
        timeframe: str,
        sub_candles_by_tf: Optional[Dict[str, pd.DataFrame]]
    ) -> int:
        """
        Port of Comb() — Lines 461-493.
        Analyzes current bar situation to determine extremum type.

        Args:
            df: Full DataFrame (needed for candle data on Outside Bar).
            i: Current bar index (ascending).
            h, l: Highest high / lowest low in the window.
            fup, fdn: Current bar's high / low.
            high_idx, low_idx: Index of highest/lowest bar in window.
            timeframe: Parent timeframe string.
            sub_candles_by_tf: Sub-candle DataFrames for multi-TF analysis.
        """
        # Line 465: Peak
        if i == high_idx and i != low_idx:
            return ExtremumType.PEAK

        # Line 468: Trough
        if i != high_idx and i == low_idx:
            return ExtremumType.TROUGH

        # Line 471: Outside Bar (both peak and trough)
        if i == high_idx and i == low_idx:
            order_hl = OrderFormation.OFBError
            rates_total = len(df)
            
            # Optimization: Check OB[] cache ONLY for closed bars
            # For the last bar (live tick), we MUST re-evaluate every time
            is_last_bar = (i >= rates_total - 1)
            
            if is_last_bar or self.ob[i] == self.EMPTY_VALUE:
                # Line 476: GetOrderFormationBarHighLow(Symbol(), Period(), i, iUseSmallerTFforEB)
                order_hl = self.ob_analyzer.get_order_formation(
                    candle=df.iloc[i],
                    timeframe=timeframe,
                    sub_candles_by_tf=sub_candles_by_tf
                )
                
                # Only cache if NOT the last bar
                if not is_last_bar and order_hl != OrderFormation.OFBError:
                    self.ob[i] = float(order_hl.value)
            else:
                # Use cached value for closed bars
                order_hl = OrderFormation(int(self.ob[i]))

            # Lines 483-489
            if order_hl == OrderFormation.OFBLowHigh:
                return ExtremumType.OUTSIDE_BULLISH
            if order_hl == OrderFormation.OFBHighLow:
                return ExtremumType.OUTSIDE_BEARISH

        # Line 492
        return ExtremumType.NONE

    def update(
        self,
        df: pd.DataFrame,
        timeframe: str = "M1",
        sub_candles_by_tf: Optional[Dict[str, pd.DataFrame]] = None,
        incremental: bool = False
    ) -> Dict[str, list]:
        """
        Port of OnCalculate() — Lines 118-457.
        Main calculation loop.

        Args:
            df: DataFrame with columns 'h', 'l', 'o', 'c', 't' (ascending order).
            timeframe: Timeframe of the data.
            sub_candles_by_tf: Optional sub-candle DataFrames for Outside Bar.
            incremental: If True, use MQL5-style incremental recalculation (requires
                        stable indices — do NOT use with sliding windows).
                        If False (default), always do full recalculation.

        Returns:
            Dict with 'up', 'dn', 'type' buffer lists.
        """
        rates_total = len(df)
        last_t = df.iloc[-1]['t'] if rates_total > 0 else '0'
        logger.debug(f"[t={last_t}] [{timeframe}] [update] 1... Processing ZZ update rates_total={rates_total} incremental={incremental} last_t={last_t}")
        if rates_total == 0:
            return {"up": [], "dn": [], "type": []}

        if incremental:
            # Detect sliding window drift BEFORE resizing or processing
            self._handle_window_drift(df)

        # --- Resize buffers to match data ---
        if len(self.up) < rates_total:
            diff = rates_total - len(self.up)
            self.up.extend([self.EMPTY_VALUE] * diff)
            self.dn.extend([self.EMPTY_VALUE] * diff)
            self.ob.extend([self.EMPTY_VALUE] * diff)
            self.times.extend([0] * diff)
            self.type_buffer.extend([int(ExtremumType.NONE)] * diff)
        elif len(self.up) > rates_total:
            self.up = self.up[:rates_total]
            self.dn = self.dn[:rates_total]
            self.ob = self.ob[:rates_total]
            self.times = self.times[:rates_total]
            self.type_buffer = self.type_buffer[:rates_total]

        if not incremental:
            # ===== FULL RECALCULATION MODE (default) =====
            # Clear all buffers and recalculate from scratch.
            for idx in range(rates_total):
                self.up[idx] = self.EMPTY_VALUE
                self.dn[idx] = self.EMPTY_VALUE
                self.ob[idx] = self.EMPTY_VALUE
                self.times[idx] = int(df.iloc[idx]['t'])
                self.type_buffer[idx] = int(ExtremumType.NONE)
            self.time_first_ext_bar = 0
            self.last_up_idx = -1
            self.last_dn_idx = -1
            self.last_mother_idx = -1
            self.valid_indices = []
            recalc_start = self.ext_period - 1
        else:
            # ===== INCREMENTAL MODE (MQL5-style, for streaming with stable indices) =====
            # Lines 134-141: Clear only new bars
            prev_calc = self.prev_calculated
            clear_start = prev_calc if prev_calc > 0 else 0
            for idx in range(clear_start, rates_total):
                self.up[idx] = self.EMPTY_VALUE
                self.dn[idx] = self.EMPTY_VALUE
                self.ob[idx] = self.EMPTY_VALUE
                self.times[idx] = int(df.iloc[idx]['t'])
                self.type_buffer[idx] = int(ExtremumType.NONE)

            # Lines 143-159: Full reset on history download
            counted_bars = prev_calc
            if counted_bars == 0:
                self.download_history = True

            if self.download_history:
                for idx in range(rates_total):
                    self.up[idx] = self.EMPTY_VALUE
                    self.dn[idx] = self.EMPTY_VALUE
                    self.ob[idx] = self.EMPTY_VALUE
                    self.type_buffer[idx] = int(ExtremumType.NONE)
                self.time_first_ext_bar = 0
                self.last_up_idx = -1
                self.last_dn_idx = -1
                self.last_mother_idx = -1
                self.valid_indices = []
                self.times = [0] * rates_total
                for idx in range(rates_total):
                    self.times[idx] = int(df.iloc[idx]['t'])
                counted_bars = 0
                self.last_bar_time = 0
                self.download_history = False

            # Lines 162-169: New bar detection
            current_time = int(df.iloc[-1]['t'])
            new_bar = (self.last_bar_time != current_time)

            if new_bar:
                self.last_bar_time = current_time
                self.last_bar_last_high = float(df.iloc[-1]['h'])
                self.last_bar_last_low = float(df.iloc[-1]['l'])

            # Lines 172-194: BarsForRecalculation & MinMotion optimization
            if counted_bars > 0:
                # To fix "Stuck Pivot", always recalculate at least the last candle
                recalc_start = max(self.ext_period - 1, counted_bars - 1)

                # MinMotion optimization (skip if price didn't move enough).
                # IMPORTANT: this must happen BEFORE buffer/pointer reset;
                # otherwise an early-return can erase the latest pivot.
                if not new_bar:
                    current_high = float(df.iloc[-1]['h'])
                    current_low = float(df.iloc[-1]['l'])
                    diff_h = normalize_double(
                        current_high - self.last_bar_last_high, self.digits
                    )
                    diff_l = normalize_double(
                        self.last_bar_last_low - current_low, self.digits
                    )

                    if diff_h < self.mm and diff_l < self.mm:
                        self.prev_calculated = rates_total
                        return {
                            "up": self.up[:rates_total],
                            "dn": self.dn[:rates_total],
                            "type": self.type_buffer[:rates_total]
                        }

                    self.last_bar_last_high = current_high
                    self.last_bar_last_low = current_low

                # Reset buffers for ONLY the bars we are about to recalculate.
                # If we were previously holding a peak/trough at these indices,
                # we must also reset the O(1) pointers to avoid stale comparisons.
                for idx in range(recalc_start, rates_total):
                    if self.last_up_idx == idx:
                        self.last_up_idx = -1
                    if self.last_dn_idx == idx:
                        self.last_dn_idx = -1

                    self.up[idx] = self.EMPTY_VALUE
                    self.dn[idx] = self.EMPTY_VALUE
                    self.ob[idx] = self.EMPTY_VALUE
                    self.type_buffer[idx] = int(ExtremumType.NONE)

                # Story 5.1: Reset valid indices and mother for the recalc range
                self.valid_indices = [idx for idx in self.valid_indices if idx < recalc_start]
                self.last_mother_idx = self.valid_indices[-1] if self.valid_indices else -1

                # Find the actual last valid Up/Dn index PRIOR to recalc_start
                if self.last_up_idx >= recalc_start or self.last_up_idx == -1:
                    m = recalc_start - 1
                    while m >= 0 and self.up[m] == self.EMPTY_VALUE:
                        m -= 1
                    self.last_up_idx = m

                if self.last_dn_idx >= recalc_start or self.last_dn_idx == -1:
                    n = recalc_start - 1
                    while n >= 0 and self.dn[n] == self.EMPTY_VALUE:
                        n -= 1
                    self.last_dn_idx = n
            else:
                recalc_start = self.ext_period - 1

        # ============================================================
        # Lines 196-454: MAIN LOOP
        # MQL5 (series): for(i=BarsForRecalculation; i>=0; i--)
        # Python (ascending): for i in range(recalc_start, rates_total)
        # Both process oldest → newest in time.
        # ============================================================
        # Story 5.1: Ensure valid_indices is populated correctly.
        # If we are reprocessing index 0, loop_start is 0.
        # If we are continuing from recalc_start, ensure we don't duplicate items already in valid_indices.
        loop_start = 0 if not self.valid_indices and rates_total > 0 else recalc_start

        for i in range(loop_start, rates_total):
            # O(1) Optimization: Use cached indices instead of while loops
            last_up_bar = self.last_up_idx
            last_dn_bar = self.last_dn_idx
            
            last_up = self.up[last_up_bar] if last_up_bar != -1 else 0.0
            last_dn = self.dn[last_dn_bar] if last_dn_bar != -1 else 0.0

            # If both are -1, let remains 0.
            
            # Line 277: Determine current 'let' (last extremum type)
            # 1 = Peak, -1 = Trough, 0 = None
            let = 0
            if last_up_bar != -1 and last_dn_bar != -1:
                let = 1 if last_up_bar > last_dn_bar else -1
            elif last_up_bar != -1:
                let = 1
            elif last_dn_bar != -1:
                let = -1

            curr_h = float(df.iloc[i]['h'])
            curr_l = float(df.iloc[i]['l'])
            prev_h = float(df.iloc[i-1]['h']) if i > 0 else curr_h
            prev_l = float(df.iloc[i-1]['l']) if i > 0 else curr_l

            # --- AC: 5 OB Matrix WIPE & Resolution (Top of Loop) ---
            if self.ob_waiting and i >= recalc_start:
                resolved = self._process_ob_matrix(df, i, curr_h, curr_l, prev_h, prev_l, let, last_up, last_dn, last_up_bar, last_dn_bar, recalc_start)
                if resolved:
                    self.last_mother_idx = i
                    if not self.valid_indices or self.valid_indices[-1] != i:
                        self.valid_indices.append(i)
                    continue
                else:
                    # PENDING (IB): WIPE and continue to skip rest of loop
                    self.last_mother_idx = i
                    if not self.valid_indices or self.valid_indices[-1] != i:
                        self.valid_indices.append(i)
                    continue

            # Lines 236-261: Same bar (outside bar) — resolve by looking further back
            if last_up_bar == last_dn_bar and last_up_bar >= 0:
                m = last_up_bar
                n = m
                while m == n:
                    m -= 1
                    n -= 1
                    while m >= 0 and self.up[m] == self.EMPTY_VALUE:
                        m -= 1
                    while n >= 0 and self.dn[n] == self.EMPTY_VALUE:
                        n -= 1
                    if m < 0 or n < 0:
                        break
                if m > n:
                    let = 1
                elif m < n:
                    let = -1

            curr_h = float(df.iloc[i]['h'])
            curr_l = float(df.iloc[i]['l'])
            prev_h = float(df.iloc[i-1]['h']) if i > 0 else 0.0
            prev_l = float(df.iloc[i-1]['l']) if i > 0 else 0.0

            # --- Story 5.1/5.2: Inside Bar Detection & Bypass ---
            is_inside = False
            if self.last_mother_idx != -1:
                mother_h = float(df.iloc[self.last_mother_idx]['h'])
                mother_l = float(df.iloc[self.last_mother_idx]['l'])
                if curr_h < mother_h and curr_l > mother_l:
                    is_inside = True
            
            if is_inside:
                # Story 5.2: Stale-mate Bypass
                # If movement inside mother bar > min_amplitude from last pivot, bypass filter
                bypass = False
                last_pivot_val = 0.0
                if let == 1:
                    last_pivot_val = last_up
                elif let == -1:
                    last_pivot_val = last_dn

                if last_pivot_val != 0.0:
                    delta_h = abs(curr_h - last_pivot_val)
                    delta_l = abs(curr_l - last_pivot_val)
                    if delta_h > self.mp or delta_l > self.mp:
                        # Bypass: treat as valid candle despite being inside mother bar
                        bypass = True

                if not bypass:
                    self.type_buffer[i] = int(ExtremumType.NONE)
                    # If OB Matrix is waiting, we MUST process it to WIPE standard pivots
                    if self.ob_waiting:
                        self._process_ob_matrix(df, i, curr_h, curr_l, prev_h, prev_l, let, last_up, last_dn, last_up_bar, last_dn_bar, recalc_start)
                    continue

            is_breakout = False
            if self.last_mother_idx != -1 and i >= recalc_start:
                mother_h = self.normalize_double(float(df.iloc[self.last_mother_idx]['h']))
                mother_l = self.normalize_double(float(df.iloc[self.last_mother_idx]['l']))
                c_h = self.normalize_double(curr_h)
                c_l = self.normalize_double(curr_l)
                
                broke_h = c_h > mother_h
                broke_l = c_l < mother_l
                
                # Story 2.1: If BOTH High and Low are broken (Outside Bar), we skip simple breakout 
                # and let the standard _comb/OB Matrix logic handle it below.
                if (broke_h or broke_l) and not (broke_h and broke_l):
                    # Breakout detected. Determine action based on current wave (let).
                    if let == 1: # Last was Peak
                        # Case: Break High (Priority Replace - even if broke_l)
                        if broke_h and c_h > self.normalize_double(last_up):
                            if last_up_bar != -1:
                                self.up[last_up_bar] = self.EMPTY_VALUE
                            self.up[i] = curr_h
                            self.last_up_idx = i
                            self.type_buffer[i] = int(ExtremumType.PEAK)
                            is_breakout = True
                        
                        # Case: Break Low ONLY (Transition)
                        elif broke_l:
                            self.dn[i] = curr_l
                            self.last_dn_idx = i
                            self.type_buffer[i] = int(ExtremumType.TROUGH)
                            is_breakout = True
                                
                    elif let == -1: # Last was Trough
                        # Case: Break Low (Priority Replace - even if broke_h)
                        if broke_l and c_l < self.normalize_double(last_dn):
                            if last_dn_bar != -1:
                                self.dn[last_dn_bar] = self.EMPTY_VALUE
                            self.dn[i] = curr_l
                            self.last_dn_idx = i
                            self.type_buffer[i] = int(ExtremumType.TROUGH)
                            is_breakout = True
 
                        # Case: Break High ONLY (Transition)
                        elif broke_h:
                            self.up[i] = curr_h
                            self.last_up_idx = i
                            self.type_buffer[i] = int(ExtremumType.PEAK)
                            is_breakout = True
                    
                    elif let == 0:
                        # Starting state: let normal logic handle it
                        pass
 
            # If breakout occurred, we skip standard extremum search for this bar
            if is_breakout:
                self.last_mother_idx = i
                if not self.valid_indices or self.valid_indices[-1] != i:
                    self.valid_indices.append(i)
                # If OB Matrix is waiting, handle breakout override
                if self.ob_waiting:
                    self._process_ob_matrix(df, i, curr_h, curr_l, prev_h, prev_l, let, last_up, last_dn, last_up_bar, last_dn_bar, recalc_start)
                continue
 
            # Standard update of mother and valid indices
            self.last_mother_idx = i
            if not self.valid_indices or self.valid_indices[-1] != i:
                self.valid_indices.append(i)
 
            if i < recalc_start:
                continue

            # Lines 268-274: ArrayMaximum / ArrayMinimum (Modified for Story 5.1)
            # Use valid_indices to find the search window
            win_indices = self.valid_indices[-self.ext_period:]
            sub_df = df.iloc[win_indices]
            
            max_val = sub_df['h'].max()
            # Prefer latest index in case of tie (consistent with MQL5 breakout logic)
            high_idx = sub_df.index[sub_df['h'] == max_val][-1]
            
            min_val = sub_df['l'].min()
            low_idx = sub_df.index[sub_df['l'] == min_val][-1]

            fup = float(df.iloc[i]['h'])  # Line 273
            fdn = float(df.iloc[i]['l'])  # Line 274

            # --- Line 277: Comb() call ---
            comb_res = self._comb(
                df, i, max_val, min_val, fup, fdn, high_idx, low_idx,
                timeframe, sub_candles_by_tf
            )
            self.type_buffer[i] = int(comb_res)

            # --- Lines 278-453: Main State Machine ---

            if comb_res == ExtremumType.PEAK:
                # Lines 281-298
                if let == 1:
                    # Line 284: Previous was also peak → keep higher
                    if last_up < fup:
                        self.up[last_up_bar] = self.EMPTY_VALUE
                        self.up[i] = fup
                        self.last_up_idx = i # Update O(1) pointer
                elif let == -1:
                    # Line 291: Previous was trough → check amplitude
                    if (fup - last_dn) > self.mp:
                        self.up[i] = fup
                        self.last_up_idx = i # Update O(1) pointer
                else:
                    # Line 294-296: No previous extremum → starting point
                    self.up[i] = fup
                    self.last_up_idx = i # Update O(1) pointer
                    self.time_first_ext_bar = int(df.iloc[i]['t'])

            elif comb_res == ExtremumType.TROUGH:
                # Lines 302-320
                if let == 1:
                    # Line 306: Previous was peak → check amplitude
                    if (last_up - fdn) > self.mp:
                        self.dn[i] = fdn
                        self.last_dn_idx = i # Update O(1) pointer
                elif let == -1:
                    # Line 310: Previous was also trough → keep lower
                    if last_dn > fdn:
                        self.dn[last_dn_bar] = self.EMPTY_VALUE
                        self.dn[i] = fdn
                        self.last_dn_idx = i # Update O(1) pointer
                else:
                    # Line 316-318: No previous extremum → starting point
                    self.dn[i] = fdn
                    self.last_dn_idx = i # Update O(1) pointer
                    self.time_first_ext_bar = int(df.iloc[i]['t'])

            elif comb_res == ExtremumType.OUTSIDE_BULLISH:
                # Lines 324-384: Low formed first, then High
                if let == 1:
                    # Lines 328-356: Previous was peak
                    if (fup - fdn) > self.mp:
                        if (last_up - fdn) > self.mp:
                            # Line 332-333
                            self.up[i] = fup
                            self.dn[i] = fdn
                            self.last_up_idx = i
                            self.last_dn_idx = i
                        else:
                            # Lines 337-341
                            if last_up < fup:
                                self.up[last_up_bar] = self.EMPTY_VALUE
                                self.up[i] = fup
                                self.last_up_idx = i
                    else:
                        if (last_up - fdn) > self.mp:
                            # Line 347
                            self.dn[i] = fdn
                            self.last_dn_idx = i
                        else:
                            # Lines 350-354
                            if last_up < fup:
                                self.up[last_up_bar] = self.EMPTY_VALUE
                                self.up[i] = fup
                                self.last_up_idx = i

                elif let == -1:
                    # Lines 358-380: Previous was trough
                    if (fup - fdn) > self.mp:
                        self.up[i] = fup
                        self.last_up_idx = i
                        # Line 362: Check if can replace previous trough
                        if (fdn < last_dn) and (int(df.iloc[last_dn_bar]['t']) > self.time_first_ext_bar):
                            self.dn[last_dn_bar] = self.EMPTY_VALUE
                            self.dn[i] = fdn
                            self.last_dn_idx = i
                    else:
                        if (fup - last_dn) > self.mp:
                            # Line 370-371
                            self.up[i] = fup
                            self.last_up_idx = i
                        else:
                            # Lines 374-378
                            if last_dn > fdn:
                                self.dn[last_dn_bar] = self.EMPTY_VALUE
                                self.dn[i] = fdn
                                self.last_dn_idx = i
                # default (let==0): break — do nothing (Line 382-383)
                
                # @user: distance <= ext_period check before call
                # Use last_up_bar/last_dn_bar (state at the start of current bar i)
                last_conf_piv = max(last_up_bar, last_dn_bar)
                if last_conf_piv == -1 or (i - last_conf_piv) <= self.ext_period:
                    # --- Story 2.1: OB Matrix Integration (START/OVERRIDE) ---
                    self._process_ob_matrix(df, i, curr_h, curr_l, prev_h, prev_l, let, last_up, last_dn, last_up_bar, last_dn_bar, recalc_start)

            elif comb_res == ExtremumType.OUTSIDE_BEARISH:
                # Lines 388-448: High formed first, then Low
                if let == 1:
                    # Lines 391-413: Previous was peak
                    if (fup - fdn) > self.mp:
                        self.dn[i] = fdn
                        self.last_dn_idx = i
                        # Line 395: Check if can replace previous peak
                        if (last_up < fup) and (int(df.iloc[last_up_bar]['t']) > self.time_first_ext_bar):
                            self.up[last_up_bar] = self.EMPTY_VALUE
                            self.up[i] = fup
                            self.last_up_idx = i
                    else:
                        if (last_up - fdn) > self.mp:
                            # Line 403-404
                            self.dn[i] = fdn
                            self.last_dn_idx = i
                        else:
                            # Lines 407-411
                            if last_up < fup:
                                self.up[last_up_bar] = self.EMPTY_VALUE
                                self.up[i] = fup
                                self.last_up_idx = i

                elif let == -1:
                    # Lines 415-444: Previous was trough
                    if (fup - fdn) > self.mp:
                        if (fup - last_dn) > self.mp:
                            # Lines 420-421
                            self.up[i] = fup
                            self.dn[i] = fdn
                            self.last_up_idx = i
                            self.last_dn_idx = i
                        else:
                            # Lines 425-429
                            if last_dn > fdn:
                                self.dn[last_dn_bar] = self.EMPTY_VALUE
                                self.dn[i] = fdn
                                self.last_dn_idx = i
                    else:
                        if (fup - last_dn) > self.mp:
                            # Line 434-435
                            self.up[i] = fup
                            self.last_up_idx = i
                        else:
                            # Lines 438-442
                            if last_dn > fdn:
                                self.dn[last_dn_bar] = self.EMPTY_VALUE
                                self.dn[i] = fdn
                                self.last_dn_idx = i
                # default (let==0): break — do nothing (Line 446-447)
                
                # @user: distance <= ext_period check before call
                # Use last_up_bar/last_dn_bar (state at the start of current bar i)
                last_conf_piv = max(last_up_bar, last_dn_bar)
                if last_conf_piv == -1 or (i - last_conf_piv) <= self.ext_period:
                    # --- Story 2.1: OB Matrix Integration (START/OVERRIDE) ---
                    self._process_ob_matrix(df, i, curr_h, curr_l, prev_h, prev_l, let, last_up, last_dn, last_up_bar, last_dn_bar, recalc_start)

        # --- Line 456: Return prev_calculated for next call ---
        self.prev_calculated = rates_total

        # Tracing raw buffers for debugging (Phase 2/Step 3)
        try:
            # Only slice if necessary, and use a simpler filter
            valid_up = [v for v in self.up[:rates_total] if v != 0.0]
            valid_dn = [v for v in self.dn[:rates_total] if v != 0.0]
            last_t = df.iloc[-1]['t'] if len(df) > 0 else '0'
            logger.info(f"[t={last_t}] [{timeframe}] [update] 2... ZZ finished: valid_up_count={len(valid_up)} valid_dn_count={len(valid_dn)}")
        except Exception as e:
            last_t = df.iloc[-1]['t'] if len(df) > 0 else '0'
            logger.error(f"[t={last_t}] [{timeframe}] [update] Error: Error logging ZigZagPro results: {e}")

        return {
            "up": self.up[:rates_total],
            "dn": self.dn[:rates_total],
            "type": self.type_buffer[:rates_total]
        }


# ============================================================================
# Helper functions (Python additions for downstream consumers)
# ============================================================================

def get_confirmed_pivots(
    up: List[float], dn: List[float], types: List[int], times: List[int]
) -> List[Dict[str, Any]]:
    """
    Converts ZigZag buffers to a list of pivot objects for labeling.
    Handles Outside Bar ordering based on ExtremumType.
    """
    pivots = []
    empty = ZigZagPro.EMPTY_VALUE

    for i in range(len(up)):
        has_up = up[i] != empty
        has_dn = dn[i] != empty

        if has_up and has_dn:
            bar_type = types[i]
            if bar_type == int(ExtremumType.OUTSIDE_BULLISH):
                # Low formed first, then High. Keep only the High (final extremum).
                pivots.append({"index": i, "t": times[i], "price": up[i], "is_high": True})
            else:
                # High first, then Low (Bearish or default). Keep only the Low (final extremum).
                pivots.append({"index": i, "t": times[i], "price": dn[i], "is_high": False})
        elif has_up:
            pivots.append({"index": i, "t": times[i], "price": up[i], "is_high": True})
        elif has_dn:
            pivots.append({"index": i, "t": times[i], "price": dn[i], "is_high": False})

    # Stable sort preserves OB sub-ordering
    pivots.sort(key=lambda x: x['index'])
    return pivots


def label_pivots_pro(pivots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Labels HH/LL/LH/HL appropriately for an array sorted [Oldest ... Newest].
    Compares the current extremum with the previously recorded extremum of the same type.
    """
    if not pivots:
        return []

    labeled = []
    last_h = None
    last_l = None

    for p in pivots:
        p_copy = p.copy()
        if p_copy['is_high']:
            if last_h is not None:
                p_copy['type'] = "HH" if p_copy['price'] > last_h else "LH"
            else:
                p_copy['type'] = "HH"
            last_h = p_copy['price']
        else:
            if last_l is not None:
                p_copy['type'] = "LL" if p_copy['price'] < last_l else "HL"
            else:
                p_copy['type'] = "LL"
            last_l = p_copy['price']
                
        labeled.append(p_copy)

    return labeled
