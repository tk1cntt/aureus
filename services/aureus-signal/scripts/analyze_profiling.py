"""Profiling Analyzer CLI - reads Redis profiling streams and produces bottleneck report.

Usage:
    cd services/aureus-signal
    python scripts/analyze_profiling.py
    python scripts/analyze_profiling.py --host localhost --port 6379
    python scripts/analyze_profiling.py --symbols XAUUSD,BTCUSD --json
    python scripts/analyze_profiling.py --log-file /path/to/engine.log

Reads timing data from `aureus:profiling:{symbol}` Redis streams written by
Phase 44.0 profiling instrumentation in live_engine.py.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

import redis

DEFAULT_SYMBOLS = [
    "XAUUSD", "BTCUSD", "ETHUSD", "USTEC",
    "USDJPY", "EURUSD", "GBPUSD", "AUDUSD",
]
NS_TO_MS = 1_000_000
PROFILING_STREAM = "aureus:profiling:{symbol}"


def percentile(sorted_data, p):
    """Linear-interpolation percentile on a pre-sorted list."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    k = (p / 100.0) * (n - 1)
    f = int(k)
    c = f + 1 if f + 1 < n else f
    d = k - f
    return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])


def read_profiling_data(redis_client, symbols):
    """Read all profiling entries from Redis streams. Returns {symbol: [entry_dict, ...]}"""
    all_data = {}
    for sym in symbols:
        stream_key = PROFILING_STREAM.format(symbol=sym)
        try:
            entries = redis_client.xrange(stream_key)
            if not entries:
                print(f"  WARNING: stream {stream_key} is empty (skipping)", file=sys.stderr)
                continue
            all_data[sym] = [entry_data for _, entry_data in entries]
        except redis.ResponseError:
            print(f"  WARNING: stream {stream_key} does not exist (skipping)", file=sys.stderr)
    return all_data


def compute_signal_stats(all_data):
    """Aggregate per-signal timing stats across all symbols."""
    values = defaultdict(list)  # signal_name -> [ms_values]
    for sym_entries in all_data.values():
        for entry in sym_entries:
            for key, raw_val in entry.items():
                if key in ("t",):
                    continue
                try:
                    ms = float(raw_val) / NS_TO_MS
                    values[key].append(ms)
                except (ValueError, TypeError):
                    continue

    stats = []
    for name, vals in values.items():
        vals.sort()
        count = len(vals)
        avg = sum(vals) / count if count else 0
        stats.append({
            "signal": name,
            "count": count,
            "avg_ms": round(avg, 4),
            "min_ms": round(vals[0], 4) if vals else 0,
            "max_ms": round(vals[-1], 4) if vals else 0,
            "p50_ms": round(percentile(vals, 50), 4),
            "p95_ms": round(percentile(vals, 95), 4),
            "p99_ms": round(percentile(vals, 99), 4),
            "total_cpu_ms": round(avg * count, 2),
        })
    stats.sort(key=lambda s: s["total_cpu_ms"], reverse=True)
    return stats


def compute_symbol_totals(all_data):
    """Compute per-symbol _total stats."""
    totals = []
    for sym, entries in sorted(all_data.items()):
        vals = []
        for entry in entries:
            raw = entry.get("_total")
            if raw:
                try:
                    vals.append(float(raw) / NS_TO_MS)
                except (ValueError, TypeError):
                    continue
        if not vals:
            continue
        vals.sort()
        count = len(vals)
        totals.append({
            "symbol": sym,
            "entries": count,
            "avg_ms": round(sum(vals) / count, 2),
            "min_ms": round(vals[0], 2),
            "max_ms": round(vals[-1], 2),
            "p50_ms": round(percentile(vals, 50), 2),
        })
    totals.sort(key=lambda s: s["avg_ms"], reverse=True)
    return totals


def parse_df_build_log(log_path):
    """Parse [PROFILING] log lines for df_build/integrity/window_size."""
    pattern = re.compile(
        r"\[PROFILING\]\s+\[(\w+)\]\s+candle=\d+\s+"
        r"df_build=(\d+\.?\d*)ms\s+"
        r"integrity=(\d+\.?\d*)ms\s+"
        r"window_size=(\d+)"
    )
    rows = []
    try:
        with open(log_path, "r") as f:
            for line in f:
                m = pattern.search(line)
                if m:
                    rows.append({
                        "symbol": m.group(1),
                        "df_build_ms": float(m.group(2)),
                        "integrity_ms": float(m.group(3)),
                        "window_size": int(m.group(4)),
                    })
    except FileNotFoundError:
        print(f"  WARNING: log file not found: {log_path}", file=sys.stderr)
    return rows


def format_table(headers, rows):
    """Format aligned ASCII table. Returns string."""
    if not rows:
        return "  (no data)"
    col_widths = [len(h) for h in headers]
    str_rows = []
    for row in rows:
        str_row = [str(v) for v in row]
        str_rows.append(str_row)
        for i, v in enumerate(str_row):
            col_widths[i] = max(col_widths[i], len(v))
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_widths)
    lines = [fmt.format(*headers)]
    lines.append("  " + "  ".join("-" * w for w in col_widths))
    for sr in str_rows:
        lines.append(fmt.format(*sr))
    return "\n".join(lines)


def print_report(signal_stats, symbol_totals, df_build_rows):
    """Print the full profiling report to stdout."""
    sep = "=" * 78
    print(sep)
    print("  Aureus Signal Engine - Profiling Analysis")
    print(sep)

    # --- Per-Symbol Totals ---
    print("\n--- Per-Symbol Totals ---\n")
    if symbol_totals:
        headers = ["Symbol", "Entries", "Avg Total (ms)", "Min (ms)", "Max (ms)", "p50 (ms)"]
        rows = [[s["symbol"], s["entries"], s["avg_ms"], s["min_ms"], s["max_ms"], s["p50_ms"]] for s in symbol_totals]
        print(format_table(headers, rows))
    else:
        print("  (no data)")

    # --- Per-Signal Statistics ---
    print("\n--- Per-Signal Statistics ---\n")
    if signal_stats:
        headers = ["Signal", "Count", "Avg (ms)", "Min (ms)", "Max (ms)", "p50 (ms)", "p95 (ms)", "p99 (ms)"]
        rows = [[s["signal"], s["count"], s["avg_ms"], s["min_ms"], s["max_ms"], s["p50_ms"], s["p95_ms"], s["p99_ms"]] for s in signal_stats]
        print(format_table(headers, rows))
    else:
        print("  (no data)")

    # --- Top 5 Bottlenecks ---
    print("\n--- Top 5 Bottlenecks (by total CPU time) ---\n")
    top5 = signal_stats[:5]
    if top5:
        headers = ["Rank", "Signal", "Total CPU (ms)", "Count", "Avg (ms)"]
        rows = [[i + 1, s["signal"], s["total_cpu_ms"], s["count"], s["avg_ms"]] for i, s in enumerate(top5)]
        print(format_table(headers, rows))
    else:
        print("  (no data)")

    # --- DataFrame Rebuild Time ---
    print("\n--- DataFrame Rebuild Time ---\n")
    if df_build_rows:
        grouped = defaultdict(list)
        for r in df_build_rows:
            grouped[r["symbol"]].append(r)
        headers = ["Symbol", "Samples", "Avg df_build (ms)", "Min (ms)", "Max (ms)", "Avg integrity (ms)"]
        agg_rows = []
        for sym, entries in sorted(grouped.items()):
            dbs = [e["df_build_ms"] for e in entries]
            ints = [e["integrity_ms"] for e in entries]
            agg_rows.append([
                sym, len(entries),
                round(sum(dbs) / len(dbs), 2),
                round(min(dbs), 2),
                round(max(dbs), 2),
                round(sum(ints) / len(ints), 2),
            ])
        print(format_table(headers, agg_rows))
    else:
        print("  (no data - provide --log-file to parse engine logs)")

    print("\n" + sep)


def main():
    parser = argparse.ArgumentParser(description="Analyze profiling data from Redis streams")
    parser.add_argument("--host", default="localhost", help="Redis host (default: localhost)")
    parser.add_argument("--port", type=int, default=6380, help="Redis port (default: 6380 dev)")
    parser.add_argument("--symbols", help="Comma-separated symbols (default: all 8)")
    parser.add_argument("--log-file", help="Path to engine log file for df_build analysis")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else DEFAULT_SYMBOLS

    # Connect Redis
    try:
        r = redis.Redis(host=args.host, port=args.port, decode_responses=True)
        r.ping()
    except redis.ConnectionError:
        print(f"ERROR: Cannot connect to Redis at {args.host}:{args.port}")
        sys.exit(1)

    # Read profiling data
    all_data = read_profiling_data(r, symbols)
    if not all_data:
        print("No profiling data found. Streams may not exist yet.", file=sys.stderr)
        print("  Ensure the signal engine is running with Phase 44.0 instrumentation.", file=sys.stderr)
        sys.exit(0)

    signal_stats = compute_signal_stats(all_data)
    symbol_totals = compute_symbol_totals(all_data)
    df_build_rows = parse_df_build_log(args.log_file) if args.log_file else []

    if args.json:
        output = {
            "symbol_totals": symbol_totals,
            "signal_stats": signal_stats,
            "top_5_bottlenecks": signal_stats[:5],
            "df_build_stats": df_build_rows,
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print_report(signal_stats, symbol_totals, df_build_rows)


if __name__ == "__main__":
    main()
