import logging
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = logging.getLogger("aureus-signal.sweep")

class SweepSignal(BaseSignal):
    """
    Monitors identified liquidity levels (Sweep Targets) for stop hunts.
    Implements Regime-based filtering (Trend vs Sideways).
    """
    TAG_BULL = "sweep_bull" # Price swept BELOW a target (Bullish setup)
    TAG_BEAR = "sweep_bear" # Price swept ABOVE a target (Bearish setup)
    
    def __init__(self):
        super().__init__("Stop Hunt / Sweep Monitor")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if state_obj is None:
            return None

        active_targets = getattr(state_obj, 'sweep_targets', None)
        if not isinstance(active_targets, list) or not active_targets:
            return None

        # The engine calls calculate at the beat of a NEW candle (meaning the last one just CLOSED)
        # So df.iloc[-1] is the finalized candle we evaluate for breaches.
        candle = df.iloc[-1]
        c_h = float(candle['h'])
        c_l = float(candle['l'])
        c_t = int(candle['t'])
        ts_c_t = pd.to_datetime(c_t, unit='s')

        symbol = getattr(state_obj, 'symbol', 'UNKNOWN')
        logger.debug(f"[t={c_t}] [{symbol}] [calculate] 1... SWEEP Signal Start")

        regime = getattr(state_obj, 'market_regime', 'SIDEWAYS')
        logger.debug(f"[t={c_t}] [{symbol}] [calculate] 2... SWEEP Signal Active Targets: {active_targets}")
        triggered_sweep = None
        
        updated_targets = []
        for target in active_targets:
            # logger.trace(f"[{symbol}][{c_t}]🎯 SWEEP Signal Target: {target}")
            # If we already triggered a sweep this candle, we just keep the rest for next time
            if triggered_sweep:
                updated_targets.append(target)
                continue

            side = target.get('side')
            target_price = target.get('price')
            if side not in ("BULLISH", "BEARISH") or target_price is None:
                updated_targets.append(target)
                continue

            is_swept = False
            tag = None

            # BULLISH Sweep: Price swept BELOW a target (Expect reversal UP)
            if side == "BULLISH":
                if c_l < target_price:
                    # Filter: In Trend cases, only allow sweeps that align with HTF flow
                    # If strong trend up, we only want bullish sweeps.
                    if regime in ["TREND_UP", "SIDEWAYS"]:
                        is_swept = True
                        tag = self.TAG_BULL

            # BEARISH Sweep: Price swept ABOVE a target (Expect reversal DOWN)
            elif side == "BEARISH":
                if c_h > target_price:
                    if regime in ["TREND_DN", "SIDEWAYS"]:
                        is_swept = True
                        tag = self.TAG_BEAR

            if is_swept:
                # Deduplicate check: Did we already log this sweep for this target?
                already_swept = any(
                    s.get('tag') == tag and s.get('price_swept') == target_price and s.get('t') == c_t
                    for s in getattr(state_obj, 'signal_history', [])
                )
                logger.info(f"[t={c_t}] [{symbol}] [calculate] 3... SWEEP Signal Already Swept: {already_swept}")

                if not already_swept:
                    triggered_sweep = {
                        "tag": tag,
                        "t": c_t,
                        "price_swept": target_price,
                        "source_type": target.get('type'),
                        "source_t": target.get('t_source'),
                        "fidelity": target.get('fidelity', 0.5), # Pass fidelity to Judge
                        "market_regime": regime
                    }
                    logger.info(f"[t={c_t}] [{symbol}] [calculate] 4... SWEEP DETECTED (Candle Close): {tag} @ {target_price} ({target.get('type')})")

                    # Register in transient signals for consumers
                    transient = getattr(state_obj, 'transient_signals', None)
                    if isinstance(transient, dict):
                        transient[tag] = triggered_sweep

                    request_ai_update = getattr(state_obj, 'request_ai_update', None)
                    if callable(request_ai_update):
                        request_ai_update("STOP_HUNT")
                else: # If it was swept but already recorded, keep the target for future evaluation
                    updated_targets.append(target)
            else: # If not swept, keep the target
                updated_targets.append(target)
                
        # Update state with remaining targets
        state_obj.sweep_targets = updated_targets
        
        return triggered_sweep
