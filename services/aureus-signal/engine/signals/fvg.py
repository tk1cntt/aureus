from .base import BaseSignal
import logging
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger("aureus-signal.fvg")

class FVGSignal(BaseSignal):
    """Signal Calculator for Fair Value Gaps."""
    
    def __init__(self):
        super().__init__("FVG")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if len(df) < 3:
            return None
        
        c1 = df.iloc[-3]
        c2 = df.iloc[-2]
        c3 = df.iloc[-1]
        result = None
        
        # Bullish FVG
        if c3['l'] > c1['h']:
            fvg_data = {
                "t": int(c3['t']),
                "direction": "BULLISH",
                "top": float(c3['l']),
                "bottom": float(c1['h']),
                "msg": "New Bullish FVG"
            }
            state_obj.add_fvg(fvg_data)
            
            # Story 3.5: Emit event for Event-Driven Sparse Storage
            if hasattr(state_obj, 'transient_signals'):
                state_obj.transient_signals['fvg_bull_new'] = fvg_data
                
            result = fvg_data
            
        # Bearish FVG
        elif c3['h'] < c1['l']:
            fvg_data = {
                "t": int(c3['t']),
                "direction": "BEARISH",
                "top": float(c1['l']),
                "bottom": float(c3['h']),
                "msg": "New Bearish FVG"
            }
            state_obj.add_fvg(fvg_data)
            
            # Story 3.5: Emit event for Event-Driven Sparse Storage
            if hasattr(state_obj, 'transient_signals'):
                state_obj.transient_signals['fvg_bear_new'] = fvg_data
                
            result = fvg_data

        # Story 3.5: Check for FVG mitigation events
        self._check_mitigations(df, state_obj)
            
        return result

    def _check_mitigations(self, df: pd.DataFrame, state_obj: Any):
        """Detect FVG mitigation on the current candle and emit transient signals."""
        if not hasattr(state_obj, 'fvgs') or not state_obj.fvgs:
            return
        
        latest = df.iloc[-1]
        c_t = int(latest['t'])
        c_h = float(latest['h'])
        c_l = float(latest['l'])
        c_c = float(latest['c'])
        
        for fvg in state_obj.fvgs:
            if fvg.get('state') == 'BROKEN':
                continue
            if fvg.get('_mitigated_emitted'):
                continue
            
            is_bullish = fvg['direction'] == 'BULLISH'
            
            # Bullish FVG mitigated: price drops into or through the gap
            if is_bullish and c_l <= fvg['top']:
                fvg['_mitigated_emitted'] = True
                if hasattr(state_obj, 'transient_signals'):
                    state_obj.transient_signals['fvg_bull_mitigated'] = {
                        "t": c_t,
                        "direction": "BULLISH",
                        "fvg_t": fvg.get('t'),
                        "top": fvg['top'],
                        "bottom": fvg['bottom'],
                    }
                    logger.info(f"[{state_obj.symbol}] Bullish FVG ({fvg.get('t')}) MITIGATED at {c_t}")
            
            # Bearish FVG mitigated: price rises into or through the gap 
            elif not is_bullish and c_h >= fvg['bottom']:
                fvg['_mitigated_emitted'] = True
                if hasattr(state_obj, 'transient_signals'):
                    state_obj.transient_signals['fvg_bear_mitigated'] = {
                        "t": c_t,
                        "direction": "BEARISH",
                        "fvg_t": fvg.get('t'),
                        "top": fvg['top'],
                        "bottom": fvg['bottom'],
                    }
                    logger.info(f"[{state_obj.symbol}] Bearish FVG ({fvg.get('t')}) MITIGATED at {c_t}")

