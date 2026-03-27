"""
StateSnapshot — Unified data format for Live, Redis, DB, and Backtest.

Phase 7, Step 3: Ensures Live = Backtest data parity.
All engines produce and consume the same StateSnapshot object.
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


@dataclass
class StateSnapshot:
    """Unified snapshot for Live Engine, Redis State, DB Snapshot, and Backtest Engine."""

    # Identity
    symbol: str = ""
    timestamp: int = 0

    # Indicators
    atr: Optional[float] = None
    ema_21: Optional[float] = None
    ema_34: Optional[float] = None
    ema_55: Optional[float] = None
    ema_89: Optional[float] = None
    ema_100: Optional[float] = None
    ema_200: Optional[float] = None
    vol_sma_20: Optional[float] = None

    # Market Context
    htf_trend: Optional[str] = None
    market_regime: Optional[str] = None
    session: Optional[str] = None

    # Events (transient signals for this candle)
    events: Optional[str] = None         # JSON string of signal events

    # Structure — compact
    active_obs: Optional[str] = None     # JSON string of active OBs
    swing_label: Optional[str] = None    # HH/HL/LL/LH

    # Phase 7 expanded fields
    aci: int = 0
    sentiment: str = "NEUTRAL"
    narrative: Optional[str] = None
    obs_full: Optional[str] = None       # JSON: all OBs (active + mitigated)
    swing_points_snapshot: Optional[str] = None  # JSON: last 50 swing points
    strategy_progress: Optional[str] = None      # JSON: strategy tracking

    # -- Serialization Methods --

    def to_db_row(self) -> Dict[str, Any]:
        """Flat dict for INSERT into aureus_signal_snapshots."""
        dt = datetime.fromtimestamp(self.timestamp, tz=timezone.utc) if self.timestamp else None
        return {
            'time': dt,
            'symbol': self.symbol,
            'atr': self.atr,
            'ema_21': self.ema_21,
            'ema_34': self.ema_34,
            'ema_55': self.ema_55,
            'ema_89': self.ema_89,
            'ema_100': self.ema_100,
            'ema_200': self.ema_200,
            'vol_sma_20': self.vol_sma_20,
            'htf_trend': self.htf_trend,
            'market_regime': self.market_regime,
            'session': self.session,
            'events': self.events,
            'active_obs': self.active_obs,
            'swing_label': self.swing_label,
            'aci': self.aci,
            'sentiment': self.sentiment,
            'narrative': self.narrative,
            'obs_full': self.obs_full,
            'swing_points_snapshot': self.swing_points_snapshot,
            'strategy_progress': self.strategy_progress,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full dict for Redis state or JSON serialization."""
        return asdict(self)

    @classmethod
    def from_state(cls, state, candle: Dict[str, Any]) -> 'StateSnapshot':
        """Create a StateSnapshot from a SymbolState + candle dict.
        
        This replaces the old `build_snapshot()` function logic.
        """
        ts_unix = int(candle['t'])
        symbol = candle.get('symbol', state.symbol)

        # Extract EMA values
        def get_ema(period):
            v = state.emas.get(period)
            if isinstance(v, dict):
                return v.get('current')
            return v

        # Events
        events = None
        if state.transient_signals:
            events = json.dumps(list(state.transient_signals.values()))

        # Active OBs (non-mitigated, last 10)
        active_obs = None
        if hasattr(state, 'obs') and state.obs:
            live_obs = [ob for ob in state.obs if not ob.get('mitigated', False)][-10:]
            if live_obs:
                active_obs = json.dumps(live_obs)

        # Full OBs (all, last 20)
        obs_full = None
        if hasattr(state, 'obs') and state.obs:
            obs_full = json.dumps(state.obs[-20:])

        # Swing points (last 50)
        swing_points_snapshot = None
        if hasattr(state, 'swing_points') and state.swing_points:
            swing_points_snapshot = json.dumps(state.swing_points[-50:])

        # Strategy progress
        strategy_progress = None
        if hasattr(state, 'strategy_progress') and state.strategy_progress:
            strategy_progress = json.dumps(state.strategy_progress)

        # Swing label (if just updated)
        swing_label = None
        if state.swing_points:
            last_sp = state.swing_points[-1]
            if last_sp.get('t') == ts_unix:
                swing_label = last_sp.get('type', 'HH' if last_sp.get('is_high') else 'LL')

        return cls(
            symbol=symbol,
            timestamp=ts_unix,
            atr=state.atr if state.atr else None,
            ema_21=get_ema(21),
            ema_34=get_ema(34),
            ema_55=get_ema(55),
            ema_89=get_ema(89),
            ema_100=get_ema(100),
            ema_200=get_ema(200),
            vol_sma_20=state.vol_sma_20 if hasattr(state, 'vol_sma_20') else None,
            htf_trend=getattr(state, 'htf_trend', None),
            market_regime=getattr(state, 'market_regime', None),
            session=getattr(state, 'current_session', None),
            events=events,
            active_obs=active_obs,
            swing_label=swing_label,
            aci=getattr(state, 'aci', 0),
            sentiment=getattr(state, 'sentiment', 'NEUTRAL'),
            narrative=getattr(state, 'narrative', None),
            obs_full=obs_full,
            swing_points_snapshot=swing_points_snapshot,
            strategy_progress=strategy_progress,
        )

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'StateSnapshot':
        """Reconstruct a StateSnapshot from a DB row (asyncpg Record or dict)."""
        ts = row.get('time')
        if hasattr(ts, 'timestamp'):
            ts_unix = int(ts.timestamp())
        else:
            ts_unix = int(ts) if ts else 0

        def _json_field(val):
            """Parse JSON field — could be str or already-parsed dict/list."""
            if val is None:
                return None
            if isinstance(val, str):
                return val
            return json.dumps(val)

        return cls(
            symbol=row.get('symbol', ''),
            timestamp=ts_unix,
            atr=row.get('atr'),
            ema_21=row.get('ema_21'),
            ema_34=row.get('ema_34'),
            ema_55=row.get('ema_55'),
            ema_89=row.get('ema_89'),
            ema_100=row.get('ema_100'),
            ema_200=row.get('ema_200'),
            vol_sma_20=row.get('vol_sma_20'),
            htf_trend=row.get('htf_trend'),
            market_regime=row.get('market_regime'),
            session=row.get('session'),
            events=_json_field(row.get('events')),
            active_obs=_json_field(row.get('active_obs')),
            swing_label=row.get('swing_label'),
            aci=row.get('aci', 0) or 0,
            sentiment=row.get('sentiment', 'NEUTRAL') or 'NEUTRAL',
            narrative=row.get('narrative'),
            obs_full=_json_field(row.get('obs_full')),
            swing_points_snapshot=_json_field(row.get('swing_points_snapshot')),
            strategy_progress=_json_field(row.get('strategy_progress')),
        )

    def restore_to_state(self, state):
        """Apply this snapshot's values onto a SymbolState object.
        
        Used by backtest engine to reconstruct state from snapshot.
        """
        if self.atr is not None:
            state.atr = self.atr
        if self.ema_21 is not None:
            state.emas[21] = self.ema_21
            state.emas[34] = self.ema_34 or 0
            state.emas[55] = self.ema_55 or 0
            state.emas[89] = self.ema_89 or 0
            state.emas[100] = self.ema_100 or 0
            state.emas[200] = self.ema_200 or 0
        if self.vol_sma_20 is not None:
            state.vol_sma_20 = self.vol_sma_20
        if self.htf_trend:
            state.htf_trend = self.htf_trend
        if self.market_regime:
            state.market_regime = self.market_regime
        if self.session:
            state.current_session = self.session
        if self.aci:
            state.aci = self.aci
        if self.sentiment and self.sentiment != 'NEUTRAL':
            state.sentiment = self.sentiment

        # Restore events into transient_signals
        if self.events:
            try:
                events = json.loads(self.events) if isinstance(self.events, str) else self.events
                if isinstance(events, list):
                    for evt in events:
                        if not isinstance(evt, dict):
                            continue

                        tag = str(evt.get("tag", "")).strip().lower()
                        if not tag:
                            continue

                        value = evt.get("value")
                        data_payload = evt.get("data") if isinstance(evt.get("data"), dict) else None
                        if data_payload is None:
                            legacy_payload = {
                                key: val
                                for key, val in evt.items()
                                if key not in {"tag", "t", "value", "data"} and val is not None
                            }
                            data_payload = legacy_payload or None

                        restored_evt = {"tag": tag, "t": self.timestamp}
                        if value is not None:
                            restored_evt["value"] = value
                        if data_payload is not None:
                            restored_evt["data"] = data_payload
                        state.transient_signals[tag] = restored_evt

                        state.log_signal(
                            tag,
                            self.timestamp,
                            value=value,
                            data=data_payload,
                        )
            except Exception:
                pass

        # Restore full OBs (prefer obs_full over active_obs)
        obs_json = self.obs_full or self.active_obs
        if obs_json:
            try:
                obs = json.loads(obs_json) if isinstance(obs_json, str) else obs_json
                state.obs = obs
            except Exception:
                pass

        # Restore swing points
        if self.swing_points_snapshot:
            try:
                sp = json.loads(self.swing_points_snapshot) if isinstance(self.swing_points_snapshot, str) else self.swing_points_snapshot
                state.swing_points = sp
            except Exception:
                pass

        # Restore strategy progress
        if self.strategy_progress:
            try:
                sp = json.loads(self.strategy_progress) if isinstance(self.strategy_progress, str) else self.strategy_progress
                state.strategy_progress = sp
            except Exception:
                pass
