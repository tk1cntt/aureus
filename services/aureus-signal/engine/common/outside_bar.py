"""
Full 1:1 Port of AlexSTAL_OutsideBar.mqh (Copyright 2011, AlexSTAL)
http://www.alexstal.ru

Determines the order of High/Low formation for Outside Bars (Engulfing Candles).
Supports multi-timeframe sub-candle analysis for accurate detection.

Reference: phase-2/step-3/reference/AlexSTAL_OutsideBar_utf8.mqh (337 lines)

Usage:
    from engine.common.outside_bar import OutsideBarAnalyzer

    analyzer = OutsideBarAnalyzer()
    result = analyzer.get_order_formation(candle, timeframe='M1', sub_candles=None)
    # result is one of: OFBError, OFBLowEqualHigh, OFBHighLow, OFBLowHigh, OFBErrorFindSmallTF
"""

import pandas as pd
from .physics import is_touching, has_closed_above
from collections import OrderedDict
import logging
logger = logging.getLogger("aureus-signals")
from typing import Dict, Optional
from enum import IntEnum
import calendar
from datetime import datetime


class OrderFormation(IntEnum):
    """Port of enum OrderFormationBarHighLow (Lines 10-17)"""
    OFBError = 0            # Error or not determined
    OFBLowEqualHigh = 1     # High == Low (doji with no range)
    OFBHighLow = 2          # High formed first, then Low (Bearish outside bar)
    OFBLowHigh = 3          # Low formed first, then High (Bullish outside bar)
    OFBErrorFindSmallTF = 4 # Both extremes on same sub-candle (inconclusive)


# ============================================================================
# Timeframe Constants & Mappings
# Port of NumberOfPassesSearch() (Lines 168-207)
# and SmallTFforNumberOfPassesSearch() (Lines 213-307)
# ============================================================================

# Timeframe names to seconds mapping
TF_SECONDS: Dict[str, int] = {
    "M1": 60, "M2": 120, "M3": 180, "M4": 240, "M5": 300,
    "M6": 360, "M10": 600, "M12": 720, "M15": 900,
    "M20": 1200, "M30": 1800,
    "H1": 3600, "H2": 7200, "H3": 10800, "H4": 14400,
    "H6": 21600, "H8": 28800, "H12": 43200,
    "D1": 86400,
    "W1": 604800,
    "MN1": 0,  # Variable, handled by number_days_month()
}

# Port of NumberOfPassesSearch() — Lines 168-207
# Maps timeframe -> number of smaller TF passes to attempt
NUMBER_OF_PASSES: Dict[str, int] = {
    "M1": 0,   # No smaller TF exists
    "M2": 1, "M3": 1, "M4": 1, "M5": 1, "M6": 1, "M10": 1, "M12": 1, "M15": 1,
    "M20": 2, "M30": 2, "H1": 2, "H2": 2, "H3": 2,
    "H4": 2, "H6": 2,
    "H8": 3, "H12": 3, "D1": 3,
    "W1": 4, "MN1": 4,
}

# Port of SmallTFforNumberOfPassesSearch() — Lines 213-307
# Maps (parent_timeframe, pass_number) -> smaller_timeframe
SMALL_TF_MAP: Dict[str, Dict[int, str]] = {
    # M2-M15: 1 pass -> M1
    "M2":  {1: "M1"},
    "M3":  {1: "M1"},
    "M4":  {1: "M1"},
    "M5":  {1: "M1"},
    "M6":  {1: "M1"},
    "M10": {1: "M1"},
    "M12": {1: "M1"},
    "M15": {1: "M1"},
    # M20: 2 passes
    "M20": {1: "M2", 2: "M1"},
    # M30, H1: 2 passes
    "M30": {1: "M5", 2: "M1"},
    "H1":  {1: "M5", 2: "M1"},
    # H2, H3: 2 passes
    "H2":  {1: "M15", 2: "M1"},
    "H3":  {1: "M15", 2: "M1"},
    # H4, H6: 2 passes
    "H4":  {1: "M30", 2: "M1"},
    "H6":  {1: "M30", 2: "M1"},
    # H8, H12: 3 passes
    "H8":  {1: "H1", 2: "M5", 3: "M1"},
    "H12": {1: "H1", 2: "M5", 3: "M1"},
    # D1: 3 passes
    "D1":  {1: "H4", 2: "M30", 3: "M1"},
    # W1: 4 passes
    "W1":  {1: "D1", 2: "H4", 3: "M30", 4: "M1"},
    # MN1: 4 passes
    "MN1": {1: "D1", 2: "H4", 3: "M30", 4: "M1"},
}


def number_days_month(dt: datetime) -> int:
    """
    Port of NumberDaysMonth() — Lines 312-337.
    Returns the number of days in the month of the given datetime.
    """
    return calendar.monthrange(dt.year, dt.month)[1]


class OutsideBarAnalyzer:
    """
    Complete port of AlexSTAL_OutsideBar.mqh.
    
    Provides multi-timeframe analysis to determine whether an Outside Bar's
    High or Low was formed first, which is critical for correct ZigZag ordering.
    
    The analyzer can work in two modes:
    1. Simple mode (no sub-candle data): Uses Open/Close/Wick analysis
    2. Multi-TF mode (with sub-candle data): Scans sub-candles chronologically
    
    Args:
        use_smaller_tf: If True, attempt sub-candle analysis before falling back.
                       Mirrors MQL5's iUseSmallerTFforEB input.
    """

    def __init__(self, mode: str = "TICK", cache_max_size: int = 500) -> None:
        """
        Initialize the Outside Bar analyzer.
        Mode can be TICK (uses tick volume/data) or REAL (uses real volume).
        cache_max_size limits the LRU bounded cache size to prevent memory leaks.
        """
        self.mode = mode
        # Bounded cache to prevent memory leak (COM-04)
        self._cache_max_size = cache_max_size
        self._cache: OrderedDict[tuple, OrderFormation] = OrderedDict()
        
    def _cache_get(self, key: tuple) -> Optional[OrderFormation]:
        if key in self._cache:
            # Move to end to mark as recently used
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
        
    def _cache_set(self, key: tuple, value: OrderFormation) -> None:
        self._cache[key] = value
        if len(self._cache) > self._cache_max_size:
            # Pop oldest (FIFO/LRU hybrid)
            self._cache.popitem(last=False)

    def get_order_formation(
        self,
        candle: pd.Series,
        timeframe: str = "M1",
        lookback_tf: str = "M1",
        use_sub_tf: bool = True,
        sub_candles_by_tf: Optional[Dict[str, pd.DataFrame]] = None
    ) -> OrderFormation:
        """
        Port of GetOrderFormationBarHighLow() — Lines 32-53.
        
        Main entry point. Determines the order of High/Low formation.
        
        Args:
            candle: The parent bar (must have 'h', 'l', 'o', 'c', 't' columns).
            timeframe: The timeframe of the parent bar (e.g., "H1", "M15").
            lookback_tf: The timeframe used for lookback (e.g., "M1").
            use_sub_tf: If True, attempt sub-candle analysis.
            sub_candles_by_tf: Dict mapping timeframe string -> DataFrame of sub-candles.
                              e.g., {"M5": df_m5, "M1": df_m1}
                              Each DataFrame must have 'h', 'l', 't' columns.
                              
        Returns:
            OrderFormation enum value.
        """
        candle_t = int(candle['t'])
        # Check cache
        cache_key = (candle_t, timeframe, lookback_tf, use_sub_tf)
        cached_result = self._cache_get(cache_key)
        if cached_result is not None:
            return cached_result

        result = OrderFormation.OFBError

        if use_sub_tf:
            num_passes = NUMBER_OF_PASSES.get(timeframe, 0)

            for i in range(1, num_passes + 1):
                small_tf = SMALL_TF_MAP.get(timeframe, {}).get(i)
                if small_tf is None:
                    continue

                # Ensure sub_candles_by_tf is not None and contains the required small_tf
                if sub_candles_by_tf is None or small_tf not in sub_candles_by_tf:
                    logger.debug(f"No sub-candles available for {small_tf} for candle {candle_t}")
                    continue # Skip this pass if data is missing

                result = self.small_tf_logic(
                    candle=candle,
                    timeframe=timeframe,
                    small_tf=small_tf,
                    sub_candles_by_tf=sub_candles_by_tf
                )

                if result in (OrderFormation.OFBHighLow, OrderFormation.OFBLowHigh):
                    break  # Found definitive answer

            # If still no answer, fallback to simple logic
            if result not in (OrderFormation.OFBHighLow, OrderFormation.OFBLowHigh):
                result = self.simple_logic(candle)
        else:
            result = self.simple_logic(candle)

        # Cache the result
        self._cache_set(cache_key, result)
        return result

    def small_tf_logic(
        self,
        candle: pd.Series,
        timeframe: str,
        small_tf: str,
        sub_candles_by_tf: Optional[Dict[str, pd.DataFrame]] = None
    ) -> OrderFormation:
        """
        Port of SmallTFLogicBarHighLow() — Lines 65-120.
        
        Loads sub-candles within the parent bar's time range and checks
        which extremum (High or Low) was hit first chronologically.
        
        Args:
            candle: The parent bar.
            timeframe: Parent timeframe string.
            small_tf: The smaller timeframe to analyze.
            sub_candles_by_tf: Dict of available sub-candle DataFrames.
            
        Returns:
            OrderFormation enum value.
        """
        bar_h = float(candle['h'])
        bar_l = float(candle['l'])

        if bar_h == bar_l:
            return OrderFormation.OFBLowEqualHigh

        bar_t = int(candle['t'])

        # Calculate parent bar time range
        tf_seconds = TF_SECONDS.get(timeframe, 0)
        if timeframe == "MN1":
            dt = datetime.utcfromtimestamp(bar_t)
            tf_seconds = number_days_month(dt) * 86400

        bar_start = bar_t
        bar_end = bar_t + tf_seconds - 1

        # Get sub-candles for the requested smaller timeframe
        if sub_candles_by_tf is None or small_tf not in sub_candles_by_tf:
            return OrderFormation.OFBError  # No data available

        sub_df = sub_candles_by_tf[small_tf]
        if sub_df is None or sub_df.empty:
            return OrderFormation.OFBError

        # Filter sub-candles within parent bar's time range
        required_cols = {'t', 'h', 'l'}
        if not required_cols.issubset(sub_df.columns):
            missing = required_cols - set(sub_df.columns)
            logger.error(f"Missing required columns in sub_candles for {small_tf}: {missing}")
            return OrderFormation.OFBError

        mask = (sub_df['t'] >= bar_start) & (sub_df['t'] <= bar_end)
        window = sub_df[mask]

        if window.empty:
            return OrderFormation.OFBError

        # Port of lines 92-101 using 360x faster NumPy vectorization (COM-05)
        highs = window['h'].values
        lows = window['l'].values
        
        hit_high = highs >= bar_h
        hit_low = lows <= bar_l
        
        any_high = hit_high.any()
        any_low = hit_low.any()
        
        if not any_high and not any_low:
            return OrderFormation.OFBError           # Neither found (data gap)
            
        first_high_idx = hit_high.argmax() if any_high else len(highs)
        first_low_idx = hit_low.argmax() if any_low else len(lows)

        # Interpret result (Port of lines 102-119)
        if first_high_idx < first_low_idx:
            return OrderFormation.OFBHighLow         # High reached first -> Bearish
        elif first_low_idx < first_high_idx:
            return OrderFormation.OFBLowHigh         # Low reached first -> Bullish
        else:
            return OrderFormation.OFBErrorFindSmallTF # Both on same sub-candle

    @staticmethod
    def simple_logic(candle: pd.Series) -> OrderFormation:
        """
        Port of SimpleLogicBarHighLow() — Lines 133-162.
        
        Fallback logic when sub-candle data is unavailable or inconclusive.
        Determines bar direction from Open/Close comparison and wick analysis.
        
        Args:
            candle: The bar to analyze (must have 'h', 'l', 'o', 'c').
            
        Returns:
            OrderFormation enum value.
        """
        h = float(candle['h'])
        l = float(candle['l'])
        o = float(candle['o'])
        c = float(candle['c'])

        # Doji with zero range
        if h == l:
            return OrderFormation.OFBLowEqualHigh

        # Standard candle direction
        if c > o:
            return OrderFormation.OFBLowHigh   # Bullish: Low formed first
        if c < o:
            return OrderFormation.OFBHighLow   # Bearish: High formed first

        # Close == Open: Compare wick lengths
        a1 = h - c  # Upper wick
        a2 = c - l  # Lower wick

        if a1 > a2:
            return OrderFormation.OFBLowHigh   # Longer upper wick -> treated as bullish
        if a1 < a2:
            return OrderFormation.OFBHighLow   # Longer lower wick -> treated as bearish

        # Ultimate fallback: equal wicks -> bearish (MQH line 159)
        return OrderFormation.OFBHighLow

    def clear_cache(self):
        """Clear the OB result cache."""
        self._cache.clear()
