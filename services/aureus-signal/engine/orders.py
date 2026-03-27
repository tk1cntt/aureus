import logging
from engine.logging_common import get_logger
import json
from typing import Dict, List, Any

from engine.snapshot_utils import REQUIRED_ORDER_PLAN_KEYS

logger = get_logger(__name__)
PIPELINE_LOG_PREFIX = "[PIPELINE]"
class SimulatedTradeManager:
    """Manages creation, monitoring and closure of simulated trades."""
    
    def __init__(self, r):
        self.r = r # Redis client
        self.last_tick_events: List[str] = []  # Track trade events per candle cycle

    async def process_triggers(
        self,
        symbol: str,
        triggers: List[Dict[str, Any]],
        state_obj: Any,
        ai_validator: Any = None,
        execution_mode: str = "simulated",
    ):
        """Processes strategy triggers, checks TraceID, and generates simulated orders."""
        for t in triggers:
            strat_id = t.get('strategy_id', 0)
            origin_t = t.get('origin_timestamp')
            strategy_name = t.get('strategy', 'UNKNOWN')
            
            if not origin_t:
                logger.debug(
                    f"{PIPELINE_LOG_PREFIX}[D][process_triggers][missing_origin_timestamp] "
                    f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} "
                    f"reason_code=MISSING_ORIGIN_TIMESTAMP"
                )
                logger.warning(f"[{symbol}] [process_triggers] Error: Trigger {strategy_name} missing origin_timestamp, skipping order.")
                continue

            trace_id = f"{symbol}:{strat_id}:{origin_t}"
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[D][process_triggers][candidate] "
                f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} trace_id={trace_id}"
            )
            
            # Check for existing TraceID in Redis
            history_key = f"aureus:orders:history:{symbol}"
            if await self.r.sismember(history_key, trace_id):
                logger.debug(
                    f"{PIPELINE_LOG_PREFIX}[D][process_triggers][duplicate_trace] "
                    f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} trace_id={trace_id} "
                    f"reason_code=DUPLICATE_TRACE_ID"
                )
                continue # Already processed this setup

            order_plan_snapshot = self._build_order_plan_snapshot(t)

            # 1. Calculate SL/TP first so completeness validation can use computed levels.
            exit_config = t.get('exit_config', {})
            sl, tp = self._calculate_sl_tp(t, state_obj, exit_config)

            if sl is None or tp is None:
                logger.debug(
                    f"{PIPELINE_LOG_PREFIX}[D][process_triggers][sl_tp_calc_failed] "
                    f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} trace_id={trace_id} "
                    f"reason_code=SL_TP_CALC_FAILED sl={sl} tp={tp}"
                )
                logger.warning(f"[{symbol}] [process_triggers] Error: Failed to calculate SL/TP for {trace_id}, skipping.")
                continue

            # Enrich order-plan snapshot with concrete computed levels when missing.
            if order_plan_snapshot.get("sl_value") in (None, ""):
                order_plan_snapshot["sl_value"] = sl
            if order_plan_snapshot.get("tp_value") in (None, ""):
                order_plan_snapshot["tp_value"] = tp

            missing_order_plan_keys = self._missing_order_plan_keys(order_plan_snapshot)
            if missing_order_plan_keys:
                reason_payload = {
                    "trace_id": trace_id,
                    "symbol": symbol,
                    "strategy_id": strat_id,
                    "strategy_name": strategy_name,
                    "decision_phase": "process_triggers",
                    "status": "REJECTED",
                    "reason_code": "ORDER_PLAN_INCOMPLETE",
                    "missing_order_plan_keys": missing_order_plan_keys,
                    "origin_timestamp": int(origin_t),
                    "t": int(state_obj.last_candle.get("t", origin_t)),
                }
                self._persist_rejection(state_obj, reason_payload)
                await self.r.xadd(
                    f"aureus:stream:{symbol}:orders",
                    {
                        "type": "ORDER_REJECTED",
                        "data": json.dumps(reason_payload),
                    },
                )
                logger.debug(
                    f"{PIPELINE_LOG_PREFIX}[D][process_triggers][order_plan_incomplete] "
                    f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} trace_id={trace_id} "
                    f"reason_code=ORDER_PLAN_INCOMPLETE missing_keys={missing_order_plan_keys}"
                )
                logger.warning(
                    f"[{symbol}] [process_triggers] Trigger {strategy_name}: Incomplete order plan for {trace_id}. "
                    f"Missing keys: {missing_order_plan_keys}"
                )
                continue

            # It's a NEW trade!
            logger.debug(
                f"{PIPELINE_LOG_PREFIX}[D][process_triggers][new_trade] "
                f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} trace_id={trace_id}"
            )
            logger.info(f"[{symbol}] [process_triggers] NEW Simulated Trade Triggered: {trace_id}")
                
            # 2. Determine Side
            side = t.get('side')
            if not side:
                name = t['strategy'].lower()
                if 'up' in name or 'bull' in name: side = 'BUY'
                elif 'down' in name or 'bear' in name: side = 'SELL'
                else: side = 'BUY'

            # 3. Check if AI Validation is required
            # If ai_validator is provided and the strategy/system settings require it
            use_ai = t.get('ai_validation', False)
            status = "PENDING_AI" if use_ai and ai_validator else "ACTIVE"

            # 4. Create Order Object
            order = {
                "trace_id": trace_id,
                "symbol": symbol,
                "strategy_id": strat_id,
                "strategy_name": t['strategy'],
                "side": side,
                "type": "MARKET",
                "entry_price": float(state_obj.last_candle['c']),
                "sl": float(sl),
                "tp": float(tp),
                "status": status,
                "open_time": int(state_obj.last_candle['t']),
                "close_time": None,
                "pnl": 0.0,
                "exit_price": None,
                "execution_mode": execution_mode,
                "order_plan_snapshot": order_plan_snapshot,
                "ai_audit": None # Place for ACI and Debate Log
            }
            
            # 5. Save to Redis / State
            state_obj.simulated_orders.append(order)
            await self.r.sadd(history_key, trace_id)
            
            # 5b. Track event for sparse storage
            if status == "ACTIVE":
                self.last_tick_events.append("ORDER_OPENED")
            
            # Notify Gateway/Dashboard via Stream
            stream_type = "ORDER_PENDING" if status == "PENDING_AI" else "ORDER_OPEN"
            logger.info(
                f"[{symbol}] [process_triggers] {stream_type} entry_price={order.get('entry_price')} sl={order.get('sl')} tp={order.get('tp')} open_time={order.get('open_time')} " 
                f"trace_id={order.get('trace_id')} strategy_name={order.get('strategy_name')} strategy_id={order.get('strategy_id')} side={order.get('side')} type={order.get('type')} "
                f"status={order.get('status')} execution_mode={order.get('execution_mode')} ai_validation={order.get('ai_validation')} order_plan_snapshot={order.get('order_plan_snapshot')}")
            await self.r.xadd(f"aureus:stream:{symbol}:orders", {
                "type": stream_type,
                "data": json.dumps(order)
            })

            # 6. Trigger AI Audit Task if needed
            if status == "PENDING_AI":
                # We return the order so main.py can schedule the AI task
                return order

    async def handle_ai_decision(self, order: Dict[str, Any], audit_result: Dict[str, Any]):
        """Processes the AI verdict and updates the order status."""
        symbol = order['symbol']
        trace_id = order['trace_id']
        decision = audit_result.get('decision', 'REJECTED')
        
        order['ai_audit'] = audit_result
        
        if decision in ("ACTIVE", "REDUCED_RISK"):
            order['status'] = "ACTIVE"
            logger.info(f"[{symbol}] [handle_ai_decision] 1... AI APPROVED {trace_id}: {audit_result.get('key_insight')}")
            
            # If REDUCED_RISK, we might adjust position size here (conceptual for simulated)
            
            await self.r.xadd(f"aureus:stream:{symbol}:orders", {
                "type": "ORDER_OPEN",
                "data": json.dumps(order)
            })
        else:
            order['status'] = "REJECTED"
            logger.info(f"[{symbol}] [handle_ai_decision] 1... AI REJECTED {trace_id}: {audit_result.get('key_insight')}")
            
            await self.r.xadd(f"aureus:stream:{symbol}:orders", {
                "type": "ORDER_REJECTED",
                "data": json.dumps(order)
            })

    async def update_orders(self, symbol: str, candle: Dict[str, Any], state_obj: Any):
        """Monitors active orders for TP/SL hits."""
        high = float(candle['h'])
        low = float(candle['l'])
        bid = float(candle['c']) # Using Close as current price for MVP
        ask = bid # Simplified, spread not handled for simulated
        t = int(candle['t'])
        
        updated = False
        for order in state_obj.simulated_orders:
            if order['status'] != 'ACTIVE':
                continue
            
            hit = False
            exit_price = 0.0
            
            if order['side'] == 'BUY':
                if high >= order['tp']:
                    hit = True
                    exit_price = order['tp']
                elif low <= order['sl']:
                    hit = True
                    exit_price = order['sl']
            else: # SELL
                if low <= order['tp']:
                    hit = True
                    exit_price = order['tp']
                elif high >= order['sl']:
                    hit = True
                    exit_price = order['sl']
                    
            if hit:
                order['status'] = 'CLOSED'
                order['close_time'] = t
                order['exit_price'] = exit_price
                
                # Calculate PnL (in pips/points)
                if order['side'] == 'BUY':
                    order['pnl'] = exit_price - order['entry_price']
                else:
                    order['pnl'] = order['entry_price'] - exit_price
                
                # Track event for sparse storage
                if exit_price == order['sl']:
                    self.last_tick_events.append("SL_HIT")
                else:
                    self.last_tick_events.append("TP_HIT")
                
                logger.info(f"[{symbol}] [update_orders] 1... Trade CLOSED: {order['trace_id']} | PnL: {order['pnl']:.5f}")
                updated = True
                
                # Notify
                await self.r.xadd(f"aureus:stream:{symbol}:orders", {
                    "type": "ORDER_CLOSE",
                    "data": json.dumps(order)
                })
        
        return updated

    def _missing_order_plan_keys(self, order_plan_snapshot: Dict[str, Any]) -> List[str]:
        missing: List[str] = []
        for key in REQUIRED_ORDER_PLAN_KEYS:
            value = order_plan_snapshot.get(key)
            if value is None or value == "":
                missing.append(key)
        return missing

    def _normalize_mapping(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        return {}

    def _build_order_plan_snapshot(self, trigger: Dict[str, Any]) -> Dict[str, Any]:
        order_plan = self._normalize_mapping(trigger.get("order_plan"))
        exit_config = self._normalize_mapping(trigger.get("exit_config"))

        sl_cfg = self._normalize_mapping(order_plan.get("sl"))
        if not sl_cfg:
            sl_cfg = self._normalize_mapping(exit_config.get("sl"))

        tp_cfg = self._normalize_mapping(order_plan.get("tp"))
        if not tp_cfg:
            tp_cfg = self._normalize_mapping(exit_config.get("tp"))

        trailing_cfg = self._normalize_mapping(order_plan.get("trailing"))
        if not trailing_cfg:
            trailing_cfg = self._normalize_mapping(exit_config.get("trailing"))

        size_value = order_plan.get("size")
        size_mode = str(order_plan.get("size_mode", "FIXED_UNITS")).upper()

        expiry_policy = order_plan.get("expiry_policy")
        if not expiry_policy:
            expiry = order_plan.get("expiry", exit_config.get("expiry"))
            expiry_policy = str(expiry if expiry is not None else "BAR_CLOSE")

        snapshot = {
            "entry_type": order_plan.get("entry_type", "MARKET"),
            "entry_policy": order_plan.get("entry_policy", "IMMEDIATE"),
            "sl_mode": sl_cfg.get("mode", "PRICE"),
            "sl_value": sl_cfg.get("value"),
            "tp_mode": tp_cfg.get("mode", "PRICE"),
            "tp_value": tp_cfg.get("value"),
            "trailing_mode": trailing_cfg.get("mode", "NONE"),
            "trailing_value": trailing_cfg.get("value", 0.0),
            "size_mode": size_mode,
            "size_value": size_value,
            "expiry_policy": expiry_policy,
        }

        return snapshot

    def _persist_rejection(self, state_obj: Any, payload: Dict[str, Any]) -> None:
        if hasattr(state_obj, "record_order_rejection") and callable(state_obj.record_order_rejection):
            state_obj.record_order_rejection(payload)
            return

        if not hasattr(state_obj, "order_rejections"):
            state_obj.order_rejections = []
        state_obj.order_rejections.append(payload)
        if len(state_obj.order_rejections) > 500:
            state_obj.order_rejections = state_obj.order_rejections[-500:]

    def _calculate_sl_tp(self, trigger: Dict[str, Any], state_obj: Any, config: Dict[str, Any]):
        """Calculates prices for SL and TP based on strategy config."""
        entry = float(state_obj.last_candle['c'])
        sl = None
        tp = None
        
        sl_cfg = config.get('sl', {})
        tp_cfg = config.get('tp', {})
        
        # 1. Stop Loss
        mode = sl_cfg.get('mode', 'FIXED_PIPS')
        if mode == 'FIXED_PIPS':
            pips = sl_cfg.get('value', 300) / 10000.0 # Default 30 pips for FX
            if 'JPY' in trigger['strategy'] or state_obj.symbol.endswith('JPY'):
                 pips = sl_cfg.get('value', 300) / 100.0
                 
            sl = (entry - pips) if 'BUY' in trigger.get('side', 'BUY') else (entry + pips)
            
        elif mode == 'SIGNAL_LOW' or mode == 'SIGNAL_HIGH':
            target_tag = sl_cfg.get('tag')
            buffer = sl_cfg.get('buffer', 0) / 10000.0
            
            # Priority 1: Check if the trigger itself has an 'ob' field (standard for Structure signals)
            ob = trigger.get('ob')
            if ob and isinstance(ob, dict):
                if mode == 'SIGNAL_LOW':
                    sl = float(ob.get('bottom', entry)) - buffer
                else:
                    sl = float(ob.get('top', entry)) + buffer
            
            # Priority 2: Find the specific signal in progress history and match with swing points
            if sl is None:
                progress = json.loads(trigger['progress']) if isinstance(trigger['progress'], str) else trigger['progress']
                found_time = None
                for step in progress.get('sequence', []):
                    if step['tag'] == target_tag:
                        found_time = step['time']
                        break
                
                if found_time:
                    for sp in state_obj.swing_points:
                        if sp['t'] == found_time:
                            sl = sp['price'] + (buffer if mode == 'SIGNAL_HIGH' else -buffer)
                            break
            
            if sl is None: # Fallback to fixed distance
                pips = 300 / 10000.0
                sl = (entry - pips) if 'BUY' in trigger.get('side', 'BUY') else (entry + pips)

        # 2. Take Profit
        mode = tp_cfg.get('mode', 'RR')
        if mode == 'RR':
            ratio = tp_cfg.get('value', 1.5)
            risk = abs(entry - sl) if sl else (entry * 0.001)
            tp = entry + (risk * ratio) if 'BUY' in trigger.get('side', 'BUY') else entry - (risk * ratio)
        elif mode == 'FIXED_PIPS':
             pips = tp_cfg.get('value', 500) / 10000.0
             tp = (entry + pips) if 'BUY' in trigger.get('side', 'BUY') else (entry - pips)

        return sl, tp
