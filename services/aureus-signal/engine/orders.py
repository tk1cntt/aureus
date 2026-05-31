import logging
from collections import deque
from engine.logging_common import get_logger
import json
import os
from typing import Dict, List, Any, Optional

from engine.snapshot_utils import REQUIRED_ORDER_PLAN_KEYS, VALID_ENTRY_TYPES, VALID_SIZE_MODES, VALID_ENTRY_METHODS

# Load symbol metadata from symbols.json — single source of truth for symbol parameters.
# When you change values in symbols.json, all calculations automatically use the new values.
_SYMBOLS_CONFIG: Dict[str, dict] = {}

# RISK_FIXED_AMOUNT default budget (configurable via .env)
_DEFAULT_RISK_BUDGET: float = 50.0  # fallback if env not set
def _get_default_risk_budget() -> float:
    """Read RISK_FIXED_AMOUNT_BUDGET from .env, fallback to 50.0."""
    env_val = os.getenv("RISK_FIXED_AMOUNT_BUDGET")
    if env_val:
        try:
            val = float(env_val)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    return _DEFAULT_RISK_BUDGET
_SYMBOLS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'symbols.json')
try:
    with open(_SYMBOLS_CONFIG_PATH, 'r') as f:
        _SYMBOLS_CONFIG = json.load(f)
except Exception as e:
    get_logger(__name__).error(f"Failed to load symbols.json from {_SYMBOLS_CONFIG_PATH}: {e}")

def _get_symbol_config(symbol: str) -> Optional[dict]:
    """Get symbol configuration from symbols.json."""
    return _SYMBOLS_CONFIG.get(symbol.upper())

def get_point_size(symbol: str) -> float:
    """Return point size for SL/TP calculation from symbols.json.

    This value is used to convert strategy SL/TP point values to price units:
        price_delta = sl_value * point_size
        sl_price = entry - price_delta (for BUY)

    Example: BTCUSD point=0.01, sl=15000 → delta = $150 SL distance
    """
    cfg = _get_symbol_config(symbol)
    if cfg and 'point' in cfg:
        return float(cfg['point'])

    get_logger(__name__).warning(
        f"Symbol {symbol.upper()} not found in symbols.json — using default point=0.00001. "
        f"Add it to symbols.json to configure the correct point size."
    )
    return 0.00001

def get_symbol_digits(symbol: str) -> int:
    """Return decimal digits for a symbol from symbols.json."""
    cfg = _get_symbol_config(symbol)
    if cfg and 'digits' in cfg:
        return int(cfg['digits'])

    get_logger(__name__).warning(
        f"Symbol {symbol.upper()} not found in symbols.json — using default digits=5. "
        f"Add it to symbols.json to configure the correct digits."
    )
    return 5

def get_default_sl_pips(symbol: str) -> int:
    """Return default SL in points from symbols.json."""
    cfg = _get_symbol_config(symbol)
    if cfg and 'sl' in cfg:
        return int(cfg['sl'])

    get_logger(__name__).warning(
        f"Symbol {symbol.upper()} not found in symbols.json or missing 'sl' field — using default sl=100. "
        f"Add it to symbols.json to configure the correct default SL."
    )
    return 100


def _get_pivot_sl_max_distance(symbol: str) -> Optional[float]:
    """Return max allowed PIVOT_POINT entry-to-SL price distance for guarded symbols."""
    sym = symbol.upper()
    if 'XAU' in sym:
        return 10.0
    if 'USTEC' in sym or 'NAS' in sym:
        return 50.0
    if 'BTC' in sym:
        return 500.0
    return None

logger = get_logger(__name__)
PIPELINE_LOG_PREFIX = "[PIPELINE]"

# Contract sizes for lot calculation (standard forex/CFD contracts)
_SYMBOL_CONTRACT_SIZES: Dict[str, float] = {}
_SYMBOL_CONTRACT_SIZES_PATH = os.path.join(os.path.dirname(__file__), '..', 'symbol_contracts.json')
try:
    with open(_SYMBOL_CONTRACT_SIZES_PATH, 'r') as f:
        _SYMBOL_CONTRACT_SIZES = json.load(f)
except Exception:
    pass  # Use defaults below

def get_contract_size(symbol: str) -> float:
    """Return contract size (units per lot) for lot calculation.

    Default contract sizes (standard CFD/forex):
    - Forex pairs (XXX/YYY): 100,000 units per lot
    - XAUUSD: 100 oz per lot
    - XAGUSD: 5,000 oz per lot
    - Indices (USTEC, US30, etc.): 1 unit per lot
    - Crypto (BTCUSD, ETHUSD): 1 unit per lot
    """
    cfg = _get_symbol_config(symbol)
    if cfg and 'contract_size' in cfg:
        return float(cfg['contract_size'])

    sym = symbol.upper()
    if sym in _SYMBOL_CONTRACT_SIZES:
        return float(_SYMBOL_CONTRACT_SIZES[sym])

    if sym in ('XAUUSD', 'GOLD'):
        return 100.0
    if sym in ('XAGUSD', 'SILVER'):
        return 5000.0
    if sym in ('USTEC', 'US30', 'US500', 'SPX500', 'NAS100', 'DJ30'):
        return 1.0
    if sym in ('BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD'):
        return 1.0
    return 100000.0  # Default: standard forex

def calculate_lot_size(symbol: str, entry_price: float, sl_price: float, risk_amount: float) -> float:
    """Tính lot size dựa trên số tiền rủi ro cố định và SL distance.

    Formula: lot = risk_amount / (sl_distance_in_price * contract_size)

    Args:
        symbol: Trading symbol
        entry_price: Entry price
        sl_price: Stop loss price
        risk_amount: Fixed dollar amount to risk (e.g., $50)

    Returns:
        Lot size rounded down to 2 decimal places (MT5 precision)
    """
    contract_size = get_contract_size(symbol)
    sl_distance = abs(entry_price - sl_price)

    if sl_distance <= 0 or contract_size <= 0:
        logger.warning(f"[lot_calc] Cannot calculate lot: sl_distance={sl_distance}, contract={contract_size}")
        return 0.01

    risk_per_lot = sl_distance * contract_size
    lot = risk_amount / risk_per_lot if risk_per_lot > 0 else 0.01
    lot = max(0.01, round(lot, 2))  # Floor at 0.01 lot

    logger.debug(f"[lot_calc] {symbol}: budget=${risk_amount}, entry={entry_price}, sl={sl_price}, "
                f"sl_dist={sl_distance:.5f}, contract={contract_size}, risk_per_lot=${risk_per_lot:.2f}, lot={lot}")
    return lot

class SimulatedTradeManager:
    """Manages creation, monitoring and closure of simulated trades."""
    
    def __init__(self, r):
        self.r = r # Redis client
        self.last_tick_events: List[str] = []  # Track trade events per candle cycle
        self._recent_trigger_keys: deque[str] = deque(maxlen=2000)
        self._recent_trigger_lookup: set[str] = set()

    def _build_trigger_dedupe_key(self, symbol: str, strategy_id: Any, origin_t: Any, side: str) -> str:
        return f"{symbol}:{strategy_id}:{origin_t}:{side}"

    def _mark_trigger_key(self, key: str) -> None:
        if key in self._recent_trigger_lookup:
            return
        if len(self._recent_trigger_keys) >= self._recent_trigger_keys.maxlen:
            expired = self._recent_trigger_keys.popleft()
            self._recent_trigger_lookup.discard(expired)
        self._recent_trigger_keys.append(key)
        self._recent_trigger_lookup.add(key)

    def _is_duplicate_trigger_key(self, key: str) -> bool:
        return key in self._recent_trigger_lookup

    async def process_triggers(
        self,
        symbol: str,
        triggers: List[Dict[str, Any]],
        state_obj: Any,
        ai_validator: Any = None,
        execution_mode: str = "simulated",
        recent_candles: Optional[List[Dict[str, Any]]] = None,
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

            # Stale trigger check: skip if origin_timestamp is too far behind current candle time
            # Both are in the same reference system (candle unix timestamps).
            # If origin_timestamp > 5 seconds behind current candle, skip (realtime requirement).
            current_candle_t = int(state_obj.last_candle.get("t", 0))
            if current_candle_t > 0:
                trigger_age = current_candle_t - int(origin_t)
                if trigger_age > 5:
                    logger.debug(
                        f"{PIPELINE_LOG_PREFIX}[D][process_triggers][stale_trigger] "
                        f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} "
                        f"origin_timestamp={origin_t} current_candle_t={current_candle_t} age_seconds={trigger_age} "
                        f"reason_code=STALE_TRIGGER"
                    )
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

            # 1. Determine Side (before SL/TP and entry_price)
            side = t.get('side')
            if not side:
                name = t['strategy'].lower()
                if 'up' in name or 'bull' in name: side = 'BUY'
                elif 'down' in name or 'bear' in name: side = 'SELL'
                else: side = 'BUY'

            trigger_key = self._build_trigger_dedupe_key(symbol, strat_id, origin_t, side)
            if self._is_duplicate_trigger_key(trigger_key):
                logger.debug(
                    f"{PIPELINE_LOG_PREFIX}[D][process_triggers][duplicate_trigger_key] "
                    f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} trigger_key={trigger_key} "
                    f"reason_code=DUPLICATE_TRIGGER_KEY"
                )
                continue

            # 2. Compute entry_price from entry_method
            entry_method = order_plan_snapshot.get("entry_method", "CURRENT")
            entry_value = order_plan_snapshot.get("entry_value")
            computed_entry = self._calculate_entry_price(side, state_obj, entry_method, entry_value)

            if computed_entry is None:
                reason_payload = {
                    "trace_id": trace_id,
                    "symbol": symbol,
                    "strategy_id": strat_id,
                    "strategy_name": strategy_name,
                    "decision_phase": "process_triggers",
                    "status": "REJECTED",
                    "reason_code": "ORDER_PLAN_INCOMPLETE",
                    "entry_method": entry_method,
                    "entry_error": "ENTRY_PRICE_UNAVAILABLE",
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
                logger.warning(
                    f"[{symbol}] [process_triggers] Trigger {strategy_name}: entry_method={entry_method} "
                    f"could not calculate entry price for {trace_id}; order rejected"
                )
                continue

            # 3. Calculate SL/TP using computed entry_price
            # config is pulled directly from t because registry.py flattens sl/tp configs onto the root of the map
            sl, tp = self._calculate_sl_tp(
                t,
                state_obj,
                t,
                entry_price_override=computed_entry,
                recent_candles=recent_candles,
            )

            if sl is None or tp is None:
                logger.debug(
                    f"{PIPELINE_LOG_PREFIX}[D][process_triggers][sl_tp_calc_failed] "
                    f"symbol={symbol} strategy={strategy_name} strategy_id={strat_id} trace_id={trace_id} "
                    f"reason_code=SL_TP_CALC_FAILED sl={sl} tp={tp}"
                )
                # When SL/TP cannot be calculated, treat as order plan incomplete
                # Enrich whatever we got and let missing_keys check handle the rejection
                if order_plan_snapshot.get("sl_value") in (None, "") and sl is not None:
                    order_plan_snapshot["sl_value"] = sl
                if order_plan_snapshot.get("tp_value") in (None, "") and tp is not None:
                    order_plan_snapshot["tp_value"] = tp

            # Enrich order-plan snapshot with concrete computed levels when missing.
            if order_plan_snapshot.get("sl_value") in (None, ""):
                order_plan_snapshot["sl_value"] = sl
            if order_plan_snapshot.get("tp_value") in (None, ""):
                order_plan_snapshot["tp_value"] = tp

            # 4. Validate order_plan structure (after SL/TP enrichment)
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

            # 5. Handle RISK_FIXED_AMOUNT mode — LOT will be calculated on MT5 side
            # using real-time Ask/Bid price for accurate SL distance
            size_mode = order_plan_snapshot.get("size_mode", "FIXED_UNITS")
            size_value = order_plan_snapshot.get("size_value")
            if size_mode == "RISK_FIXED_AMOUNT":
                risk_amount = size_value if isinstance(size_value, (int, float)) and size_value > 0 else _get_default_risk_budget()
                order_plan_snapshot["risk_amount"] = risk_amount
                order_plan_snapshot["size_value"] = 0  # Placeholder — MT5 calculates real lot
                logger.info(f"[{symbol}] RISK_FIXED_AMOUNT: budget=${risk_amount} — lot will be calculated on MT5")

            # 6. Check if AI Validation is required
            use_ai = t.get('ai_validation', False)
            status = "PENDING_AI" if use_ai and ai_validator else "ACTIVE"

            # 7. Create Order Object
            order = {
                "trace_id": trace_id,
                "symbol": symbol,
                "strategy_id": strat_id,
                "strategy_name": t['strategy'],
                "side": side,
                "type": order_plan_snapshot.get("entry_type", "MARKET"),
                "entry_price": float(computed_entry),
                "sl": float(sl),
                "tp": float(tp),
                "volume": order_plan_snapshot.get("size_value", 0.01),
                "status": status,
                "open_time": int(state_obj.last_candle['t']),
                "close_time": None,
                "pnl": 0.0,
                "exit_price": None,
                "execution_mode": execution_mode,
                "order_plan_snapshot": order_plan_snapshot,
                "ai_audit": None # Place for ACI and Debate Log
            }
            
            # 7. Save to Redis / State
            state_obj.simulated_orders.append(order)
            await self.r.sadd(history_key, trace_id)
            
            # 7b. Track event for sparse storage
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
            self._mark_trigger_key(trigger_key)

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

        # Validate entry_type
        entry_type = order_plan.get("entry_type", "MARKET")
        if entry_type not in VALID_ENTRY_TYPES:
            logger.warning(f"[orders] Invalid entry_type '{entry_type}', defaulting to MARKET")
            entry_type = "MARKET"

        # Validate entry_method
        entry_method = order_plan.get("entry_method", "CURRENT")
        if entry_method not in VALID_ENTRY_METHODS:
            logger.warning(f"[orders] Invalid entry_method '{entry_method}', defaulting to CURRENT")
            entry_method = "CURRENT"
        entry_value = order_plan.get("entry_value")

        # Validate size_mode
        if size_mode not in VALID_SIZE_MODES:
            logger.warning(f"[orders] Invalid size_mode '{size_mode}', defaulting to FIXED_UNITS")
            size_mode = "FIXED_UNITS"

        expiry_policy = order_plan.get("expiry_policy")
        if not expiry_policy:
            expiry = order_plan.get("expiry", exit_config.get("expiry"))
            expiry_policy = str(expiry if expiry is not None else "BAR_CLOSE")

        tp_rr_ratio = self._get_tp_rr_ratio(order_plan)

        snapshot = {
            "entry_type": entry_type,
            "entry_method": entry_method,
            "entry_value": entry_value,
            "entry_policy": order_plan.get("entry_policy", "IMMEDIATE"),
            "sl_mode": sl_cfg.get("mode", "PRICE"),
            "sl_value": sl_cfg.get("value"),
            "tp_mode": tp_cfg.get("mode", "PRICE"),
            "tp_value": tp_cfg.get("value"),
            "tp_rr_ratio": tp_rr_ratio,
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

    def _find_pivot_for_sl_candidates(self, side: str, state_obj: Any) -> List[Dict[str, float]]:
        """Trả về danh sách pivot candidates hợp lệ cho PIVOT_POINT SL.

        BUY → LL (Lower Low) gần nhất chưa broken.
        SELL → HH (Higher High) gần nhất chưa broken.
        """
        swing_points = getattr(state_obj, 'swing_points', [])
        if not swing_points:
            return []

        is_high = ('SELL' in side)  # SELL cần HH, BUY cần LL
        pivots: List[Dict[str, float]] = []

        for sp in swing_points:
            if sp.get('is_high') != is_high:
                continue
            if sp.get('broken') is True:
                continue
            sp_type = sp.get('type', '').upper()
            if is_high and sp_type != 'HH':
                continue
            if not is_high and sp_type != 'LL':
                continue
            try:
                pivots.append({"price": float(sp['price']), "t": float(sp['t'])})
            except (TypeError, ValueError, KeyError):
                continue

        return pivots

    def _calculate_sl_tp(
        self,
        trigger: Dict[str, Any],
        state_obj: Any,
        config: Dict[str, Any],
        entry_price_override: float = None,
        recent_candles: Optional[List[Dict[str, Any]]] = None,
    ):
        """Calculates prices for SL and TP based on strategy config.

        SL value priority:
        1. Strategy config sl.value (if specified)
        2. symbols.json sl field (per-symbol default)
        3. Default: 100 points

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

        strategy_name = trigger.get('strategy', 'UNKNOWN')
        symbol = state_obj.symbol
        side = trigger.get('side', 'BUY')

        # 1. Stop Loss
        point_size = get_point_size(symbol)
        # Accept both 'type' and 'mode' keys for backward compatibility
        sl_mode = sl_cfg.get('type', 'FIXED_PIPS')

        if sl_mode == 'FIXED_PIPS':
            # Priority: strategy config value > symbols.json sl > default 100
            raw_value = sl_cfg.get('value')
            if raw_value is None:
                raw_value = get_default_sl_pips(symbol)
                logger.debug(f"[{strategy_name}] [{symbol}] SL: strategy config has no value, "
                           f"using symbols.json default sl={raw_value}")

            price_delta = raw_value * point_size
            sl = (entry - price_delta) if 'BUY' in side else (entry + price_delta)
            logger.debug(f"[{strategy_name}] [{symbol}] SL: entry={entry}, mode=FIXED_PIPS, value={raw_value}, "
                        f"point={point_size}, delta={price_delta}, sl={sl}, side={side}")

        elif sl_mode == 'PIVOT_POINT':
            offset_pips = sl_cfg.get('offset_pips', 0)
            offset_distance = offset_pips * point_size

            pivots = self._find_pivot_for_sl_candidates(side, state_obj)
            selected_pivot = None

            lows: List[float] = []
            highs: List[float] = []
            if recent_candles and len(recent_candles) >= 5:
                last5 = recent_candles[-5:]
                for c in last5:
                    try:
                        lows.append(float(c.get('low', c.get('l'))))
                        highs.append(float(c.get('high', c.get('h'))))
                    except (TypeError, ValueError):
                        continue

            pivot_index = int(sl_cfg.get('pivot_index', 1) or 1)
            pivot_index = max(1, pivot_index)
            valid_pivots: List[Dict[str, float]] = []
            for pivot in pivots:
                pivot_price = pivot["price"]
                if len(lows) >= 5 and len(highs) >= 5:
                    if 'BUY' in side:
                        if min(lows) <= pivot_price:
                            logger.debug(
                                f"[{strategy_name}] [{symbol}] PIVOT_POINT reject BUY pivot={pivot_price} "
                                f"because min(low_5)={min(lows)} <= pivot"
                            )
                            continue
                    else:
                        if max(highs) >= pivot_price:
                            logger.debug(
                                f"[{strategy_name}] [{symbol}] PIVOT_POINT reject SELL pivot={pivot_price} "
                                f"because max(high_5)={max(highs)} >= pivot"
                            )
                            continue
                valid_pivots.append(pivot)

            valid_pivots.sort(key=lambda pivot: pivot["t"], reverse=True)
            if len(valid_pivots) >= pivot_index:
                selected_pivot = valid_pivots[pivot_index - 1]["price"]

            if selected_pivot is None:
                logger.warning(
                    f"[{strategy_name}] [{symbol}] PIVOT_POINT SL: no valid pivot after 5-candle filter "
                    f"for pivot_index={pivot_index}; order rejected"
                )
                return None, None
            else:
                if 'BUY' in side:
                    sl = selected_pivot - offset_distance
                else:
                    sl = selected_pivot + offset_distance
                sl_distance = abs(entry - sl)
                max_distance = _get_pivot_sl_max_distance(symbol)
                if max_distance is not None and sl_distance > max_distance:
                    logger.warning(
                        f"[{strategy_name}] [{symbol}] PIVOT_POINT SL rejected: entry={entry}, sl={sl}, "
                        f"distance={sl_distance}, threshold={max_distance}, reason=SL_DISTANCE_TOO_FAR"
                    )
                    return None, None
                logger.info(
                    f"[{strategy_name}] [{symbol}] SL: entry={entry}, mode=PIVOT_POINT, "
                    f"pivot_price={selected_pivot}, offset_pips={offset_pips}, offset_distance={offset_distance}, "
                    f"sl={sl}, side={side}"
                )

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
                progress = json.loads(trigger['progress']) if isinstance(trigger['progress'], str) else trigger['progress']
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
                logger.warning(f"[{strategy_name}] SL from SIGNAL_LOW/HIGH yielded None — no fallback, SL/TP rejected")
                return None, None

        # 2. Take Profit
        # Accept both 'type' and 'mode' keys for backward compatibility
        tp_mode = tp_cfg.get('mode') or tp_cfg.get('type', 'RR')

        if tp_mode in ('RR', 'RR_RATIO'):
            ratio = tp_cfg.get('value')
            if ratio is None:
                logger.warning(f"[{strategy_name}] TP mode=RR but no 'value' configured — TP cannot be calculated")
                return sl, None
            risk = abs(entry - sl) if sl else (entry * 0.001)
            tp = entry + (risk * ratio) if 'BUY' in side else entry - (risk * ratio)
            logger.debug(f"[{strategy_name}] [{symbol}] TP: entry={entry}, mode=RR, ratio={ratio}, "
                        f"risk={risk}, tp={tp}, side={side}")

        elif tp_mode == 'FIXED_PIPS':
             raw_tp_value = tp_cfg.get('value')
             if raw_tp_value is None:
                 logger.warning(f"[{strategy_name}] TP mode=FIXED_PIPS but no 'value' configured — TP cannot be calculated")
                 return sl, None
             price_delta = raw_tp_value * point_size
             tp = (entry + price_delta) if 'BUY' in side else (entry - price_delta)
             logger.debug(f"[{strategy_name}] [{symbol}] TP: entry={entry}, mode=FIXED_PIPS, value={raw_tp_value}, "
                         f"point={point_size}, delta={price_delta}, tp={tp}, side={side}")

        return sl, tp

    @staticmethod
    def _get_tp_rr_ratio(config: Dict[str, Any]) -> Optional[float]:
        """Lấy RR ratio từ TP config để MT5 tính lại TP từ entry thực tế.

        Returns ratio (ví dụ 1.5) hoặc None nếu TP không phải RR_RATIO.
        """
        tp_cfg = config.get('tp', {})
        tp_mode = tp_cfg.get('mode') or tp_cfg.get('type', 'RR')
        if tp_mode in ('RR', 'RR_RATIO'):
            ratio = tp_cfg.get('value')
            if ratio is not None:
                try:
                    return float(ratio)
                except (ValueError, TypeError):
                    pass
        return None

    def _calculate_entry_price(
        self, side: str, state_obj: Any,
        entry_method: str = "CURRENT",
        entry_value: Any = None,
    ) -> Optional[float]:
        """Tính entry price theo phương án được config."""
        current_price = float(state_obj.last_candle['c'])
        method = str(entry_method or "CURRENT").upper()

        if method == "CURRENT":
            return current_price
        if method == "PULLBACK_50":
            return self._entry_pullback_50(side, state_obj, current_price)
        elif method == "OB_EDGE":
            return self._entry_ob_edge(side, state_obj, current_price)
        elif method == "EMA_TOUCH":
            return self._entry_ema_touch(side, state_obj, entry_value, current_price)
        elif method == "FIXED_OFFSET":
            return self._entry_fixed_offset(side, state_obj, entry_value, current_price)
        elif method == "ENTRY_PIVOT_LIMIT":
            return self._entry_pivot_limit(side, state_obj, current_price)
        elif method == "ENTRY_FVG_FROM_CHOCH_PIVOT":
            return self._entry_fvg_from_choch_pivot(side, state_obj, current_price)
        elif method == "FIRST_HIGH_LOW_PIVOT":
            return self._entry_first_high_low_pivot(side, state_obj, current_price)
        elif method == "FIRST_LOW_HIGH_PIVOT":
            return self._entry_first_low_high_pivot(side, state_obj, current_price)

        logger.warning(f"[orders] Unknown entry_method '{entry_method}' — order rejected")
        return None

    def _entry_pullback_50(self, side: str, state_obj: Any, fallback: float) -> Optional[float]:
        """50% retracement từ swing point hợp lệ tới trigger candle."""
        candle = state_obj.last_candle
        current = float(candle['c'])
        is_buy = side == 'BUY'
        pivot_type = 'LL' if is_buy else 'HH'
        pivot_is_high = not is_buy
        for sp in reversed(getattr(state_obj, 'swing_points', [])):
            if sp.get('broken') is True or sp.get('is_high') != pivot_is_high:
                continue
            if str(sp.get('type', '')).upper() != pivot_type:
                continue
            try:
                pivot = float(sp['price'])
                edge = float(candle['h']) if is_buy else float(candle['l'])
            except (TypeError, ValueError, KeyError):
                continue
            entry = (pivot + edge) / 2
            if is_buy and entry >= current:
                logger.warning(f"[orders] PULLBACK_50 BUY entry={entry} is not below current={current} — order rejected")
                return None
            if not is_buy and entry <= current:
                logger.warning(f"[orders] PULLBACK_50 SELL entry={entry} is not above current={current} — order rejected")
                return None
            return entry
        logger.warning(f"[orders] PULLBACK_50 no valid {pivot_type} pivot — order rejected")
        return None

    def _entry_ob_edge(self, side: str, state_obj: Any, fallback: float) -> float:
        """Cạnh của OB chưa mitigate gần nhất. BUY → bottom, SELL → top."""
        obs = getattr(state_obj, 'obs', [])
        if not obs:
            logger.warning(f"[orders] OB_EDGE has no order blocks — order rejected")
            return None
        for ob in reversed(obs):
            if ob.get('mitigated') or ob.get('broken'):
                continue
            ob_type = str(ob.get('ob_type', '')).upper()
            if side == 'BUY' and ob_type == 'BULLISH':
                return float(ob.get('top', fallback))
            elif side == 'SELL' and ob_type == 'BEARISH':
                return float(ob.get('bottom', fallback))
        logger.warning(f"[orders] OB_EDGE no valid order block for side={side} — order rejected")
        return None

    def _entry_ema_touch(self, side: str, state_obj: Any, period_value: Any, fallback: float) -> float:
        """Giá EMA tại period được chỉ định."""
        period = 21  # default
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
            logger.warning(f"[orders] EMA_TOUCH missing EMA period={period} — order rejected")
            return None
        # ema_data có thể là dict {'value': ..., 'slope': ...} hoặc direct float
        ema_val = ema_data.get('value') if isinstance(ema_data, dict) else ema_data
        if ema_val is None:
            logger.warning(f"[orders] EMA_TOUCH EMA period={period} has no value — order rejected")
            return None
        return float(ema_val)

    def _entry_fixed_offset(self, side: str, state_obj: Any, pips_value: Any, fallback: float) -> float:
        """Current price +/- N pips. BUY trừ xuống, SELL cộng lên."""
        pips = None
        if isinstance(pips_value, (int, float)):
            pips = float(pips_value)
        elif isinstance(pips_value, str):
            try:
                pips = float(pips_value)
            except (ValueError, TypeError):
                pass
        if pips is None or pips <= 0:
            logger.warning(f"[orders] FIXED_OFFSET invalid entry_value={pips_value} — order rejected")
            return None
        point_size = get_point_size(state_obj.symbol)
        offset = pips * point_size
        return fallback - offset if side == 'BUY' else fallback + offset

    def _entry_pivot_limit(self, side: str, state_obj: Any, fallback: float) -> Optional[float]:
        """BUY dùng LL chưa broken dưới current; SELL dùng HH chưa broken trên current."""
        is_buy = side == 'BUY'
        pivot_type = 'LL' if is_buy else 'HH'
        pivot_is_high = not is_buy
        for sp in reversed(getattr(state_obj, 'swing_points', [])):
            if sp.get('broken') is True or sp.get('is_high') != pivot_is_high:
                continue
            if str(sp.get('type', '')).upper() != pivot_type:
                continue
            try:
                price = float(sp['price'])
            except (TypeError, ValueError, KeyError):
                continue
            if is_buy and price < fallback:
                return price
            if not is_buy and price > fallback:
                return price
        logger.warning(f"[orders] ENTRY_PIVOT_LIMIT no valid {pivot_type} pivot for side={side} — order rejected")
        return None

    def _entry_fvg_from_choch_pivot(self, side: str, state_obj: Any, fallback: float) -> Optional[float]:
        """BUY dùng FVG bullish đầu tiên sau LL; SELL dùng FVG bearish đầu tiên sau HH."""
        is_buy = side == 'BUY'
        pivot_type = 'LL' if is_buy else 'HH'
        pivot_is_high = not is_buy
        pivot_t = None
        for sp in reversed(getattr(state_obj, 'swing_points', [])):
            if sp.get('broken') is True or sp.get('is_high') != pivot_is_high:
                continue
            if str(sp.get('type', '')).upper() != pivot_type:
                continue
            try:
                pivot_t = float(sp['t'])
                break
            except (TypeError, ValueError, KeyError):
                continue
        if pivot_t is None:
            logger.warning(f"[orders] ENTRY_FVG_FROM_CHOCH_PIVOT no valid {pivot_type} pivot for side={side} — order rejected")
            return None

        wanted = 'BULLISH' if is_buy else 'BEARISH'
        candidates: List[Dict[str, Any]] = []
        for fvg in getattr(state_obj, 'fvgs', []):
            if str(fvg.get('direction', '')).upper() != wanted:
                continue
            if str(fvg.get('state', '')).upper() == 'BROKEN' or fvg.get('broken') is True:
                continue
            raw_t = fvg.get('t', fvg.get('t_start'))
            try:
                fvg_t = float(raw_t)
                top = float(fvg['top'])
                bottom = float(fvg['bottom'])
            except (TypeError, ValueError, KeyError):
                continue
            if fvg_t < pivot_t:
                continue
            candidates.append({'t': fvg_t, 'top': top, 'bottom': bottom})

        if not candidates:
            logger.warning(f"[orders] ENTRY_FVG_FROM_CHOCH_PIVOT no valid {wanted} FVG after {pivot_type} pivot — order rejected")
            return None

        selected = sorted(candidates, key=lambda item: item['t'])[0]
        return (selected['top'] + selected['bottom']) / 2

    def _entry_first_high_low_pivot(self, side: str, state_obj: Any, fallback: float) -> Optional[float]:
        """BUY: entry at first LOW pivot after BOS_up (low that created the BOS high)."""
        is_buy = side == 'BUY'
        if not is_buy:
            logger.warning(f"[orders] FIRST_HIGH_LOW_PIVOT only supports BUY side — order rejected")
            return None
        # For BUY: find LL pivot that created BOS_up
        pivot_type = 'LL'
        pivot_is_high = False  # LL is low pivot
        for sp in reversed(getattr(state_obj, 'swing_points', [])):
            if sp.get('broken') is True or sp.get('is_high') != pivot_is_high:
                continue
            if str(sp.get('type', '')).upper() != pivot_type:
                continue
            # Check if this LL corresponds to BOS_up trigger (has bos_up signal)
            if sp.get('bos_up'):
                try:
                    return float(sp['price'])
                except (TypeError, ValueError, KeyError):
                    continue
        # Fallback: get first valid LL if no BOS marker
        for sp in reversed(getattr(state_obj, 'swing_points', [])):
            if sp.get('broken') is True or sp.get('is_high') != pivot_is_high:
                continue
            if str(sp.get('type', '')).upper() != pivot_type:
                continue
            try:
                return float(sp['price'])
            except (TypeError, ValueError, KeyError):
                continue
        logger.warning(f"[orders] FIRST_HIGH_LOW_PIVOT no valid LL pivot for side={side} — order rejected")
        return None

    def _entry_first_low_high_pivot(self, side: str, state_obj: Any, fallback: float) -> Optional[float]:
        """SELL: entry at first HIGH pivot after BOS_down (high that created the BOS low)."""
        is_sell = side == 'SELL'
        if not is_sell:
            logger.warning(f"[orders] FIRST_LOW_HIGH_PIVOT only supports SELL side — order rejected")
            return None
        # For SELL: find HH pivot that created BOS_down
        pivot_type = 'HH'
        pivot_is_high = True  # HH is high pivot
        for sp in reversed(getattr(state_obj, 'swing_points', [])):
            if sp.get('broken') is True or sp.get('is_high') != pivot_is_high:
                continue
            if str(sp.get('type', '')).upper() != pivot_type:
                continue
            # Check if this HH corresponds to BOS_down trigger (has bos_down signal)
            if sp.get('bos_down'):
                try:
                    return float(sp['price'])
                except (TypeError, ValueError, KeyError):
                    continue
        # Fallback: get first valid HH if no BOS marker
        for sp in reversed(getattr(state_obj, 'swing_points', [])):
            if sp.get('broken') is True or sp.get('is_high') != pivot_is_high:
                continue
            if str(sp.get('type', '')).upper() != pivot_type:
                continue
            try:
                return float(sp['price'])
            except (TypeError, ValueError, KeyError):
                continue
        logger.warning(f"[orders] FIRST_LOW_HIGH_PIVOT no valid HH pivot for side={side} — order rejected")
        return None
