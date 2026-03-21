import logging
from engine.logging_common import get_logger
from .base import BaseSignal
import pandas as pd
from typing import Dict, Any, Optional, List

logger = get_logger(__name__)
class StructureSignal(BaseSignal):
    """
    Detects Market Structure Shifts (CHoCH) and creates Order Blocks (OB).
    Strict 1:1 port of MQL5 ProcessZigZag / ProcessCHOCH logic.
    """
    TAG_CHOCH_UP = "choch_up"
    TAG_CHOCH_DN = "choch_down"
    
    def __init__(self):
        super().__init__("Market Structure Processor (MQL5 Parity)")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if len(df) < 5 or state_obj is None:
            return None

        points = getattr(state_obj, 'swing_points', None)
        if not isinstance(points, list) or not points:
            return None

        nPoints = len(points)
        
        # --- Performance Optimization ---
        # Generate timestamp to integer positional index mapping once per cycle.
        # This replaces the old caching which became stale when len(df) was 
        # constant in a rolling window.
        t_values = df['t'].values
        t_map = {int(t): i for i, t in enumerate(t_values)}
        
        # Pivot-Centric Scan: Iterate through every historical pivot
        # Check if it has been broken by subsequent price action
        new_signals = []
        for i in range(nPoints):
            p = points[i]
            if p.get('is_choch'): continue
            
            # User Rule: Only HH and LL swing points trigger CHOCH on breach.
            # (LH and HL are considered internal structure and ignored for CHOCH).
            if p.get('type') not in ["HH", "LL"]:
                continue
            
            is_bullish = p['is_high']
            
            # Using i as both starting scan index and pivot index
            signal = self._process_choch(df, points, i, i, is_bullish, state_obj=state_obj, t_map=t_map)
            if signal:
                new_signals.append(signal)
                # Also store in transient_signals for consumer outlets
                tag = signal.get('tag')
                if tag:
                    history = getattr(state_obj, 'signal_history', [])
                    transient = getattr(state_obj, 'transient_signals', None)
                    is_duplicate = any(
                        s.get('tag') == tag for s in history if s.get('t') == signal.get('breakout_t')
                    )
                    if not is_duplicate and isinstance(transient, dict):
                        transient[tag] = signal

        self._verify_mitigations(df, state_obj)

        # Soft Garbage Collection: Prevent memory leak from endless OB array
        if hasattr(state_obj, 'obs') and isinstance(state_obj.obs, list) and len(state_obj.obs) > 200:
            unmitigated = [ob for ob in state_obj.obs if not ob.get('mitigated')]
            mitigated = [ob for ob in state_obj.obs if ob.get('mitigated')]
            if len(mitigated) > 50:
                state_obj.obs = sorted(unmitigated + mitigated[-50:], key=lambda x: x.get('t_start', 0))

        # Traceability v1.1: Export explicit ob_state to transient_signals for Factory consumption
        if hasattr(state_obj, 'transient_signals') and isinstance(state_obj.transient_signals, dict):
            state_obj.transient_signals["ob_state"] = {
                "active_obs": [
                    {
                        "top": ob.get("top"),
                        "bottom": ob.get("bottom"),
                        "ob_type": ob.get("ob_type"),
                        "t_start": ob.get("t_start"),
                        "mitigated": ob.get("mitigated", False)
                    } for ob in getattr(state_obj, 'obs', [])
                ]
            }

        if new_signals:
            return new_signals[-1]
            
        return None

    def _verify_mitigations(self, df: pd.DataFrame, state_obj: Any):
        """Mirrors MQL5 VerifyMitigation with historical sweep to find exact touch time."""
        if not hasattr(state_obj, 'obs') or not state_obj.obs:
            return
            
        latest_t = int(df.iloc[-1]['t'])
        
        for ob in state_obj.obs:
            if ob.get('mitigated'): continue
            
            t_breakout = ob.get('t_breakout', 0)
            last_checked_t = ob.get('_last_checked_t', t_breakout)
            
            if latest_t <= last_checked_t: continue
            
            # Optimized Sweep: Find only the candles AFTER the last checked time
            search_df = df[df['t'] > last_checked_t]
            if search_df.empty: 
                continue
            
            is_bullish = (ob['ob_type'] == 'BULLISH')
            mitigated_in_this_run = False
            
            for _, candle in search_df.iterrows():
                c_t = int(candle['t'])
                c_h = float(candle['h'])
                c_l = float(candle['l'])
                
                if is_bullish:
                    if c_l <= ob['top']:
                        ob['mitigated'] = True
                        ob['t_mitigation'] = c_t
                        
                        # Rejection Quality (Wicking)
                        ob_zone_height = ob['top'] - ob['bottom']
                        penetration = ob['top'] - c_l
                        pen_ratio = (penetration / ob_zone_height) if ob_zone_height > 0 else 0
                        
                        # Evaluation: Closed out of zone? (Rejection strength)
                        is_rejection = candle['c'] > ob['top']
                        
                        log_actor = getattr(state_obj, 'log_actor', None)
                        if callable(log_actor):
                            log_actor(c_t, {
                                "type": "OB_TOUCH",
                                "ob_type": "BULLISH",
                                "ob_start": ob['t_start'],
                                "is_hard_break": candle['c'] < ob['bottom'], # Closed below zone
                                "rejection_quality": "HIGH" if is_rejection and pen_ratio > 0.3 else "NORMAL",
                                "candle": {
                                    "o": float(candle['o']), "h": float(candle['h']),
                                    "l": float(candle['l']), "c": float(candle['c'])
                                }
                            })

                        symbol = getattr(state_obj, 'symbol', 'UNKNOWN')
                        logger.debug(f"[t={c_t}] [{symbol}] [_verify_mitigations] 1... Bullish OB ({ob['t_start']}) MITIGATED at {c_t}")
                        request_ai_update = getattr(state_obj, 'request_ai_update', None)
                        if c_t == latest_t and callable(request_ai_update):
                            request_ai_update("OB_INTERACTION") # Trigger AI ONLY if it just happened
                        # Story 3.5: Emit event for Event-Driven Sparse Storage
                        transient = getattr(state_obj, 'transient_signals', None)
                        if c_t == latest_t and isinstance(transient, dict):
                            transient['ob_bull_mitigated'] = ob
                        mitigated_in_this_run = True
                        break
                else: # BEARISH
                    if c_h >= ob['bottom']:
                        ob['mitigated'] = True
                        ob['t_mitigation'] = c_t

                        # Rejection Quality
                        ob_zone_height = ob['top'] - ob['bottom']
                        penetration = c_h - ob['bottom']
                        pen_ratio = (penetration / ob_zone_height) if ob_zone_height > 0 else 0

                        is_rejection = candle['c'] < ob['bottom']

                        log_actor = getattr(state_obj, 'log_actor', None)
                        if callable(log_actor):
                            log_actor(c_t, {
                                "type": "OB_TOUCH",
                                "ob_type": "BEARISH",
                                "ob_start": ob['t_start'],
                                "is_hard_break": candle['c'] > ob['top'], # Closed above zone
                                "rejection_quality": "HIGH" if is_rejection and pen_ratio > 0.3 else "NORMAL",
                                "candle": {
                                    "o": float(candle['o']), "h": float(candle['h']),
                                    "l": float(candle['l']), "c": float(candle['c'])
                                }
                            })

                        symbol = getattr(state_obj, 'symbol', 'UNKNOWN')
                        logger.debug(f"[t={c_t}] [{symbol}] [_verify_mitigations] 2... Bearish OB ({ob['t_start']}) MITIGATED at {c_t}")
                        request_ai_update = getattr(state_obj, 'request_ai_update', None)
                        if c_t == latest_t and callable(request_ai_update):
                            request_ai_update("OB_INTERACTION") # Trigger AI ONLY if it just happened
                        # Story 3.5: Emit event for Event-Driven Sparse Storage
                        transient = getattr(state_obj, 'transient_signals', None)
                        if c_t == latest_t and isinstance(transient, dict):
                            transient['ob_bear_mitigated'] = ob
                        mitigated_in_this_run = True
                        break
                        
            if not mitigated_in_this_run:
                # If we scanned everything and found no mitigation, update the checkpoint
                ob['_last_checked_t'] = int(search_df.iloc[-1]['t'])

    def _process_choch(self, df: pd.DataFrame, points: List[Dict[str, Any]], current_idx: int, pivot_idx: int, is_bullish: bool, state_obj: Any, t_map: Optional[Dict[int, int]] = None) -> Optional[Dict[str, Any]]:
        """Exact parity with ProcessCHOCH in MQL5."""
        pivot_price = points[pivot_idx]['price']
        pivot_t = points[pivot_idx]['t']
        
        # If already marked as CHOCH, don't re-trigger
        if points[pivot_idx].get('is_choch'):
            return None
            
        if t_map is None:
            t_map = {int(t): i for i, t in enumerate(df['t'].values)}
            
        pivot_t_int = int(pivot_t)
        
        if pivot_t_int not in t_map:
            start_idx = 0
        else:
            start_idx = t_map[pivot_t_int] + 1
            
        # Scan forward for breakout
        for k in range(start_idx, len(df)):
            candle = df.iloc[k]
            isBreak = (candle['h'] > pivot_price) if is_bullish else (candle['l'] < pivot_price)
            
            if isBreak:
                breakout_t = int(candle['t'])
                
                # OB Base Point Logic (Opposing Pivot Check)
                zone_base_idx = -1
                if is_bullish:
                    min_price = float('inf')
                    # Look for lowest LL AFTER the broken HH (pivot_idx) up to current time
                    for m in range(pivot_idx + 1, len(points)):
                        if points[m]['type'] == "LL" and points[m]['t'] < breakout_t:
                            if points[m]['price'] < min_price:
                                min_price = points[m]['price']
                                zone_base_idx = m
                else:
                    max_price = float('-inf')
                    # Look for highest HH AFTER the broken LL (pivot_idx) up to current time
                    for m in range(pivot_idx + 1, len(points)):
                        if points[m]['type'] == "HH" and points[m]['t'] < breakout_t:
                            if points[m]['price'] > max_price:
                                max_price = points[m]['price']
                                zone_base_idx = m
                
                # User Rule: Valid CHOCH REQUIRE an opposing extreme.
                # If no such point exists, this is a continuation, not a CHOCH.
                if zone_base_idx == -1:
                    return None
                            
                # --- CHOCH: Valid structural break with opposing extreme → create OB ---
                points[pivot_idx]['is_choch'] = True
                points[pivot_idx]['choch_type'] = "Up" if is_bullish else "Down"
                points[pivot_idx]['breakout_t'] = breakout_t
                points[pivot_idx]['chochConfirmingPointIndex'] = current_idx
                points[pivot_idx]['chochZoneBasePointIndex'] = zone_base_idx
                
                ob = self._process_ob(df, points, current_idx, pivot_idx, is_bullish, state_obj=state_obj, t_map=t_map)
                if ob:
                    symbol = getattr(state_obj, 'symbol', 'UNKNOWN')
                    ob['symbol'] = symbol
                    ob['breakout_t'] = breakout_t

                    add_ob = getattr(state_obj, 'add_ob', None)
                    if callable(add_ob):
                        add_ob(ob)

                    # Story 3.5: Emit event for Event-Driven Sparse Storage
                    transient = getattr(state_obj, 'transient_signals', None)
                    if breakout_t == int(df.iloc[-1]['t']) and isinstance(transient, dict):
                        if is_bullish:
                            transient['ob_bull_new'] = ob
                        else:
                            transient['ob_bear_new'] = ob

                    log_actor = getattr(state_obj, 'log_actor', None)
                    if callable(log_actor):
                        log_actor(breakout_t, {
                            "type": "CHOCH_BREAKOUT",
                            "symbol": symbol,
                            "side": "BULLISH" if is_bullish else "BEARISH",
                            "pivot_t": int(pivot_t),
                            "pivot_price": pivot_price,
                            "ob_t": ob['t_start'],
                            "candle": {
                                "o": float(candle['o']), "h": float(candle['h']),
                                "l": float(candle['l']), "c": float(candle['c'])
                            }
                        })

                    tag = self.TAG_CHOCH_UP if is_bullish else self.TAG_CHOCH_DN
                    # Determine if we already logged this to avoid spamming
                    already_logged = any(s.get('tag') == tag and s.get('t') == breakout_t for s in getattr(state_obj, 'signal_history', []))
                    if not already_logged:
                        logger.debug(f"[t={breakout_t}] [{symbol}] [_process_choch] 1... {tag} detected at {breakout_t} (Level: {pivot_price})")

                    request_ai_update = getattr(state_obj, 'request_ai_update', None)
                    if int(candle['t']) == int(df.iloc[-1]['t']) and not already_logged and callable(request_ai_update):
                        request_ai_update("CHOCH")
                        
                    self._register_sweep_targets(state_obj, ob, points[pivot_idx])
                    
                    return {"tag": tag, "t": int(candle['t']), "price": pivot_price, "breakout_t": breakout_t, "ob": ob}
                
                break # Only process the FIRST break
                
        return None

    def _register_sweep_targets(self, state_obj: Any, current_ob: Dict[str, Any], current_pivot: Dict[str, Any]):
        """Implements Institutional Sweep Selection logic with same-color pairing."""
        obs = getattr(state_obj, 'obs', [])
        
        # 1. Filter OBs by color
        bull_obs = [o for o in obs if o['ob_type'] == "BULLISH"]
        bear_obs = [o for o in obs if o['ob_type'] == "BEARISH"]

        # Helper to process a pair of same-color OBs
        def get_best_target(pair_obs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if len(pair_obs) < 2:
                # Strong Trend Filter: If < 2 same-color OBs, don't register target
                # User: "Nếu k tìm được 2 ob cùng màu hiện tại chứng tỏ trend xu hướng ngược lại đang mạnh"
                return None
            
            ob1 = pair_obs[-2] # Older
            ob2 = pair_obs[-1] # Newer
            is_bullish = ob2['ob_type'] == "BULLISH"
            
            # Check for FVG Gap (No touch)
            has_gap = False
            if is_bullish:
                if ob1['bottom'] > ob2['top']: has_gap = True
            else:
                if ob1['top'] < ob2['bottom']: has_gap = True
                
            # Check for Overlap (Intersection of ranges)
            is_overlap = max(ob1['bottom'], ob2['bottom']) < min(ob1['top'], ob2['top'])
                
            if has_gap:
                # FVG Rule: Select NEWEST (ob2)
                target_price = ob2['bottom'] if is_bullish else ob2['top']
                return {
                    "price": target_price,
                    "type": "ST_FVG_PAIR",
                    "fidelity": 1.0,
                    "side": ob2['ob_type'],
                    "t_source": ob2['t_start']
                }
            elif is_overlap:
                # Overlap Rule: Select OLDER (ob1)
                target_price = ob1['bottom'] if is_bullish else ob1['top']
                return {
                    "price": target_price,
                    "type": "ST_OVERLAP",
                    "fidelity": 0.7,
                    "side": ob1['ob_type'],
                    "t_source": ob1['t_start']
                }
            else:
                # Generic: Default to newest if neither rule applies strictly
                target_price = ob2['bottom'] if is_bullish else ob2['top']
                return {
                    "price": target_price,
                    "type": "ST_GENERIC",
                    "fidelity": 0.5,
                    "side": ob2['ob_type'],
                    "t_source": ob2['t_start']
                }

        # 2. Register Targets for each color
        new_targets = []
        
        bull_target = get_best_target(bull_obs)
        if bull_target: new_targets.append(bull_target)
        
        bear_target = get_best_target(bear_obs)
        if bear_target: new_targets.append(bear_target)

        # 3. CHOCH Origin as a "Failure" Sweep point
        new_targets.append({
            "price": current_pivot['price'],
            "type": "CHOCH_ORIGIN",
            "side": "BULLISH" if current_pivot['is_high'] else "BEARISH",
            "t_source": current_pivot['t']
        })
        
        # Merge with existing targets (keeping unique ones by price/source_t)
        existing_targets_raw = getattr(state_obj, 'sweep_targets', [])
        existing_targets: List[Dict[str, Any]] = existing_targets_raw if isinstance(existing_targets_raw, list) else []
        for nt in new_targets:
            if not any(et['price'] == nt['price'] and et['t_source'] == nt['t_source'] for et in existing_targets):
                existing_targets.append(nt)

        # Keep only the most recent targets to avoid over-calculating
        if len(existing_targets) > 10:
            existing_targets = existing_targets[-10:]

        state_obj.sweep_targets = existing_targets
        symbol = getattr(state_obj, 'symbol', 'UNKNOWN')
        logger.debug(f"[GLOBAL] [{symbol}] [_register_sweep_targets] 1... Updated Sweep Targets for {symbol}. Active count: {len(existing_targets)}")

    def _process_ob(self, df: pd.DataFrame, points: List[Dict[str, Any]], current_idx: int, pivot_idx: int, is_bullish: bool, state_obj: Any, t_map: Optional[Dict[int, int]] = None) -> Optional[Dict[str, Any]]:
        """Exact parity with the updated OB Logic: Find extreme candle between pivot and breakout."""
        try:
            pivot_t = points[pivot_idx]['t']
            pivot_price = points[pivot_idx]['price']
            
            # 1. Find the breakout candle time from the point metadata
            breakout_t = points[pivot_idx].get('breakout_t')
            if not breakout_t: return None
            
            if t_map is None:
                t_map = {int(t): i for i, t in enumerate(df['t'].values)}
                
            pivot_t_int = int(pivot_t)
            breakout_t_int = int(breakout_t)
            
            if pivot_t_int not in t_map or breakout_t_int not in t_map: 
                return None
                
            pivot_df_idx = t_map[pivot_t_int]
            breakout_df_idx = t_map[breakout_t_int]
            
            # 2. Window Search: [pivot_df_idx, breakout_df_idx]
            # Bearish Break of LL (is_bullish=False) => Find Highest HH candle in range
            # Bullish Break of HH (is_bullish=True)  => Find Lowest LL candle in range
            
            extreme_idx = -1
            if not is_bullish: # Bearish Breakout of LL -> Find Highest HH
                max_price = -1.0
                # Scan Pivot -> Breakout to find highest High
                for j in range(pivot_df_idx, breakout_df_idx + 1):
                    h_val = float(df.iloc[j]['h'])
                    if h_val > max_price: # Strict greater than finds the FIRST, ABSOLUTE highest peak
                        max_price = h_val
                        extreme_idx = j
            else: # Bullish Breakout of HH -> Find Lowest LL
                min_price = 1e18
                # Scan Pivot -> Breakout to find lowest Low
                for j in range(pivot_df_idx, breakout_df_idx + 1):
                    l_val = float(df.iloc[j]['l'])
                    if l_val < min_price: # Strict less than finds the FIRST, ABSOLUTE lowest trough
                        min_price = l_val
                        extreme_idx = j
            
            if extreme_idx == -1: return None
            
            ext_candle = df.iloc[extreme_idx]
            
            # OB Quality Calculation (Geometric)
            candle_range = float(ext_candle['h']) - float(ext_candle['l'])
            candle_body = abs(float(ext_candle['c']) - float(ext_candle['o']))
            body_ratio = (candle_body / candle_range) if candle_range > 0 else 0
            
            # Quality Label: Marubozu (Body > 80%), Standard (> 50%), Weak/Doji (< 50%)
            quality = "HIGH" if body_ratio > 0.8 else "MEDIUM" if body_ratio > 0.5 else "LOW"
            
            return {
                "ob_type": "BULLISH" if is_bullish else "BEARISH",
                "top": float(ext_candle['h']),
                "bottom": float(ext_candle['l']),
                "t_start": int(ext_candle['t']),
                "pivot_t": int(pivot_t),
                "t_breakout": int(breakout_t),
                "quality": quality,
                "body_ratio": round(body_ratio, 2),
                "ohlc": {
                    "o": float(ext_candle['o']), "h": float(ext_candle['h']),
                    "l": float(ext_candle['l']), "c": float(ext_candle['c'])
                }
            }
        except Exception as e:
            logger.error(f"[GLOBAL] [structure] [_process_ob] Error: Error processing OB: {e}")
            return None
