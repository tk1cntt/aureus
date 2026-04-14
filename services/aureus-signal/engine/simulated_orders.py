import logging
from engine.logging_common import get_logger
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from engine.orders import get_point_size, get_default_sl_pips
from engine.snapshot_utils import VALID_ENTRY_METHODS

logger = get_logger(__name__)
class SimulatedTradeManager:
    """
    Manages simulated trade lifecycle for Backtest Engine V5.
    Completely isolated from live trading systems (no engine.orders dependencies).
    """
    
    def __init__(self, r=None, run_id: str = None):
        self.r = r
        self.run_id = run_id
        self.active_orders: List[Dict[str, Any]] = []
        self.closed_orders: List[Dict[str, Any]] = []
        self.last_tick_events: List[str] = [] # Track events in the current candle
        logger.info("SimulatedTradeManager V2 initialized (Isolated-Mode with Advanced Logic).")

    async def process_triggers(self, symbol: str, triggers: List[Dict[str, Any]], state_obj: Any) -> int:
        """
        Processes strategy triggers, checks TraceID via Redis to avoid duplicates,
        calculates advanced SL/TP, and generates simulated orders.
        Returns the number of new orders opened.
        """
        if not self.r or not self.run_id:
            logger.error("SimulatedTradeManager requires Redis client and run_id to process triggers.")
            return 0

        new_orders_count = 0
        
        # Use imported or local get_redis_key logic
        clean_base = "orders:history"
        history_key = f"aureus:backtest:{self.run_id}:{symbol}:{clean_base}"

        for t in triggers:
            strat_id = t.get('strategy_id', 0)
            origin_t = t.get('origin_timestamp')
            
            if not origin_t:
                logger.warning(f"Trigger {t['strategy']} missing origin_timestamp, skipping order.")
                continue

            # Stale trigger check: skip if origin_timestamp is too far behind current candle time
            # Both are in the same reference system (candle unix timestamps).
            # If origin_timestamp > 5 seconds behind current candle, skip (realtime requirement).
            current_candle_t = int(state_obj.last_candle.get("t", 0))
            if current_candle_t > 0:
                trigger_age = current_candle_t - int(origin_t)
                if trigger_age > 5:
                    logger.warning(
                        f"Trigger {t.get('strategy', 'UNKNOWN')}: stale origin_timestamp={origin_t}, "
                        f"current_candle_t={current_candle_t}, age={trigger_age}s > 5s threshold, skipping."
                    )
                    continue

            # 1. Independent Order Tracking (TraceID)
            trace_id = f"{symbol}:{strat_id}:{origin_t}"
            
            # 2. Duplicate Avoidance (SISMEMBER)
            if await self.r.sismember(history_key, trace_id):
                continue # Already processed this setup

            logger.info(f"🚀 NEW Simulated Trade Setup Detected: {trace_id}")
            
            # 3. Determine Side (before SL/TP and entry_price)
            side = t.get('side')
            if not side:
                name = t['strategy'].lower()
                if 'up' in name or 'bull' in name: side = 'BUY'
                elif 'down' in name or 'bear' in name: side = 'SELL'
                else: side = 'BUY'

            # 4. Compute entry_price from order_plan entry_method
            order_plan = t.get('order_plan', {})
            entry_method = order_plan.get('entry_method', 'CURRENT')
            entry_value = order_plan.get('entry_value')
            entry_price = self._calculate_entry_price(side, state_obj, entry_method, entry_value)

            # 5. Advanced SL/TP Logic
            exit_config = t.get('exit_config', {})
            sl, tp = self._calculate_sl_tp(t, state_obj, exit_config, entry_price_override=entry_price)
            
            if sl is None or tp is None:
                logger.warning(f"Failed to calculate SL/TP for {trace_id}, skipping.")
                continue

            # 6. Create Order Object
            order = {
                "trace_id": trace_id,
                "symbol": symbol,
                "strategy_id": strat_id,
                "strategy_name": t['strategy'],
                "side": side.upper(),
                "entry_price": float(entry_price),
                "sl": float(sl),
                "tp": float(tp),
                "volume": 0.01, # Default fixed volume for backtest
                "status": "ACTIVE",
                # The order was definitively opened on THIS candle timestamp.
                # Must track this to prevent time-travel bias during update_orders.
                "open_time": int(state_obj.last_candle['t']),
                "close_time": None,
                "exit_price": None,
                "pnl": 0.0,
                "reason": None
            }
            
            # 6. Save to Memory and Mark in Redis
            self.active_orders.append(order)
            await self.r.sadd(history_key, trace_id)
            new_orders_count += 1
            self.last_tick_events.append("ORDER_OPENED") # Signal for sparse storage
            logger.info(f"✅ Simulated Order OPENED: {trace_id} ({side} at {order['entry_price']}) SL:{sl} TP:{tp}")

        return new_orders_count

    def _calculate_sl_tp(self, trigger: Dict[str, Any], state_obj: Any, config: Dict[str, Any], entry_price_override: float = None):
        """
        Calculates prices for SL and TP based on strategy config (Ported from Live Engine).

        SL value priority:
        1. Strategy config sl.value (if specified)
        2. symbols.json sl field (per-symbol default)
        3. REJECTED if signal point not found (no fallback)

        TP value priority:
        1. Strategy config tp.value (if specified)
        2. RR mode: default ratio 1.5 (if tp.value not specified)
        3. FIXED_PIPS mode: REJECTED if tp.value not specified

        Config keys: both 'type' and 'mode' are accepted for backward compatibility.
        Point size is loaded from symbols.json (single source of truth).

        Args:
            entry_price_override: Pre-computed entry price (for LIMIT/STOP).
                                  If None, uses current candle close.
        """
        entry = entry_price_override if entry_price_override is not None else float(state_obj.last_candle['c'])
        sl = None
        tp = None

        sl_cfg = config.get('sl', {})
        tp_cfg = config.get('tp', {})

        # 1. Stop Loss Logic
        point_size = get_point_size(state_obj.symbol)
        # Accept both 'type' and 'mode' keys for backward compatibility
        sl_mode = sl_cfg.get('mode') or sl_cfg.get('type', 'FIXED_PIPS')
        if sl_mode == 'FIXED_PIPS':
            # Priority: strategy config value > symbols.json sl > default 100
            raw_value = sl_cfg.get('value')
            if raw_value is None:
                raw_value = get_default_sl_pips(state_obj.symbol)
            price_delta = raw_value * point_size
            sl = (entry - price_delta) if 'BUY' in trigger.get('side', 'BUY') else (entry + price_delta)
            
        elif sl_mode in ('SIGNAL_LOW', 'SIGNAL_HIGH'):
            target_tag = sl_cfg.get('tag')
            buffer = sl_cfg.get('buffer', 0) * point_size
            
            # Priority 1: Check if the trigger itself has an 'ob' field (standard for Structure signals)
            ob = trigger.get('ob')
            if ob and isinstance(ob, dict):
                if sl_mode == 'SIGNAL_LOW':
                    sl = float(ob.get('bottom', entry)) - buffer
                else:
                    sl = float(ob.get('top', entry)) + buffer
            
            # Priority 2: Find the specific signal in progress history and match with swing points
            if sl is None:
                progress = trigger.get('progress')
                if isinstance(progress, str):
                    try:
                        progress = json.loads(progress)
                    except Exception:
                        progress = {}
                
                if isinstance(progress, dict):
                    found_time = None
                    for step in progress.get('sequence', []):
                        if step['tag'] == target_tag:
                            found_time = step['time']
                            break
                    
                    if found_time:
                        for sp in state_obj.swing_points:
                            if sp['t'] == found_time:
                                sl = sp['price'] + (buffer if sl_mode == 'SIGNAL_HIGH' else -buffer)
                                break
            
            if sl is None:
                logger.warning(
                    f"[_calculate_sl_tp] SL mode={sl_mode} but signal point not found — "
                    f"SL rejected for {trigger.get('strategy', 'UNKNOWN')}. "
                    f"Strategy must provide sl.value in exit_config or use FIXED_PIPS mode."
                )
                return None, None

        # 2. Take Profit Logic
        tp_mode = tp_cfg.get('mode', 'RR')
        if tp_mode == 'RR':
            ratio = tp_cfg.get('value', 1.5)  # default RR 1.5 per D-01, D-03
            if sl is None:
                logger.warning(
                    f"[_calculate_sl_tp] TP mode=RR but sl is None — "
                    f"TP rejected for {trigger.get('strategy', 'UNKNOWN')}"
                )
                return None, None
            risk = abs(entry - sl)
            tp = entry + (risk * ratio) if 'BUY' in trigger.get('side', 'BUY') else entry - (risk * ratio)
        elif tp_mode == 'FIXED_PIPS':
            raw_tp_value = tp_cfg.get('value')
            if raw_tp_value is None:
                logger.warning(
                    f"[_calculate_sl_tp] TP mode=FIXED_PIPS but no 'value' configured — "
                    f"TP rejected for {trigger.get('strategy', 'UNKNOWN')}. "
                    f"Strategy must provide tp.value in exit_config."
                )
                return sl, None
            price_delta = raw_tp_value * point_size
            tp = (entry + price_delta) if 'BUY' in trigger.get('side', 'BUY') else (entry - price_delta)

        return sl, tp

    def _calculate_entry_price(
        self, side: str, state_obj: Any,
        entry_method: str = "CURRENT",
        entry_value: Any = None,
    ) -> float:
        """Tính entry price theo phương án được config."""
        current_price = float(state_obj.last_candle['c'])
        method = str(entry_method or "CURRENT").upper()

        if method == "PULLBACK_50":
            return self._entry_pullback_50(side, state_obj, current_price)
        elif method == "OB_EDGE":
            return self._entry_ob_edge(side, state_obj, current_price)
        elif method == "EMA_TOUCH":
            return self._entry_ema_touch(side, state_obj, entry_value, current_price)
        elif method == "FIXED_OFFSET":
            return self._entry_fixed_offset(side, state_obj, entry_value, current_price)

        return current_price

    def _entry_pullback_50(self, side: str, state_obj: Any, fallback: float) -> float:
        candle = state_obj.last_candle
        h, l = float(candle['h']), float(candle['l'])
        return l + (h - l) * 0.5

    def _entry_ob_edge(self, side: str, state_obj: Any, fallback: float) -> float:
        obs = getattr(state_obj, 'obs', [])
        if not obs:
            return fallback
        for ob in reversed(obs):
            if ob.get('mitigated') or ob.get('broken'):
                continue
            ob_type = str(ob.get('ob_type', '')).upper()
            if side == 'BUY' and ob_type == 'BULLISH':
                return float(ob.get('bottom', fallback))
            elif side == 'SELL' and ob_type == 'BEARISH':
                return float(ob.get('top', fallback))
        return fallback

    def _entry_ema_touch(self, side: str, state_obj: Any, period_value: Any, fallback: float) -> float:
        period = 21
        if isinstance(period_value, (int, float)):
            period = int(period_value)
        elif isinstance(period_value, str):
            try:
                period = int(float(period_value))
            except (ValueError, TypeError):
                pass
        emas = getattr(state_obj, 'emas', {})
        ema_data = emas.get(period)
        if ema_data is None:
            return fallback
        ema_val = ema_data.get('value') if isinstance(ema_data, dict) else ema_data
        return float(ema_val) if ema_val is not None else fallback

    def _entry_fixed_offset(self, side: str, state_obj: Any, pips_value: Any, fallback: float) -> float:
        pips = None
        if isinstance(pips_value, (int, float)):
            pips = float(pips_value)
        elif isinstance(pips_value, str):
            try:
                pips = float(pips_value)
            except (ValueError, TypeError):
                pass
        if pips is None or pips <= 0:
            return fallback
        point_size = get_point_size(state_obj.symbol)
        offset = pips * point_size
        return fallback - offset if side == 'BUY' else fallback + offset

    def check_sl_tp(self, order: Dict[str, Any], candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Conservative check: evaluates SL before TP if both hit in same M1 candle.
        """
        high = float(candle['h'])
        low = float(candle['l'])
        
        if order['side'] == 'BUY':
            if low <= order['sl']:
                return {"hit": "SL", "price": order['sl']}
            if high >= order['tp']:
                return {"hit": "TP", "price": order['tp']}
        else: # SELL
            if high >= order['sl']:
                return {"hit": "SL", "price": order['sl']}
            if low <= order['tp']:
                return {"hit": "TP", "price": order['tp']}
        
        return None

    def update_orders(self, symbol: str, candle: Dict[str, Any], state_obj: Any) -> List[Dict[str, Any]]:
        """
        Process a new candle to check for SL/TP hits on active orders.
        """
        time_int = int(candle.get('t'))
        
        # Event lifecycle managed by engine (clears last_tick_events after snapshot check)
        # Both process_triggers and update_orders contribute events to the same tick
        
        closed_this_tick = []
        remaining_orders = []
        
        for order in self.active_orders:
            if order['symbol'] != symbol:
                remaining_orders.append(order)
                continue

            # REVIEW FIX 1: Prevent Look-Ahead (Time-Travel) Bias
            # The candle that opens the order cannot simultaneously close it.
            # SL/TP evaluation must start from the *next* candle.
            if order.get('open_time') == time_int:
                remaining_orders.append(order)
                continue
            
            result = self.check_sl_tp(order, candle)
            
            if result:
                reason = "SL HIT" if result['hit'] == "SL" else "TP HIT"
                # Add to tick events for sparse storage trigger
                self.last_tick_events.append("SL_HIT" if result['hit'] == "SL" else "TP_HIT")
                
                self._close_order_internal(order, result['price'], time_int, reason)
                closed_this_tick.append(order)
            else:
                remaining_orders.append(order)
        
        self.active_orders = remaining_orders
        return closed_this_tick

    def _close_order_internal(self, order: Dict[str, Any], exit_price: float, time: Any, reason: str):
        """
        Updates order fields for closure and moves to history.
        """
        order['status'] = 'CLOSED'
        order['close_time'] = time
        order['exit_price'] = float(exit_price)
        order['reason'] = reason
        
        if order['side'] == 'BUY':
            order['pnl'] = order['exit_price'] - order['entry_price']
        else:
            order['pnl'] = order['entry_price'] - order['exit_price']
            
        self.closed_orders.append(order)
        logger.info(f"✅ Simulated {order['side']} CLOSED: {order['trace_id']} | Reason: {reason} | PnL: {order['pnl']:.5f}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns basic performance stats for the session.
        """
        total = len(self.closed_orders)
        if total == 0:
            return {"total": 0, "winrate": 0, "net_pnl": 0}
            
        wins = len([o for o in self.closed_orders if o['pnl'] > 0])
        net_pnl = sum([o['pnl'] for o in self.closed_orders])
        
        return {
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "winrate": (wins / total) * 100,
            "net_pnl": net_pnl,
            "active_count": len(self.active_orders)
        }

