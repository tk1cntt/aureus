import os
import sys
import json
import time
from datetime import datetime, timedelta

def run_tests():
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "environment": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "tradingagents": "unknown"
        },
        "symbol_tests": {
            "XAUUSD": {"status": "fail", "decision": None, "reasoning_length": 0, "error": None},
            "BTCUSD": {"status": "fail", "decision": None, "reasoning_length": 0, "error": None}
        },
        "latency": {"avg_s": 0, "min_s": 0, "max_s": 0, "p95_s": 0, "per_call": []},
        "rate_limit": {"total_av_calls": 0, "throttle_429": 0, "max_burst": 0},
        "cost_estimate": {"llm_tokens_per_call": 0, "estimated_cost_usd_per_call": 0},
        "decision": "PAUSE_AND_PIVOT",
        "decision_reason": "Tests failed or did not complete"
    }

    # Test 1: Import check
    try:
        import tradingagents
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        results["environment"]["tradingagents"] = getattr(tradingagents, "__version__", "installed")
        print(f"✅ TradingAgents version {results['environment']['tradingagents']} imported successfully.")
    except ImportError as e:
        results["decision_reason"] = f"ImportError: {str(e)}"
        _write_results(results)
        return

    # Check env
    alpha_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not alpha_key or not openai_key:
        print("⚠️ Missing API keys. Ensure OPENAI_API_KEY and ALPHA_VANTAGE_API_KEY are set.")
        results["decision_reason"] = "Missing API keys"
        _write_results(results)
        return

    # Configure TA
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openai"
    llm_model = os.getenv("TA_LLM_MODEL", "cx/gpt-5.4")
    config["deep_think_llm"] = llm_model
    config["quick_think_llm"] = llm_model
    # Note: OPENAI_API_BASE should be set in environment (.env)

    try:
        ta = TradingAgentsGraph(debug=True, config=config)
    except Exception as e:
        results["decision_reason"] = f"Init error: {str(e)}"
        _write_results(results)
        return

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    latencies = []

    # Test 2: XAUUSD
    print("\ntesting XAUUSD...")
    try:
        start_time = time.time()
        _, decision_xau = ta.propagate("XAUUSD", yesterday)
        elapsed = time.time() - start_time
        latencies.append(elapsed)
        
        signal = str(decision_xau).lower()
        has_signal = any(s in signal for s in ["buy", "sell", "hold"])
        
        results["symbol_tests"]["XAUUSD"] = {
            "status": "pass" if has_signal else "fail",
            "decision": signal[:50] + "..." if has_signal else "unknown",
            "reasoning_length": len(signal),
            "error": "No clear buy/sell/hold signal" if not has_signal else None
        }
    except Exception as e:
        results["symbol_tests"]["XAUUSD"]["error"] = str(e)
        print(f"❌ XAUUSD error: {e}")

    # Test 3: BTCUSD
    print("\ntesting BTCUSD...")
    try:
        start_time = time.time()
        _, decision_btc = ta.propagate("BTCUSD", yesterday)
        elapsed = time.time() - start_time
        latencies.append(elapsed)

        signal = str(decision_btc).lower()
        has_signal = any(s in signal for s in ["buy", "sell", "hold"])

        results["symbol_tests"]["BTCUSD"] = {
            "status": "pass" if has_signal else "fail",
            "decision": signal[:50] + "..." if has_signal else "unknown",
            "reasoning_length": len(signal),
            "error": "No clear buy/sell/hold signal" if not has_signal else None
        }
    except Exception as e:
        results["symbol_tests"]["BTCUSD"]["error"] = str(e)
        print(f"❌ BTCUSD error: {e}")

    # Calculate Latency
    if latencies:
        results["latency"]["per_call"] = latencies
        results["latency"]["avg_s"] = sum(latencies) / len(latencies)
        results["latency"]["min_s"] = min(latencies)
        results["latency"]["max_s"] = max(latencies)
        latencies_sorted = sorted(latencies)
        idx_95 = int(len(latencies_sorted) * 0.95)
        results["latency"]["p95_s"] = latencies_sorted[idx_95] if latencies_sorted else 0

    # Decision Logic
    xau_pass = results["symbol_tests"]["XAUUSD"]["status"] == "pass"
    btc_pass = results["symbol_tests"]["BTCUSD"]["status"] == "pass"
    latency_pass = results["latency"]["avg_s"] <= 30 and results["latency"]["p95_s"] <= 60
    
    if xau_pass and btc_pass and latency_pass:
        results["decision"] = "PROCEED_TO_PHASE_22"
        results["decision_reason"] = "All gates passed."
    else:
        results["decision"] = "PAUSE_AND_PIVOT"
        reasons = []
        if not xau_pass: reasons.append("XAUUSD failed")
        if not btc_pass: reasons.append("BTCUSD failed")
        if not latency_pass: reasons.append(f"Latency failed (avg={results['latency']['avg_s']:.1f}s)")
        results["decision_reason"] = " | ".join(reasons)

    print(f"\nFinal Decision: {results['decision']} ({results['decision_reason']})")
    
    # Write output
    _write_results(results)

def _write_results(results):
    os.makedirs("/app/output", exist_ok=True)
    with open("/app/output/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results written to /app/output/results.json")

if __name__ == "__main__":
    run_tests()
