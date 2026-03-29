import logging
from engine.logging_common import get_logger
import json
import os
import time
from collections import Counter
from datetime import datetime
try:
    import pandas as pd
except ImportError:
    pd = None
from typing import Dict, Any, List, Optional

from .logic.orchestrator import HybridOrchestrator
from .logic.gates.news_gate import NewsGate
from .logic.judges.structure import CHOCHJudge, SweepJudge
from .logic.judges.liquidity import LiquidityJudge
from .logic.judges.momentum import MomentumJudge
from .logic.judges.patterns import MultiPatternJudge

logger = get_logger(__name__)
class ContextBuilder:
    """Synthesizes technical data into a descriptive narrative for AI Agents."""
    
    def build_market_context(self, symbol: str, df: 'pd.DataFrame', state_obj: Any, trigger: Dict[str, Any]) -> str:
        """Main entry point to generate the institutional-grade context string."""
        
        # 1. Macro Structure (Trend & Geometry)
        structure_summary = self._synthesize_structure(state_obj)
        
        # 2. Relative Positioning (Fibs, Levels)
        positioning = self._calculate_positioning(df, state_obj)
        
        # 3. Strategy Reasoning (The Logic)
        logic_description = self._describe_logic(trigger)
        
        # 4. Liquidity & Trap Analysis (SMC specific)
        liquidity_map = self._map_liquidity(state_obj, trigger)
        
        # 5. Volatility & Volume
        metrics = self._extract_metrics(df)
        
        # Final Assembly
        context = f"""
[MARKET CONTEXT: {symbol}]
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Last Price: {state_obj.last_candle['c']}

STRUCTURE & TREND:
{structure_summary}

GEOMETRIC POSITIONING:
{positioning}

TECHNICAL SETUP LOGIC:
{logic_description}

LIQUIDITY & SMC TRAP ANALYSIS:
{liquidity_map}

VOLATILITY & VOLUME METRICS:
{metrics}

TASK: analyze the technical validity of this {trigger.get('side', 'TRADE')} setup. 
Identify if this is a high-probability institutional alignment or a retail trap.
"""
        return context.strip()
    def build_pulse_context(self, symbol: str, df: 'pd.DataFrame', state_obj: Any, trigger_events: List[str] = None) -> str:
        """Build deterministic pulse context anchored on latest normalized signal records."""
        records = self._collect_pulse_records(state_obj, limit=60)

        trigger_list = [
            str(event).strip().upper()
            for event in (trigger_events or ["PERIODIC_PULSE"])
            if str(event).strip()
        ]
        if not trigger_list:
            trigger_list = ["PERIODIC_PULSE"]

        payload = self._build_pulse_anchor_payload(symbol, records, trigger_list, df, state_obj)
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        return (
            "[MARKET_PULSE_CONTEXT_V2]\n"
            "SOURCE=PAYLOAD_JSON_ONLY\n"
            "WINDOW_RULE=log_signal_normalize_window must contain latest 60 records\n"
            "STABILITY_RULE=unchanged anchors => unchanged sentiment/aci bias\n"
            f"PAYLOAD_JSON={payload_json}\n"
            "OUTPUT_CONTRACT={narrative:string,sentiment:BULLISH|BEARISH|NEUTRAL,aci:int,"
            "debate_log:{trend:string,liquidity:string,skeptic:string}}"
        )

    def _collect_pulse_records(self, state: Any, limit: int = 60) -> List[Dict[str, Any]]:
        source = getattr(state, "log_signal_normalize", None)
        if not isinstance(source, list) or not source:
            source = getattr(state, "signal_history_normalized", [])

        records: List[Dict[str, Any]] = []
        for raw in source:
            if not isinstance(raw, dict):
                continue

            try:
                t = int(raw.get("t"))
            except (TypeError, ValueError):
                continue

            record: Dict[str, Any] = {"t": t}
            price = self._extract_record_price(raw)
            if price is not None:
                record["price"] = price

            signals_raw = raw.get("signals") if isinstance(raw.get("signals"), dict) else {}
            events_raw = signals_raw.get("events") if isinstance(signals_raw.get("events"), list) else []

            compact_signals = {
                "htf_trend": str((signals_raw.get("htf_trend") or {}).get("value") or (signals_raw.get("htf_trend") or {}).get("trend") or "UNKNOWN").upper(),
                "market_session": str((signals_raw.get("market_session") or {}).get("value") or "UNKNOWN").upper(),
                "zigzag_kind": str((signals_raw.get("zigzag") or {}).get("kind") or "UNKNOWN").upper(),
                "events": self._compact_signal_events(events_raw),
            }
            record["signals"] = compact_signals
            records.append(record)

        records.sort(key=lambda item: int(item.get("t", 0)))
        if limit > 0:
            records = records[-limit:]
        return records

    def _extract_record_price(self, record: Dict[str, Any]) -> Optional[float]:
        price_raw = record.get("price")
        if price_raw is not None:
            try:
                return float(price_raw)
            except (TypeError, ValueError):
                pass

        for key in ("c", "close", "o", "h", "l"):
            value = record.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue

        signals = record.get("signals") if isinstance(record.get("signals"), dict) else {}
        for key in ("zigzag", "htf_trend", "market_session"):
            candidate = signals.get(key)
            if not isinstance(candidate, dict):
                continue
            for value_key in ("price", "close", "value"):
                value = candidate.get(value_key)
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue

        events = signals.get("events") if isinstance(signals.get("events"), list) else []
        for event in events:
            if not isinstance(event, dict):
                continue
            for value_key in ("price", "close", "value"):
                value = event.get(value_key)
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue

        return None

    def _compact_signal_events(self, events: List[Dict[str, Any]], max_events_per_record: int = 4) -> List[Dict[str, Any]]:
        compact_events: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            tag = str(event.get("tag") or "").strip().lower()
            if not tag:
                continue
            compact_event: Dict[str, Any] = {"tag": tag}
            direction = str(event.get("direction") or "").strip().upper()
            if direction:
                compact_event["direction"] = direction
            event_price = self._extract_record_price(event)
            if event_price is not None:
                compact_event["price"] = event_price
            compact_events.append(compact_event)
            if len(compact_events) >= max_events_per_record:
                break
        return compact_events

    def _build_pulse_anchor_payload(
        self,
        symbol: str,
        records: List[Dict[str, Any]],
        trigger_events: List[str],
        df: 'pd.DataFrame',
        state: Any,
    ) -> Dict[str, Any]:
        event_counter: Counter = Counter()
        swing_counter: Counter = Counter()
        recent_events: List[Dict[str, Any]] = []

        latest_htf_trend = "UNKNOWN"
        latest_market_session = "UNKNOWN"
        latest_zigzag_kind = "UNKNOWN"
        price_series: List[float] = []

        for rec in records:
            price = self._extract_record_price(rec)
            if price is not None:
                price_series.append(float(price))

            signals = rec.get("signals") if isinstance(rec.get("signals"), dict) else {}
            latest_htf_trend = str(signals.get("htf_trend") or latest_htf_trend).upper()
            latest_market_session = str(signals.get("market_session") or latest_market_session).upper()
            latest_zigzag_kind = str(signals.get("zigzag_kind") or latest_zigzag_kind).upper()

            events = signals.get("events") if isinstance(signals.get("events"), list) else []
            for event in events:
                if not isinstance(event, dict):
                    continue
                tag = str(event.get("tag") or "").lower()
                if not tag:
                    continue

                event_counter[tag] += 1
                if tag in {"hh", "hl", "lh", "ll"}:
                    swing_counter[tag] += 1

                recent_events.append(
                    {
                        "t": int(rec.get("t", 0)),
                        "tag": tag,
                        "direction": str(event.get("direction") or "").upper(),
                        "price": event.get("price") if event.get("price") is not None else price,
                    }
                )

        if not price_series and df is not None and not df.empty:
            try:
                price_series = [float(value) for value in df["c"].tail(60).tolist()]
            except Exception:
                price_series = []

        first_t = int(records[0].get("t", 0)) if records else 0
        last_t = int(records[-1].get("t", 0)) if records else 0
        first_price = price_series[0] if price_series else self._extract_record_price(getattr(state, "last_candle", {}) or {})
        last_price = price_series[-1] if price_series else first_price

        net_change = None
        net_change_pct = None
        if first_price is not None and last_price is not None:
            net_change = round(last_price - first_price, 6)
            if abs(first_price) > 1e-9:
                net_change_pct = round((net_change / first_price) * 100.0, 4)

        dominant_tags = [
            {"tag": tag, "count": count}
            for tag, count in sorted(event_counter.items(), key=lambda item: (-item[1], item[0]))[:6]
        ]

        return {
            "schema": "pulse_context_v2",
            "symbol": symbol,
            "trigger_events": trigger_events,
            "window": {
                "record_count": len(records),
                "first_t": first_t,
                "last_t": last_t,
                "first_price": first_price,
                "last_price": last_price,
                "high_price": max(price_series) if price_series else None,
                "low_price": min(price_series) if price_series else None,
                "net_change": net_change,
                "net_change_pct": net_change_pct,
            },
            "log_signal_normalize_window": records,
            "bias_anchors": {
                "latest_htf_trend": latest_htf_trend,
                "latest_market_session": latest_market_session,
                "latest_zigzag_kind": latest_zigzag_kind,
                "swing_balance": {
                    "hh": int(swing_counter.get("hh", 0)),
                    "hl": int(swing_counter.get("hl", 0)),
                    "lh": int(swing_counter.get("lh", 0)),
                    "ll": int(swing_counter.get("ll", 0)),
                },
                "choch_count": int(event_counter.get("choch", 0) + event_counter.get("choch_up", 0) + event_counter.get("choch_down", 0)),
                "bos_count": int(event_counter.get("bos", 0) + event_counter.get("bos_up", 0) + event_counter.get("bos_down", 0)),
                "dominant_event_tags": dominant_tags,
            },
            "recent_events": recent_events[-12:],
        }

    def _synthesize_structure(self, state: Any) -> str:
        """Summarizes HH, HL, LH, LL and Choch/Bos history with institutional context."""
        swings = state.swing_points[-10:] if hasattr(state, 'swing_points') else []
        if not swings:
            return "No clear structural points detected. Market may be in range or consolidating."

        summary = []
        # Describe recent major swings to establish trend
        major_swings = [s for s in swings if s.get('type', '') in ('HH', 'LL', 'HL', 'LH')]
        for s in major_swings[-5:]:
            summary.append(f"- {s['type']} formed at {s['price']:.5f} (Time: {s['t']})")

        recent_ch: List[Dict[str, Any]] = []

        # Legacy/raw history path
        raw_history = getattr(state, 'signal_history', []) or []
        for h in raw_history[-40:]:
            if not isinstance(h, dict):
                continue
            tag = str(h.get('tag', ''))
            if not tag:
                continue
            tag_upper = tag.upper()
            if 'CHOCH' in tag_upper or 'BOS' in tag_upper:
                recent_ch.append(
                    {
                        'tag': tag,
                        't': h.get('t'),
                        'explain': h.get('explain') or (h.get('data') or {}).get('explain') if isinstance(h.get('data'), dict) else h.get('explain'),
                    }
                )

        # Normalized history path (grouped by timestamp)
        normalized_history = getattr(state, 'signal_history_normalized', []) or []
        for group in normalized_history[:20]:
            if not isinstance(group, dict):
                continue

            signals = group.get('signals') if isinstance(group.get('signals'), dict) else {}

            # Backward-compat path
            structure_tag = signals.get('structure')
            if isinstance(structure_tag, str):
                structure_upper = structure_tag.upper()
                if 'CHOCH' in structure_upper or 'BOS' in structure_upper:
                    recent_ch.append(
                        {
                            'tag': structure_tag,
                            't': group.get('t'),
                            'explain': None,
                        }
                    )

            # New normalized contract path
            events = signals.get('events') if isinstance(signals.get('events'), list) else []
            for event in events:
                if not isinstance(event, dict):
                    continue
                event_tag = str(event.get('tag', ''))
                if not event_tag:
                    continue
                event_upper = event_tag.upper()
                if 'CHOCH' in event_upper or 'BOS' in event_upper:
                    recent_ch.append(
                        {
                            'tag': event_tag,
                            't': group.get('t'),
                            'explain': event.get('explain'),
                        }
                    )

        if recent_ch:
            def _safe_t(item: Dict[str, Any]) -> int:
                try:
                    return int(item.get('t') or 0)
                except Exception:
                    return 0

            last_ch = sorted(recent_ch, key=_safe_t)[-1]

            if last_ch.get('explain'):
                ch_msg = (
                    f"CRITICAL: Recent market shift pulse: {last_ch['explain']} "
                    f"(tag: {last_ch['tag']}) detected at {last_ch.get('t')}"
                )
            else:
                ch_msg = f"CRITICAL: Recent market shift pulse: {last_ch['tag']} detected at {last_ch.get('t')}"

            # Enrich with Actor information if available
            actor_book = getattr(state, 'candle_actors', {}) if hasattr(state, 'candle_actors') else {}
            actor = actor_book.get(str(last_ch.get('t'))) if isinstance(actor_book, dict) else None
            if actor and actor.get('type') == 'CHOCH_BREAKOUT':
                candle = actor.get('candle') or {}
                ch_msg += (
                    f" (Breaking Candle: O:{candle.get('o')}, H:{candle.get('h')}, "
                    f"L:{candle.get('l')}, C:{candle.get('c')})"
                )

            summary.append(ch_msg)

        return "\n".join(summary)

    def _calculate_positioning(self, df: 'pd.DataFrame', state: Any) -> str:
        """Calculates Fibonacci retracements and distance to main zones."""
        if df.empty: return "Insufficient data for positioning."
        
        high = df['h'].max()
        low = df['l'].min()
        curr = df.iloc[-1]['c']
        
        # Simple Fib 0.5 (Mean Reversion)
        equilibrium = (high + low) / 2
        pos = "ABOVE" if curr > equilibrium else "BELOW"
        
        return f"- Range High/Low: {high:.2f} / {low:.2f}\n- Position relative to 50% Equilibrium: {pos}"

    def _describe_logic(self, trigger: Dict[str, Any]) -> str:
        """Translates the signal sequence into readable text."""
        try:
            progress = json.loads(trigger.get('progress', '{}'))
            sequence = progress.get('sequence', [])
            steps = [f"Step {i+1}: {s['tag']} confirmed at {s['time']}" for i, s in enumerate(sequence) if s['status'] == 'matched']
            return "\n".join(steps) if steps else "Triggered by standalone condition."
        except Exception:
            return f"Triggered by strategy: {trigger.get('strategy', 'Unknown')}"

    def _map_liquidity(self, state: Any, trigger: Dict[str, Any]) -> str:
        """Identifies unmitigated OBs and potential equal highs/lows nearby."""
        fresh_obs = [ob for ob in state.obs if not ob.get('mitigated')][-3:]
        eq_highs = [] # Placeholder for logic to detect EQH
        
        lines = []
        if fresh_obs:
            lines.append("Recent Unmitigated Order Blocks:")
            for ob in fresh_obs:
                qual_str = f" [Quality: {ob.get('quality', 'N/A')}]" if 'quality' in ob else ""
                lines.append(f"- {ob['ob_type']} Zone: {ob['bottom']} - {ob['top']}{qual_str}")
        else:
            lines.append("No significant unmitigated supply/demand zones nearby.")
            
        # Add Recent Interaction Actors
        recent_actors = sorted([a for a in state.candle_actors.values() if a['type'] == 'OB_TOUCH'], 
                               key=lambda x: x.get('t', 0), reverse=True)[:3]
        if recent_actors:
            lines.append("\nRecent OB Interactions (Live Price Action):")
            for actor in recent_actors:
                res = "REJECTION" if actor.get('rejection_quality') == 'HIGH' else "TOUCH"
                qual = f" ({res} - Wicking strength high)" if res == "REJECTION" else ""
                lines.append(f"- {actor['ob_type']} OB at {actor['ob_start']} was {res}ed{qual}. Candle Wick Penetration.")

        return "\n".join(lines)

    def _extract_metrics(self, df: 'pd.DataFrame') -> str:
        """Calculates volume intensity and volatility."""
        if len(df) < 5: return "Low metric precision."
        
        avg_vol = df['v'].tail(20).mean()
        last_vol = df.iloc[-1]['v']
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
        
        return f"- Volume Intensity: {vol_ratio:.1f}x average\n- Recent candle range: {df.iloc[-1]['h'] - df.iloc[-1]['l']:.5f}"

class AIValidator:
    """Orchestrates the full AI Audit flow: Context -> Debate -> Decision."""
    
    def __init__(self, base_url: str = None):
        self.builder = ContextBuilder()
        llm_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
        self.brain = AIBrainClient(base_url=llm_url)
        
        # Initialize Algorithmic Orchestrator (Phase 6)
        gates = [
            NewsGate(halt_window_mins=15)
        ]
        judges = [
            CHOCHJudge(weight=1.0),
            SweepJudge(weight=1.0),
            LiquidityJudge(weight=1.5),
            MomentumJudge(weight=0.8),
            MultiPatternJudge(weight=1.0)
        ]
        self.orchestrator = HybridOrchestrator(gates, judges, min_pass_score=0.6)

    def set_model(self, model_name: str):
        """Passes the model selection to the brain client."""
        self.brain.set_model(model_name)

    async def validate_trigger(self, symbol: str, df: 'pd.DataFrame', state_obj: Any, trigger: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the institutional audit on a technical trigger using Hybrid model (Algo + AI)."""
        try:
            start_time = time.perf_counter()
            
            # --- PHASE 6: ALGORITHMIC AUDIT FIRST ---
            # Prepare context for gates (POC: simple mocks for now)
            algo_context = {
                "estimated_rr": trigger.get('rr', 2.0), # Default to 2.0 if not provided
                "current_spread_pct": 0.01 
            }
            
            algo_res = self.orchestrator.audit(state_obj, trigger, algo_context)
            
            # If Algo REJECTS, we don't even waste vLLM tokens
            if algo_res['decision'] == "REJECT":
                logger.info(f"[t={trigger.get('t')}] [{symbol}] [validate_trigger] 1... Algo REJECTED setup: {algo_res['reason']}")
                return {
                    "aci": algo_res['aci'],
                    "decision": "REJECTED",
                    "key_insight": f"Algorithmic Reject: {algo_res['reason']}",
                    "audit_source": "ALGO",
                    "algo_breakdown": algo_res['breakdown'],
                    "symbol": symbol,
                    "trigger_time": trigger.get('t'),
                    "timestamp": int(datetime.now().timestamp()),
                    "llm_latency_ms": 0
                }

            # --- AI NARRATIVE GENERATION (Only if Algo PASSED) ---
            # 1. Build Narrative Context
            context = self.builder.build_market_context(symbol, df, state_obj, trigger)
            
            # 2. Run AI Debate
            # Pass the algo score to the AI context to anchor its narrative
            enhanced_context = f"{context}\n\n[ALGO_AUDIT_RESULT: Score {algo_res['aci']}/100, Reason: {algo_res['reason']}]"
            
            audit_result = await self.brain.debate(enhanced_context)
            llm_latency = int((time.perf_counter() - start_time) * 1000)

            # 3. Enhance result with metadata
            audit_result['symbol'] = symbol
            audit_result['trigger_time'] = trigger.get('t')
            audit_result['timestamp'] = int(datetime.now().timestamp())
            audit_result['algo_score'] = algo_res['aci']
            audit_result['algo_breakdown'] = algo_res['breakdown']
            audit_result['llm_latency_ms'] = llm_latency
            audit_result['audit_source'] = "HYBRID"
            
            logger.info(f"[{symbol}] [validate_trigger] 2... Hybrid Audit Complete: ACI={audit_result.get('aci')}, Decision={audit_result.get('decision')} (Algo: {algo_res['aci']})")
            return audit_result
            
        except Exception as e:
            logger.error(f"[{symbol}] [validate_trigger] Error: Validation flow failed: {e}")
            return {
                "aci": 0,
                "decision": "REJECTED",
                "key_insight": f"System Error: {str(e)}",
                "error": True
            }

    async def analyze_market(self, symbol: str, df: 'pd.DataFrame', state_obj: Any) -> Dict[str, Any]:
        """Generates a periodic 'Market Pulse' analysis (Context -> Narrative)."""
        try:
            # 1. Build Narrative Context (Generic market pulse context)
            context = self.builder.build_pulse_context(symbol, df, state_obj)
            
            # 2. Run LLM Narrative Analysis
            start_time = time.perf_counter()
            analysis_result = await self.brain.generate_pulse(context)
            llm_latency = int((time.perf_counter() - start_time) * 1000)
            
            # 3. Finalize result
            analysis_result['symbol'] = symbol
            analysis_result['timestamp'] = int(datetime.now().timestamp())
            analysis_result['llm_latency_ms'] = llm_latency
            analysis_result['request_payload'] = {
                "system_prompt": self.brain.get_pulse_system_prompt(),
                "user_context": context,
                "model": self.brain.model,
                "temperature": 0.0,
            }
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"[{symbol}] [analyze_market] Error: Market analysis failed: {e}")
            return {
                "aci": 50,
                "sentiment": "NEUTRAL",
                "narrative": f"Analysis offline: {str(e)}",
                "debate_log": {},
                "error": True
            }

from openai import AsyncOpenAI

class AIBrainClient:
    """Wrapper for LLM communication (Step 2 Integration: vLLM / DeepSeek-R1)."""
    
    def __init__(self, api_key: str = "none", base_url: str = "http://localhost:8000/v1"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        # Default fallback
        self.model = os.getenv("LLM_MODEL", "meta-llama/Llama-3.2-3B-Instruct")

    def set_model(self, model_name: str):
        """Update the active model dynamically."""
        self.model = model_name
        logger.info(f"[GLOBAL] [set_model] 🔄 AI Brain active model updated to: {self.model}")

    async def debate(self, context: str) -> Dict[str, Any]:
        """Sends context to DeepSeek-R1 for multi-agent reasoning using Internal Monologue."""
        logger.info("[GLOBAL] [debate] 1... AI Debate starting...")
        
        system_prompt = """
You are the Aureus Institutional Trading Brain. Your task is to perform a rigorous "Double-Lock" audit on a technical trade signal.
Use an internal monologue to debate the trade from 3 specialized perspectives. 

CRITICAL: Your analysis MUST be strictly deterministic and based on the provided technical anchors (HH/LL, OB, FVG). If the price has not moved significantly since the last analysis, your ACI and verdict should remain stable.

1. THE TREND SPECIALIST: Analyze market geometry, structure (HH/LL), and multi-timeframe alignment.
2. THE LIQUIDITY SCOUT: Identify if this is institutional participation or a retail trap. Look for sweeps vs. fakeouts.
3. THE ASSASSIN (SKEPTIC): This is your most critical role. You MUST find every reason why this trade will FAIL.

Finally, act as THE JUDGE to synthesize all arguments and provide:
- ACI (Aureus Confidence Index): 0 to 100.
- Decision: ACTIVE (if ACI >= 80), REDUCED_RISK (70-79), or REJECTED (< 70).
- Key Insight: A one-sentence summary of the final verdict.

Format your response as a valid JSON object:
{
  "aci": int,
  "decision": "ACTIVE" | "REDUCED_RISK" | "REJECTED",
  "key_insight": "...",
  "debate_log": {
    "trend": "PLAIN TEXT ONLY - 1 sentence structure overview",
    "liquidity": "PLAIN TEXT ONLY - 1 sentence liquidity/trap assessment",
    "assassin": "PLAIN TEXT ONLY - 1 sentence counter-argument",
    "judgement": "PLAIN TEXT ONLY - 1 sentence synthetic verdict"
  }
}
CRITICAL: Do NOT nest objects inside these keys. Use flat strings only.
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Force deterministic reasoning
                timeout=60.0
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            result['raw_response'] = result_text # Capture raw for transparency
            
            # Capture DeepSeek/vLLM reasoning (Internal Monologue) if present
            reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
            if reasoning:
                if 'debate_log' not in result: result['debate_log'] = {}
                result['debate_log']['monologue'] = reasoning
            
            return result
            
        except Exception as e:
            logger.error(f"[GLOBAL] [debate] Error: AI Brain Error: {e}")
            return {
                "aci": 0,
                "decision": "REJECTED",
                "key_insight": f"AI Engine Offline: {str(e)}"
            }

    def _coerce_debate_text(self, value: Any) -> str:
        if isinstance(value, str):
            text = value.strip()
            return text if text else "No anchor-specific note."
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, sort_keys=True)
            except Exception:
                return str(value)
        if value is None:
            return "No anchor-specific note."
        return str(value)

    def _normalize_pulse_contract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        narrative_raw = payload.get("narrative")
        narrative = str(narrative_raw).strip() if narrative_raw is not None else ""
        if not narrative:
            narrative = "Anchors are mixed; maintain neutral institutional posture until clearer structure confirms bias."

        sentiment = str(payload.get("sentiment") or "NEUTRAL").upper().strip()
        if sentiment not in {"BULLISH", "BEARISH", "NEUTRAL"}:
            sentiment = "NEUTRAL"

        aci_raw = payload.get("aci", 50)
        try:
            aci = int(float(aci_raw))
        except (TypeError, ValueError):
            aci = 50
        aci = max(0, min(100, aci))

        debate_input = payload.get("debate_log")
        if isinstance(debate_input, dict):
            trend = self._coerce_debate_text(debate_input.get("trend"))
            liquidity = self._coerce_debate_text(debate_input.get("liquidity"))
            skeptic = self._coerce_debate_text(debate_input.get("skeptic"))
        elif isinstance(debate_input, str):
            text = debate_input.strip() or "No anchor-specific note."
            trend = text
            liquidity = text
            skeptic = text
        else:
            trend = "No anchor-specific note."
            liquidity = "No anchor-specific note."
            skeptic = "No anchor-specific note."

        return {
            "narrative": narrative,
            "sentiment": sentiment,
            "aci": aci,
            "debate_log": {
                "trend": trend,
                "liquidity": liquidity,
                "skeptic": skeptic,
            },
        }

    def _fallback_pulse_contract(self, reason: str) -> Dict[str, Any]:
        note = f"Pulse fallback activated: {reason}"
        return {
            "narrative": "Anchors unavailable from model output; holding neutral institutional stance.",
            "sentiment": "NEUTRAL",
            "aci": 50,
            "debate_log": {
                "trend": note,
                "liquidity": note,
                "skeptic": note,
            },
        }

    def get_pulse_system_prompt(self) -> str:
        return """
You are the Aureus Institutional Pulse Engine.
Use only PAYLOAD_JSON from user message.

POLICY:
1) Derive bias only from anchors in PAYLOAD_JSON.
2) Deterministic output: when anchors are effectively unchanged, keep sentiment/aci stable.
3) No invention: no macro/news/external assumptions.
4) Keep response compact: avoid repetition and filler.

ANALYSIS ORDER:
A) Market Context: latest_htf_trend + window net_change + session tone.
B) Structure Evidence: choch_count, bos_count, swing_balance, dominant_event_tags, recent_events.
C) Actionable Outlook: base-case continuation/fade and one invalidation clue from anchors.

OUTPUT:
- JSON object with exact keys: narrative, sentiment, aci, debate_log
- sentiment in {BULLISH, BEARISH, NEUTRAL}
- aci is int 0..100
- debate_log has flat string keys: trend, liquidity, skeptic
- narrative must be 3 concise parts in this exact order:
  1) "Context: ..."
  2) "Structure: ..."
  3) "Outlook: ..."
- narrative length target: 60-110 words total
- each debate_log field: 1 concise sentence, anchor-backed
""".strip()

    async def generate_pulse(self, context: str) -> Dict[str, Any]:
        """Generates deterministic market pulse narrative from technical anchors."""
        system_prompt = self.get_pulse_system_prompt()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=45.0
            )
            result_text = (response.choices[0].message.content or "").strip()
            parsed = json.loads(result_text)
            if not isinstance(parsed, dict):
                return self._fallback_pulse_contract("model response is not a JSON object")
            return self._normalize_pulse_contract(parsed)
        except Exception as e:
            logger.error(f"[GLOBAL] [generate_pulse] Error: Pulse Brain Error: {e}")
            return self._fallback_pulse_contract(str(e))
