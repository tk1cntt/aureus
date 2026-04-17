import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from engine.logging_common import get_logger

logger = get_logger(__name__)

@dataclass
class CandleRecord:
    t: int
    price: float
    session: Optional[Dict[str, Any]] = None
    htf_trend: Optional[Dict[str, Any]] = None
    atr_14: Any = None
    zigzag: Optional[Dict[str, Any]] = None
    ema: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _events_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        signals: Dict[str, Any] = {}
        if self.session is not None:
            signals["market_session"] = self.session
        if self.htf_trend is not None:
            signals["htf_trend"] = self.htf_trend
        if self.atr_14 is not None:
            signals["atr_14"] = self.atr_14
        if self.zigzag is not None:
            signals["zigzag"] = self.zigzag
        if self.ema:
            signals["ema"] = dict(self.ema)
        if self._events_map:
            signals["events"] = list(self._events_map.values())

        return {
            "t": int(self.t),
            "price": float(self.price),
            "signals": signals,
        }


class _LoggedTransientSignals(dict):
    def __init__(self, symbol: str = "UNKNOWN", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._symbol = symbol or "UNKNOWN"

    def bind_symbol(self, symbol: str) -> None:
        self._symbol = symbol or "UNKNOWN"

    def _log_insert(self, key: Any, value: Any) -> None:
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            payload = repr(value)

        # logger.info(f"[transient_signals] [{self._symbol}] add key={key} payload={payload}")

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._log_insert(key, value)

    def update(self, *args, **kwargs):
        items = dict(*args, **kwargs)
        for key, value in items.items():
            self[key] = value


class SymbolState:
    """Manages persistent state for a specific symbol (OBs, FVGs, Ranges)."""

    @staticmethod
    def _coerce_transient_signals(value: Any, symbol: str) -> Dict[str, Any]:
        if isinstance(value, _LoggedTransientSignals):
            value.bind_symbol(symbol)
            return value

        wrapped = _LoggedTransientSignals(symbol=symbol)
        if isinstance(value, dict):
            dict.update(wrapped, value)

        return wrapped

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "transient_signals":
            symbol = self.__dict__.get("symbol", "UNKNOWN")
            value = self._coerce_transient_signals(value, symbol=symbol)
        super().__setattr__(name, value)
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.reset()

    def reset(self):
        """Clears all internal state for a fresh start (e.g. on backfill)."""
        self.obs: List[Dict[str, Any]] = []
        self.fvgs: List[Dict[str, Any]] = []
        self.swing_points: List[Dict[str, Any]] = [] 
        self.signal_history: List[Dict[str, Any]] = [] 
        self.log_signal_normalize: List[Dict[str, Any]] = []
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

        # Phase 44.2: Verification counter for incremental cache drift detection
        self._verification_counter: int = 0
        
        # AI Control & Result Storage
        self.ai_update_pending: bool = False
        self.ai_trigger_events: List[str] = []
        self.aci: int = 50
        self.sentiment: str = "NEUTRAL"
        self.narrative: str = ""
        self.debate_log: List[str] = []

        # Transient Signals (Cleared every candle cycle)
        self.transient_signals: Dict[str, Any] = {}
        
        # Current tick transient state
        self.current_signal: Optional[Dict[str, Any]] = None
        
        # Performance Tracking
        self.net_pnl: float = 0.0
        self.win_count: int = 0
        self.loss_count: int = 0
        self.trade_history: List[Dict[str, Any]] = []

    _STRUCTURE_TAGS = {
        "CHOCH_UP", "CHOCH_DOWN"
    }
    _EMA_TAG_RE = re.compile(r"^ema_(\d+)_(up|down)$", re.IGNORECASE)

    @staticmethod
    def _build_signal_payload(
        value_payload: Any,
        data_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if isinstance(value_payload, dict):
            payload.update(value_payload)
        elif value_payload is not None:
            payload["value"] = value_payload

        if isinstance(data_payload, dict):
            payload.update(data_payload)

        return payload

    def create_candle_record(self, timestamp: int, close: float) -> CandleRecord:
        return CandleRecord(t=int(timestamp), price=float(close))

    def map_signal_to_candle_record(
        self,
        record: CandleRecord,
        tag: str,
        value: Any = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not tag:
            return

        tag_lower = str(tag).lower()
        payload = self._build_signal_payload(value, data)

        if tag_lower in {"session", "market_session"}:
            record.session = payload if payload else ({"value": value} if value is not None else {})
            return

        if tag_lower == "htf_trend":
            record.htf_trend = payload if payload else ({"value": value} if value is not None else {})
            return

        if tag_lower == "atr_14":
            if payload:
                record.atr_14 = payload.get("value") if len(payload) == 1 and "value" in payload else payload
            else:
                record.atr_14 = value
            return

        if tag_lower == "zigzag":
            record.zigzag = payload if payload else ({"kind": value} if value is not None else {"kind": None})
            return

        ema_match = self._EMA_TAG_RE.match(str(tag))
        if ema_match:
            period, direction = ema_match.groups()
            ema_key = f"ema_{period}"
            ema_obj = payload if payload else {}
            ema_obj.setdefault("value", value)
            ema_obj["direction"] = direction.lower()
            record.ema[ema_key] = ema_obj
            return

        event_obj: Dict[str, Any] = {"tag": tag_lower}
        event_obj.update(payload)
        record._events_map[tag_lower] = event_obj

    def log_signal_normalize_add(self, record: CandleRecord) -> None:
        payload = record.to_dict() if isinstance(record, CandleRecord) else record
        if not isinstance(payload, dict):
            return

        signals = payload.get("signals") if isinstance(payload.get("signals"), dict) else {}
        if not signals:
            return

        self.log_signal_normalize.append(payload)
        # Phase 39.1 Stage 2: Configurable via .env (SIGNAL_HISTORY_MAX_SIZE)
        # Default: 200 records (safe because Stage 1 trigger timeout prevents permanent stalls)
        from engine.config import get_config
        max_size = get_config().signal_history_max_size
        if len(self.log_signal_normalize) > max_size:
            self.log_signal_normalize.pop(0)

    def _normalize_signal_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if getattr(self, "log_signal_normalize", None):
            return sorted(
                self.log_signal_normalize,
                key=lambda item: int(item.get("t", 0)) if isinstance(item, dict) else 0,
            )

        grouped: Dict[int, Dict[str, Any]] = {}

        for rec in history:
            if not isinstance(rec, dict):
                continue

            tag_raw = rec.get("tag")
            if tag_raw is None:
                continue

            timestamp = rec.get("t")
            try:
                t = int(timestamp)
            except (TypeError, ValueError):
                continue

            tag = str(tag_raw)
            tag_lower = tag.lower()
            data_payload = rec.get("data") if isinstance(rec.get("data"), dict) else {}
            value_payload = rec.get("value")

            if t not in grouped:
                grouped[t] = {
                    "t": t,
                    "signals": {
                        "ema": {},
                        "_events_map": {},
                    },
                }

            signals = grouped[t]["signals"]

            if tag_lower == "htf_trend":
                trend_obj: Dict[str, Any] = {}
                if value_payload is not None:
                    trend_obj["value"] = value_payload
                trend_obj.update(data_payload)
                signals["htf_trend"] = trend_obj if trend_obj else {"value": None}
                continue

            if tag_lower == "atr_14":
                signals["atr_14"] = value_payload
                continue

            if tag_lower == "market_session":
                session_obj: Dict[str, Any] = {}
                if value_payload is not None:
                    session_obj["value"] = value_payload
                session_obj.update(data_payload)
                signals["market_session"] = session_obj if session_obj else True
                continue

            if tag_lower == "zigzag":
                zigzag_obj: Dict[str, Any] = {}
                if isinstance(value_payload, dict):
                    zigzag_obj.update(value_payload)
                elif value_payload is not None:
                    zigzag_obj["kind"] = value_payload
                zigzag_obj.update(data_payload)
                if "explain" in rec:
                    zigzag_obj["explain"] = rec.get("explain")
                if "category" in rec:
                    zigzag_obj["category"] = rec.get("category")
                signals["zigzag"] = zigzag_obj if zigzag_obj else {"kind": None}
                continue

            ema_match = self._EMA_TAG_RE.match(tag)
            if ema_match:
                period, direction = ema_match.groups()
                ema_key = f"ema_{period}"
                ema_obj: Dict[str, Any] = {
                    "direction": direction.lower(),
                    "value": value_payload,
                }
                ema_obj.update(data_payload)
                signals["ema"][ema_key] = ema_obj
                continue

            event_obj: Dict[str, Any] = {"tag": tag_lower}
            if isinstance(value_payload, dict):
                event_obj.update(value_payload)
            elif value_payload is not None:
                event_obj["value"] = value_payload

            event_obj.update(data_payload)

            for passthrough_key in ("explain", "category", "inputs"):
                if passthrough_key in rec:
                    event_obj[passthrough_key] = rec.get(passthrough_key)

            # Keep latest event per tag in each timestamp group (overwrite semantics)
            signals["_events_map"][tag_lower] = event_obj

        output: List[Dict[str, Any]] = []
        for t in sorted(grouped.keys()):
            item = grouped[t]
            signals = item["signals"]

            events_map = signals.pop("_events_map", {})
            if events_map:
                signals["events"] = list(events_map.values())

            if not signals["ema"]:
                signals.pop("ema", None)
            if "events" in signals and not signals["events"]:
                signals.pop("events", None)

            output.append(item)

        return output

    def log_signal(self, tag: str, timestamp: int, value: Any = None, data: Optional[Dict[str, Any]] = None):
        # Defensive check in case of legacy state restoration
        if not hasattr(self, 'signal_history'):
            self.signal_history = []
            
        record = {"tag": tag, "t": timestamp}
        if value is not None:
            record["value"] = value
        if data is not None:
            record["data"] = data

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
        self.log_signal_normalize = data.get('signal_history_normalized', [])
        self.tracking_vars = data.get('tracking_vars', {})
        self.simulated_orders = data.get('active_orders', []) + data.get('closed_orders', [])
        self.strategy_progress = data.get('strategy_progress', {})
        self.candle_actors = data.get('candle_actors', {})
        self.current_signal = data.get('current_signal')
        
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
        source_signal_history = getattr(self, 'signal_history', [])

        def _safe_history_timestamp(entry: Any) -> int:
            if not isinstance(entry, dict):
                return 0
            try:
                return int(entry.get('t'))
            except (TypeError, ValueError):
                return 0

        raw_signal_history = sorted(
            source_signal_history,
            key=_safe_history_timestamp,
            reverse=True,
        )
        normalized_source = getattr(self, 'log_signal_normalize', [])
        if normalized_source:
            normalized_signal_history = sorted(
                normalized_source,
                key=lambda item: int(item.get('t', 0)) if isinstance(item, dict) else 0,
            )
        else:
            normalized_signal_history = self._normalize_signal_history(source_signal_history)

        return {
            "symbol": self.symbol,
            "obs": sorted(self.obs, key=lambda x: x.get('t_breakout') or x.get('t_start') or 0, reverse=True),
            "fvgs": sorted(self.fvgs, key=lambda x: x.get('t_start') or 0, reverse=True),
            "swing_points": self.swing_points,
            "signal_history": raw_signal_history,
            "signal_history_normalized": normalized_signal_history,
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
            "current_signal": self.current_signal,
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
