import logging
from engine.logging_common import get_logger
import json
import os
import time
from datetime import datetime
try:
    import pandas as pd
except ImportError:
    pd = None
from typing import Dict, Any, List

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
        """Context for periodic analysis (General state instead of trade logic)."""
        structure = self._synthesize_structure(state_obj)
        positioning = self._calculate_positioning(df, state_obj)
        liquidity = self._map_liquidity(state_obj, {})
        metrics = self._extract_metrics(df)
        
        trigger_str = ", ".join(trigger_events) if trigger_events else "PERIODIC_PULSE"
        
        context = f"""
[MARKET PULSE: {symbol}] | TRIGGER: [{trigger_str}]
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Last Price: {state_obj.last_candle['c']}

STRUCTURE:
{structure}

LEVELS:
{positioning}

LIQUIDITY:
{liquidity}

METRICS:
{metrics}

TASK: Provide an institutional narrative of the current market state, specifically addressing the TRIGGER event(s) if present. 
Be concise. Identify the dominant bias (BULLISH/BEARISH/NEUTRAL).
"""
        return context.strip()


    def _synthesize_structure(self, state: Any) -> str:
        """Summarizes HH, HL, LH, LL and Choch/Bos history with institutional context."""
        swings = state.swing_points[-10:] if hasattr(state, 'swing_points') else []
        if not swings: return "No clear structural points detected. Market may be in range or consolidating."
        
        summary = []
        # Describe the last 3 major swings to establish trend
        major_swings = [s for s in swings if s.get('type', '') in ('HH', 'LL', 'HL', 'LH')]
        for s in major_swings[-5:]:
            summary.append(f"- {s['type']} formed at {s['price']:.5f} (Time: {s['t']})")
        
        # Check for recent Break of Structure or Change of Character
        history = state.signal_history[-20:]
        recent_ch = [h for h in history if 'CHOCH' in h['tag'] or 'BOS' in h['tag']]
        if recent_ch:
            if "explain" in last_ch and last_ch.get("explain"):
                ch_msg = f"CRITICAL: Recent market shift pulse: {last_ch['explain']} (tag: {last_ch['tag']}) detected at {last_ch['t']}"
            else:
                ch_msg = f"CRITICAL: Recent market shift pulse: {last_ch['tag']} detected at {last_ch['t']}"
            
            # Enrich with Actor information if available
            actor = state.candle_actors.get(str(last_ch['t']))
            if actor and actor.get('type') == 'CHOCH_BREAKOUT':
                candle = actor['candle']
                ch_msg += f" (Breaking Candle: O:{candle['o']}, H:{candle['h']}, L:{candle['l']}, C:{candle['c']})"
            
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
            analysis_result['request_payload'] = context
            
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

    async def generate_pulse(self, context: str) -> Dict[str, Any]:
        """Generates a general market pulse narrative."""
        system_prompt = """
You are the Aureus Market Analyst. Your task is to provide a high-frequency institutional narrative.
Analyze the provided technical context and identify the dominant market bias.

CRITICAL: Stability is key. Base your narrative on the provided Technical Anchors. If the anchors haven't changed, your analysis should remain consistent with previous iterations. Avoid introducing "creative" new perspectives unless there is a clear structural breakout.

1. NARRATIVE: A concise (2-3 sentences) description of what big money is doing.
2. SENTIMENT: BULLISH, BEARISH, or NEUTRAL.
3. ACI: (Aureus Confidence Index) 0-100 indicating the strength of the current bias.
4. DEBATE_LOG: Brief notes from "Trend", "Liquidity", and "Skeptic" perspectives.

Format as JSON:
{
  "narrative": "...",
  "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
  "aci": int,
  "debate_log": { 
    "trend": "PLAIN TEXT ONLY - 1 sentence", 
    "liquidity": "PLAIN TEXT ONLY - 1 sentence", 
    "skeptic": "PLAIN TEXT ONLY - 1 sentence" 
  }
}
CRITICAL: Do NOT nest objects inside these keys. Use flat strings only.
"""
        try:
            start_time = time.perf_counter()
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Maintain consistency
                timeout=45.0
            )
            llm_latency = int((time.perf_counter() - start_time) * 1000)
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            result['raw_response'] = result_text
            
            # Capture DeepSeek/vLLM reasoning (Internal Monologue) if present
            reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
            if reasoning:
                if 'debate_log' not in result: result['debate_log'] = {}
                result['debate_log']['monologue'] = reasoning
            
            # Extract usage
            usage = getattr(response, 'usage', None)
            if usage:
                result['prompt_tokens'] = usage.prompt_tokens
                result['completion_tokens'] = usage.completion_tokens
            
            return result
        except Exception as e:
            logger.error(f"[GLOBAL] [generate_pulse] Error: Pulse Brain Error: {e}")
            return {
                "narrative": "Unable to generate narrative.",
                "sentiment": "NEUTRAL",
                "aci": 50,
                "debate_log": {"error": str(e)}
            }
