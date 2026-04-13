"""
CISD Multi-Timeframe Signal — reports CISD status on M5, M15, M30, H1.

On every M1 tick, resamples the M1 window to each configured higher timeframe,
scans completed HTF candles for CISD patterns matching MQL4 logic,
and emits the current CISD status.

MQL4 logic (FindGenericMTFCISD) — exact port:

  for i = 1..min(bars-1, 24):        // scan newest completed → oldest
      if (c[i] < o[i] && c[i+1] > o[i+1]):   // bear flip
          level = o[i]
          for k = i-1..1:                    // check candles newer than flip
              if close[k] > level → return 1  (Bullish CISD)

      if (c[i] > o[i] && c[i+1] < o[i+1]):   // bull flip
          level = o[i]
          for k = i-1..1:
              if close[k] < level → return -1 (Bearish CISD)

  return 0
"""
from .base import BaseSignal, SignalType
from .resampler import resample_to_tf
import pandas as pd
from engine.logging_common import get_logger
from typing import Dict, Any, Optional, List

logger = get_logger(__name__)

DEFAULT_TFS = ["M5", "M15", "M30", "H1"]
TF_LOWER = {"M5": "m5", "M15": "m15", "M30": "m30", "H1": "h1", "H4": "h4"}


class CISDMultiTFSignal(BaseSignal):
    """Multi-timeframe CISD scanner.

    Exact MQL4 port: scan newest→oldest for flip with break.
    Returns immediately on first match (most recent flip that got broken).
    """
    signal_type = SignalType.INDICATOR

    def __init__(self, tf_configs: Optional[list] = None):
        super().__init__("CISD Multi-TF")

        if tf_configs is None:
            tf_configs = [{"tf": tf, "max_bars": 24} for tf in DEFAULT_TFS]

        self.tf_configs = []
        for cfg in tf_configs:
            tf = str(cfg.get("tf", "")).upper()
            if tf in TF_LOWER:
                self.tf_configs.append({
                    "tf": tf,
                    "max_bars": int(cfg.get("max_bars", 24)),
                })

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df is None or len(df) < 2:
            return None

        for cfg in self.tf_configs:
            tf = cfg["tf"]
            self._process_tf(df, state_obj, tf, cfg)

        return None

    def _process_tf(self, df, state_obj, tf, cfg):
        """Process a single timeframe — scan and emit status."""
        tf_lower = TF_LOWER.get(tf, tf.lower())
        ht_df = resample_to_tf(df, tf)

        if ht_df is None or len(ht_df) < 3:
            return

        # Exclude forming candle (last row)
        completed = ht_df.iloc[:-1]
        max_bars = min(cfg.get("max_bars", 24), len(completed))

        signal = self._scan_cisd(completed, max_bars)

        if signal != 0:
            direction = "bullish" if signal > 0 else "bearish"
            self._emit_status(state_obj, tf, tf_lower, direction)

    @staticmethod
    def _scan_cisd(completed: pd.DataFrame, max_bars: int = 24) -> int:
        """Exact MQL4 FindGenericMTFCISD port.

        MQL4 index: 0=forming, 1=newest completed, 2=older, ...
        Our DataFrame: row 0=oldest, row n-1=newest completed

        Mapping: MQL4 index j → array index (n - j)
        where n = len(completed)

        Algorithm:
          For each completed candle i=1,2,...,max_bars (newest→oldest):
            Detect flip: candle[i] direction != candle[i+1] direction
            If flip found, check candles k=i-1..1 (newer than flip):
              Bear flip (bull→bear): any close[k] > open[i] → return 1
              Bull flip (bear→bull): any close[k] < open[i] → return -1
          Return 0 if no flip-with-break found
        """
        n = len(completed)
        if n < 3:
            return 0

        closes = completed["c"].values
        opens = completed["o"].values

        # match: for(i = 1; i < MathMin(bars - 1, 24); i++)
        upper_exclusive = min(n - 1, max_bars)
        for i_mql in range(1, upper_exclusive):
        # limit = min(max_bars, n - 1)
        # for i_mql in range(1, limit + 1):
            arr_i = n - i_mql          # flip candidate candle
            arr_prev = n - i_mql - 1   # older candle (i+1 in MQL4)

            if arr_prev < 0:
                break

            o = float(opens[arr_i])
            c = float(closes[arr_i])
            op1 = float(opens[arr_prev])
            cp1 = float(closes[arr_prev])

            # Bear flip: current bear, older candle was bull
            if c < o and cp1 > op1:
                level = o
                for k_mql in range(i_mql - 1, 0, -1):
                    arr_k = n - k_mql
                    if float(closes[arr_k]) > level:
                        return 1  # Bullish CISD

            # Bull flip: current bull, older candle was bear
            elif c > o and cp1 < op1:
                level = o
                for k_mql in range(i_mql - 1, 0, -1):
                    arr_k = n - k_mql
                    if float(closes[arr_k]) < level:
                        return -1  # Bearish CISD

        return 0

    def _emit_status(self, state_obj, tf, tf_lower, status):
        """Emit status tag to transient_signals."""
        ts = getattr(state_obj, "transient_signals", None)
        if isinstance(ts, dict):
            ts[f"cisd_{tf_lower}_{status}"] = {
                "tf": tf,
                "status": status,
                "category": "cisd_mtf",
            }

        symbol = getattr(state_obj, "symbol", "UNKNOWN")
        logger.info(
            f"[{symbol}] [CISD-MTF] {status.upper()} on {tf}"
        )
