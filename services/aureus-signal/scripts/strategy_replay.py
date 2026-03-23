"""Strategy Replay CLI — standalone replay tool for strategy quality assurance.

Replays historical candles through the full signal+strategy pipeline and
persists Tier 2 baseline metrics to TimescaleDB.

Modes:
  Single:     python strategy_replay.py --symbol XAUUSD --strategy TREND_CONT
  Batch:      python strategy_replay.py --symbol XAUUSD
  Full matrix: python strategy_replay.py

Usage:
    cd services/aureus-signal
    python scripts/strategy_replay.py --symbol XAUUSD --strategy TREND_CONT
    python scripts/strategy_replay.py --no-persist   # skip DB write
    python scripts/strategy_replay.py --skip-determinism  # faster run
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List

import asyncpg
import pandas as pd
from dotenv import load_dotenv

# Add parent directory so engine imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.state import SymbolState
from engine.signal_factory import create_signal_set
from engine.live_engine import execute_signals_for_candle
from engine.strategies.registry import StrategyRegistry
from engine.strategies.template import TemplateStrategy

load_dotenv()

BARS_LIMIT = 2000


def load_symbol_config(symbol: str) -> dict:
    """Load symbol-specific config from symbols.json."""
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "symbols.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            return json.load(f).get(symbol, {})
    return {}


async def fetch_candles(pool, symbol: str, limit: int = BARS_LIMIT) -> pd.DataFrame:
    """Fetch candle data from aureus_candles table."""
    rows = await pool.fetch(
        """
        SELECT
            EXTRACT(EPOCH FROM time)::BIGINT AS t,
            open AS o, high AS h, low AS l, close AS c, volume::INT AS v
        FROM aureus_candles
        WHERE symbol = $1 AND timeframe = 'M1'
        ORDER BY time DESC
        LIMIT $2
        """,
        symbol,
        limit,
    )
    rows = list(reversed(rows))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


async def fetch_strategy_configs(pool) -> List[Dict[str, Any]]:
    """Load all strategy configs from aureus_strategy_templates."""
    rows = await pool.fetch(
        "SELECT id, name, config, min_score FROM aureus_strategy_templates"
    )
    configs = []
    for r in rows:
        config = json.loads(r["config"]) if isinstance(r["config"], str) else r["config"]
        config["id"] = r["id"]
        config["name"] = r["name"]
        config["min_score_threshold"] = r["min_score"]
        configs.append(config)
    return configs


def run_replay(
    df: pd.DataFrame,
    strategy_config: dict,
    symbol: str,
    symbol_config: dict,
    window_size: int = BARS_LIMIT,
) -> dict:
    """Run single strategy replay on candle data. Returns Tier 2 metrics."""
    import copy

    signals = create_signal_set(symbol, symbol_config)
    state = SymbolState(symbol)
    registry = StrategyRegistry()
    registry.register(TemplateStrategy(copy.deepcopy(strategy_config)))

    accepted = []
    all_rejections = []

    for i in range(len(df)):
        window = df.iloc[max(0, i - window_size + 1) : i + 1]
        if len(window) < 5:
            continue

        state.transient_signals = {}
        execute_signals_for_candle(signals, window, state, symbol, redis_client=None)

        acc = registry.evaluate_all(window, signals, state)
        rej = registry.get_rejections(clear=True)

        accepted.extend(acc)
        all_rejections.extend(rej)

    # Compute Tier 2 metrics
    trigger_count = len(accepted)
    bar_count = len(df)
    trigger_rate = trigger_count / bar_count if bar_count > 0 else 0.0
    reject_count = len(all_rejections)

    # Reject reason breakdown
    reject_reasons = dict(Counter(r["reason_code"] for r in all_rejections))

    # Score distribution (from accepted intents)
    scores = []
    for a in accepted:
        # Score may be in the intent or directly on the accepted record
        intent = a.get("intent", {})
        score = intent.get("score") if isinstance(intent, dict) else None
        if score is not None:
            scores.append(float(score))

    score_min = min(scores) if scores else None
    score_max = max(scores) if scores else None
    score_avg = round(sum(scores) / len(scores), 4) if scores else None

    # Signal contribution: count of accepted triggers per strategy tag
    signal_tags: Counter = Counter()
    for a in accepted:
        strat_name = a.get("strategy", "UNKNOWN")
        signal_tags[strat_name] += 1
    signal_contribution = dict(signal_tags)

    # Session distribution: approximate from rejection details
    session_dist: Counter = Counter()
    for r in all_rejections:
        details = r.get("details", {})
        if isinstance(details, dict):
            failed_rules = details.get("failed_rules", [])
            for rule in failed_rules:
                if isinstance(rule, str) and "session" in rule.lower():
                    session_dist[rule] += 1
    session_distribution = dict(session_dist)

    # Context filter pass/fail
    context_passed = trigger_count  # accepted means context passed
    context_failed = sum(
        1 for r in all_rejections if r.get("reason_code") == "CONTEXT_FILTER_FAILED"
    )
    context_filter_stats = {
        "passed": context_passed,
        "failed": context_failed,
    }

    return {
        "bar_count": bar_count,
        "trigger_count": trigger_count,
        "trigger_rate": round(trigger_rate, 6),
        "reject_count": reject_count,
        "reject_reasons": reject_reasons,
        "score_min": score_min,
        "score_max": score_max,
        "score_avg": score_avg,
        "signal_contribution": signal_contribution,
        "session_distribution": session_distribution,
        "context_filter_stats": context_filter_stats,
    }


def check_determinism(
    df: pd.DataFrame,
    strategy_config: dict,
    symbol: str,
    symbol_config: dict,
) -> bool:
    """Run replay twice, compare results for determinism."""
    r1 = run_replay(df, strategy_config, symbol, symbol_config)
    r2 = run_replay(df, strategy_config, symbol, symbol_config)
    return (
        r1["trigger_count"] == r2["trigger_count"]
        and r1["reject_count"] == r2["reject_count"]
        and r1["score_min"] == r2["score_min"]
        and r1["score_max"] == r2["score_max"]
    )


async def persist_result(
    pool,
    symbol: str,
    strategy_name: str,
    strategy_config: dict,
    metrics: dict,
    deterministic: bool,
):
    """Write replay results to aureus_strategy_replay_results."""
    await pool.execute(
        """
        INSERT INTO aureus_strategy_replay_results
            (symbol, strategy_name, strategy_config, bar_count,
             trigger_count, trigger_rate, reject_count, reject_reasons,
             score_min, score_max, score_avg,
             signal_contribution, session_distribution, context_filter_stats,
             deterministic)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        """,
        symbol,
        strategy_name,
        json.dumps(strategy_config),
        metrics["bar_count"],
        metrics["trigger_count"],
        metrics["trigger_rate"],
        metrics["reject_count"],
        json.dumps(metrics["reject_reasons"]),
        metrics["score_min"],
        metrics["score_max"],
        metrics["score_avg"],
        json.dumps(metrics["signal_contribution"]),
        json.dumps(metrics["session_distribution"]),
        json.dumps(metrics["context_filter_stats"]),
        deterministic,
    )


def print_summary(
    symbol: str, strategy_name: str, metrics: dict, deterministic: bool
):
    """Print Tier 2 baseline summary to console."""
    print(f"\n{'='*60}")
    print(f"  {symbol}  x  {strategy_name}")
    print(f"{'='*60}")
    print(f"  Bars:           {metrics['bar_count']}")
    print(
        f"  Triggers:       {metrics['trigger_count']} "
        f"({metrics['trigger_rate']*100:.2f}%)"
    )
    print(f"  Rejects:        {metrics['reject_count']}")
    print(
        f"  Score:          min={metrics['score_min']}  "
        f"max={metrics['score_max']}  avg={metrics['score_avg']}"
    )
    det_symbol = "Y" if deterministic else "X"
    print(f"  Deterministic:  {det_symbol}")
    if metrics["reject_reasons"]:
        print(f"  Reject reasons: {metrics['reject_reasons']}")
    if metrics["signal_contribution"]:
        print(f"  Signal contrib: {metrics['signal_contribution']}")
    if metrics["context_filter_stats"]:
        print(f"  Context stats:  {metrics['context_filter_stats']}")


async def main():
    parser = argparse.ArgumentParser(
        description="Strategy Replay - Quality Assurance Tool"
    )
    parser.add_argument("--symbol", type=str, help="Symbol to replay (e.g. XAUUSD)")
    parser.add_argument(
        "--strategy", type=str, help="Strategy name (e.g. TREND_CONT)"
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=BARS_LIMIT,
        help=f"Number of bars (default: {BARS_LIMIT})",
    )
    parser.add_argument(
        "--skip-determinism",
        action="store_true",
        help="Skip determinism check (faster)",
    )
    parser.add_argument(
        "--no-persist", action="store_true", help="Don't write results to DB"
    )
    args = parser.parse_args()

    db_dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://aureus:aureus_password@localhost:5433/aureus",
    )
    pool = await asyncpg.create_pool(db_dsn)

    # Ensure replay table exists
    sql_path = os.path.join(os.path.dirname(__file__), "create_replay_table.sql")
    if os.path.exists(sql_path):
        with open(sql_path) as f:
            await pool.execute(f.read())

    # Load strategy configs from DB
    all_configs = await fetch_strategy_configs(pool)
    if not all_configs:
        print("ERROR: No strategy configs found in aureus_strategy_templates")
        await pool.close()
        return

    # Determine symbols
    if args.symbol:
        symbols = [args.symbol]
    else:
        rows = await pool.fetch(
            "SELECT DISTINCT symbol FROM aureus_candles WHERE timeframe = 'M1'"
        )
        symbols = sorted(r["symbol"] for r in rows)

    # Filter strategies
    if args.strategy:
        configs = [c for c in all_configs if c["name"] == args.strategy]
        if not configs:
            available = [c["name"] for c in all_configs]
            print(f"ERROR: Strategy '{args.strategy}' not found. Available: {available}")
            await pool.close()
            return
    else:
        configs = all_configs

    print(f"\nStrategy Replay - {len(symbols)} symbol(s) x {len(configs)} strategy(ies)")
    print(f"{'_'*60}")

    for symbol in symbols:
        sym_cfg = load_symbol_config(symbol)
        df = await fetch_candles(pool, symbol, args.bars)
        if df.empty:
            print(f"\n  SKIP {symbol}: no candle data")
            continue

        for config in configs:
            strategy_name = config["name"]
            print(f"\n  Running {symbol} x {strategy_name} ({len(df)} bars)...", end="", flush=True)

            metrics = run_replay(df, config, symbol, sym_cfg)

            deterministic = True
            if not args.skip_determinism:
                deterministic = check_determinism(df, config, symbol, sym_cfg)

            print_summary(symbol, strategy_name, metrics, deterministic)

            if not args.no_persist:
                await persist_result(
                    pool, symbol, strategy_name, config, metrics, deterministic
                )
                print(f"  -> Persisted to aureus_strategy_replay_results")

    await pool.close()
    print(f"\n{'='*60}")
    print(f"  Replay complete.")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
