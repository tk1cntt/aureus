from typing import Dict, List, Any, Optional

class SymbolState:
    """Manages persistent state for a specific symbol (OBs, FVGs, Ranges)."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.reset()

    def reset(self):
        """Clears all internal state for a fresh start (e.g. on backfill)."""
        self.obs: List[Dict[str, Any]] = []
        self.fvgs: List[Dict[str, Any]] = []
        self.swing_points: List[Dict[str, Any]] = [] 
        self.signal_history: List[Dict[str, Any]] = [] 
        self.active_range: Optional[Dict[str, Any]] = None
        self.tracking_vars: Dict[str, Any] = {}
        self.last_candle: Optional[Dict[str, Any]] = None
        self.prev_candle: Optional[Dict[str, Any]] = None
        self.zigzag_engine: Any = None 
        self.simulated_orders: List[Dict[str, Any]] = []
        self.strategy_progress: Dict[str, Any] = {}
        self.candle_actors: Dict[str, Any] = {} 
        self.current_session: str = "OFF_MARKET"

        # Phase 10: Strategy lifecycle and validation ledgers (bounded, deterministic order)
        self.strategy_lifecycle_state: Dict[str, Dict[str, Any]] = {}
        self.strategy_last_transition: Dict[str, Dict[str, Any]] = {}
        self.strategy_transition_history: List[Dict[str, Any]] = []
        self.strategy_validator_failures: List[Dict[str, Any]] = []
        self.order_rejections: List[Dict[str, Any]] = []

        # Quantitative / Hybrid Data
        self.vol_sma_20: float = 1000.0 # Default for sims
        self.htf_trend: str = "NEUTRAL"
        self.market_regime: str = "SIDEWAYS"
        self.sweep_targets: List[Dict[str, Any]] = []
        self.emas: Dict[int, Any] = {}
        self.atr: float = 5.0
        self.atr_sma_20: float = 10.0
        self.news_events: List[Dict[str, Any]] = []
        
        # AI Control & Result Storage
        self.ai_update_pending: bool = False
        self.ai_trigger_events: List[str] = []
        self.aci: int = 50
        self.sentiment: str = "NEUTRAL"
        self.narrative: str = ""
        self.debate_log: List[str] = []

        # Transient Signals (Cleared every candle cycle)
        self.transient_signals: Dict[str, Any] = {}
        
        # Performance Tracking
        self.net_pnl: float = 0.0
        self.win_count: int = 0
        self.loss_count: int = 0
        self.trade_history: List[Dict[str, Any]] = []

    def log_signal(self, tag: str, timestamp: int, category: Optional[str] = None, value: Any = None, explain: Optional[str] = None, inputs: Optional[Dict[str, Any]] = None):
        # Defensive check in case of legacy state restoration
        if not hasattr(self, 'signal_history'):
            self.signal_history = []
            
        record = {"tag": tag, "t": timestamp}
        if category is not None:
            record["category"] = category
        if value is not None:
            record["value"] = value
        if explain is not None:
            record["explain"] = explain
        if inputs is not None:
            record["inputs"] = inputs

        self.signal_history.append(record)
        # Keep history reasonable
        if len(self.signal_history) > 1000:
            self.signal_history.pop(0)

    def request_ai_update(self, event_type: str):
        """Signals that an important event occurred and needs AI analysis."""
        self.ai_update_pending = True
        if event_type not in self.ai_trigger_events:
            self.ai_trigger_events.append(event_type)

    def log_actor(self, timestamp: int, actor_data: Dict[str, Any]):
        """Records metadata for a specific 'actor' candle."""
        self.candle_actors[str(timestamp)] = actor_data
        if len(self.candle_actors) > 200:
            oldest_key = sorted(self.candle_actors.keys())[0]
            del self.candle_actors[oldest_key]

    def add_ob(self, ob_data: Dict[str, Any]):
        # Deduplication Check
        for existing in self.obs:
            if existing['ob_type'] == ob_data['ob_type'] and \
               existing['t_start'] == ob_data['t_start'] and \
               abs(existing['top'] - ob_data['top']) < 1e-6 and \
               abs(existing['bottom'] - ob_data['bottom']) < 1e-6:
                return 

        ob_data['state'] = 'FRESH'
        ob_data['mitigated'] = False
        ob_data['broken'] = False
        
        # Implement Zone Cutting (Nesting Logic)
        for existing_ob in self.obs:
            if existing_ob.get('mitigated') or existing_ob.get('broken'):
                continue
            if existing_ob['ob_type'] == ob_data['ob_type']:
                if ob_data['top'] <= existing_ob['top'] and ob_data['bottom'] >= existing_ob['bottom']:
                    if ob_data['t_start'] > existing_ob['t_start']:
                        existing_ob['capped_time'] = ob_data['t_start']
        
        self.obs.append(ob_data)

    def add_fvg(self, fvg_data: Dict[str, Any]):
        fvg_data['state'] = 'FRESH'
        self.fvgs.append(fvg_data)

    def from_dict(self, data: Dict[str, Any]):
        """Restores state from a dictionary."""
        self.obs = data.get('obs', [])
        self.fvgs = data.get('fvgs', [])
        self.swing_points = data.get('swing_points', [])
        self.signal_history = data.get('signal_history', [])
        self.tracking_vars = data.get('tracking_vars', {})
        self.simulated_orders = data.get('active_orders', []) + data.get('closed_orders', [])
        self.strategy_progress = data.get('strategy_progress', {})
        self.candle_actors = data.get('candle_actors', {})
        
        # Quantitative / Hybrid
        self.aci = data.get('aci', 50)
        self.sentiment = data.get('sentiment', "NEUTRAL")
        self.narrative = data.get('narrative', "")
        self.debate_log = data.get('debate_log', [])
        self.vol_sma_20 = data.get('vol_sma_20', 1000.0)
        self.htf_trend = data.get('htf_trend', "NEUTRAL")
        self.market_regime = data.get('market_regime', "SIDEWAYS")

        self.strategy_lifecycle_state = data.get('strategy_lifecycle_state', {})
        self.strategy_last_transition = data.get('strategy_last_transition', {})
        self.strategy_transition_history = data.get('strategy_transition_history', [])
        self.strategy_validator_failures = data.get('strategy_validator_failures', [])
        self.order_rejections = data.get('order_rejections', [])

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current state for dashboard/UI consumption."""
        return {
            "symbol": self.symbol,
            "obs": sorted(self.obs, key=lambda x: x.get('t_breakout') or x.get('t_start') or 0, reverse=True),
            "fvgs": sorted(self.fvgs, key=lambda x: x.get('t_start') or 0, reverse=True),
            "swing_points": self.swing_points,
            "signal_history": sorted(getattr(self, 'signal_history', []), key=lambda x: x.get('t') or 0, reverse=True),
            "tracking_vars": self.tracking_vars,
            "last_candle": self.last_candle,
            "strategy_progress": self.strategy_progress,
            "candle_actors": self.candle_actors,
            "aci": self.aci,
            "sentiment": self.sentiment,
            "narrative": self.narrative,
            "debate_log": self.debate_log,
            "active_orders": [o for o in self.simulated_orders if o['status'] in ('ACTIVE', 'PENDING')],
            "closed_orders": sorted([o for o in self.simulated_orders if o['status'] == 'CLOSED'], key=lambda x: x.get('close_time', 0), reverse=True)[:10],
            "strategy_lifecycle_state": self.strategy_lifecycle_state,
            "strategy_last_transition": self.strategy_last_transition,
            "strategy_transition_history": self.strategy_transition_history,
            "strategy_validator_failures": self.strategy_validator_failures,
            "order_rejections": self.order_rejections,
        }

    def _append_bounded(self, ledger: List[Dict[str, Any]], entry: Dict[str, Any], max_items: int) -> None:
        ledger.append(entry)
        if len(ledger) > max_items:
            del ledger[0 : len(ledger) - max_items]

    def record_strategy_transition(
        self,
        strategy_id: str,
        current_state: str,
        next_state: str,
        transition_allowed: bool,
        validator_passed: bool,
        validator_failures: Optional[List[str]] = None,
        timestamp: Optional[int] = None,
    ) -> None:
        safe_strategy_id = str(strategy_id)
        transition = {
            "strategy_id": safe_strategy_id,
            "current_state": str(current_state),
            "next_state": str(next_state),
            "transition_allowed": bool(transition_allowed),
            "validator_passed": bool(validator_passed),
            "validator_failures": list(validator_failures or []),
            "t": int(timestamp if timestamp is not None else (self.last_candle or {}).get("t", 0)),
        }

        self.strategy_last_transition[safe_strategy_id] = transition
        self.strategy_lifecycle_state[safe_strategy_id] = {
            "current_state": transition["next_state"] if transition["transition_allowed"] else transition["current_state"],
            "last_transition_allowed": transition["transition_allowed"],
            "validator_passed": transition["validator_passed"],
            "last_updated_t": transition["t"],
        }

        self._append_bounded(self.strategy_transition_history, transition, 500)

        if transition["validator_failures"]:
            failure_entry = {
                "strategy_id": safe_strategy_id,
                "reason_code": "VALIDATOR_FAILED",
                "failures": transition["validator_failures"],
                "t": transition["t"],
            }
            self._append_bounded(self.strategy_validator_failures, failure_entry, 500)

    def record_validator_failure(
        self,
        strategy_id: str,
        reason_code: str,
        failures: Optional[List[str]] = None,
        timestamp: Optional[int] = None,
    ) -> None:
        entry = {
            "strategy_id": str(strategy_id),
            "reason_code": str(reason_code),
            "failures": list(failures or []),
            "t": int(timestamp if timestamp is not None else (self.last_candle or {}).get("t", 0)),
        }
        self._append_bounded(self.strategy_validator_failures, entry, 500)

    def record_order_rejection(self, payload: Dict[str, Any]) -> None:
        self._append_bounded(self.order_rejections, dict(payload), 500)

    def update_with_candle(self, candle: Dict[str, Any]):
        """Update lifecycle of all registered objects based on new price action."""
        if self.last_candle is not None:
            # Shift current last to prev
            self.prev_candle = self.last_candle.copy()
            
        self.last_candle = candle
        high = float(candle['h'])
        low = float(candle['l'])
        close = float(candle['c'])
        t = int(candle['t'])

        # 1. Update FVGs
        for fvg in self.fvgs:
            if fvg['state'] == 'BROKEN': continue
            
            # Check for touch
            if low <= fvg['top'] and high >= fvg['bottom']:
                if fvg['state'] == 'FRESH':
                    fvg['state'] = 'TOUCHED'
            
            # Simplified FVG break: Price closes on the other side
            if (fvg['direction'] == 'BULLISH' and close < fvg['bottom']) or \
               (fvg['direction'] == 'BEARISH' and close > fvg['top']):
                fvg['state'] = 'BROKEN'

        # Maintain State Size: Keep last 50 OBs and 50 FVGs
        if len(self.obs) > 50:
            self.obs = self.obs[-50:]
        if len(self.fvgs) > 50:
            self.fvgs = self.fvgs[-50:]
