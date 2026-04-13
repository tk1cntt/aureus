"""
Quick CISD MTF diagnostic — fetch 2000 M1 candles (matching live service window),
scan 8 symbols x 4 TFs.
Run: cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-signal/tests/quick_cisd_check.py
"""
import subprocess, sys, time
sys.path.insert(0, "services/aureus-signal")

import pandas as pd
from engine.signals.resampler import resample_to_tf
from engine.signals.cisd_mtf import CISDMultiTFSignal

SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "BTCUSD", "ETHUSD", "USTEC"]
TFS = ["M5", "M15", "M30", "H1"]
CANDLE_LIMIT = 2000  # Match WindowManager max_window=2000


def fetch_m1(symbol: str, limit: int = CANDLE_LIMIT):
    # Get LATEST candles (matches live service which keeps most recent window)
    query = (
        "SELECT extract(epoch FROM time)::integer as t, "
        "open as o, high as h, low as l, close as c, volume as v "
        "FROM aureus_candles "
        "WHERE symbol = '%s' AND timeframe = 'M1' "
        "ORDER BY time DESC LIMIT %s;"
    ) % (symbol, limit)
    result = subprocess.run(
        ["docker", "exec", "aureus_timescaledb_dev", "psql",
         "-U", "aureus", "-d", "aureus", "-t", "-A", "-F", "|", "-c", query],
        capture_output=True, text=True, timeout=30,
    )
    rows = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip().split("|")
        if len(parts) != 6:
            continue
        rows.append({
            "t": int(parts[0]), "o": float(parts[1]), "h": float(parts[2]),
            "l": float(parts[3]), "c": float(parts[4]), "v": float(parts[5]),
        })
    rows.reverse()  # chronological order
    return rows


def scan_df(df: pd.DataFrame, tf: str):
    """Resample M1 -> tf, scan CISD state machine, return (status, candle_count)."""
    ht = resample_to_tf(df, tf)
    if ht is None or len(ht) < 3:
        return ("--", 0)
    completed = ht.iloc[:-1]  # exclude forming candle
    max_bars = min(24, len(completed))

    signal = CISDMultiTFSignal._scan_cisd(completed, max_bars)

    if signal > 0:
        status = "BULL"
    elif signal < 0:
        status = "BEAR"
    else:
        status = "NONE"

    return (status, len(completed))


def main():
    t0 = time.time()
    print(f"\n{'='*72}")
    print(f"  CISD MTF Quick Check  |  {time.strftime('%H:%M:%S')}  |  {CANDLE_LIMIT} M1 candles/symbol")
    print(f"{'='*72}")
    print(f"  {'Symbol':<10s}  {'M5':<14s}  {'M15':<14s}  {'M30':<14s}  {'H1':<14s}")
    print(f"  {'-'*10}  {'-'*14}  {'-'*14}  {'-'*14}  {'-'*14}")

    for symbol in SYMBOLS:
        rows = fetch_m1(symbol, CANDLE_LIMIT)
        if not rows:
            print(f"  {symbol:<10s}  {'NO DATA':<14s}")
            continue
        df = pd.DataFrame(rows)
        cells = []
        for tf in TFS:
            status, count = scan_df(df, tf)
            cells.append(f"{status} ({count})")

        # Color coding via emoji
        colored_cells = []
        for c in cells:
            if "BULL" in c.upper():
                colored_cells.append(f"🟢 {c}")
            elif "BEAR" in c.upper():
                colored_cells.append(f"🔴 {c}")
            else:
                colored_cells.append(f"⚪ {c}")

        print(f"  {symbol:<10s}  {colored_cells[0]:<14s}  {colored_cells[1]:<14s}  {colored_cells[2]:<14s}  {colored_cells[3]:<14s}")

    elapsed = time.time() - t0
    print(f"\n  Done in {elapsed:.1f}s  |  {CANDLE_LIMIT} M1 candles per symbol")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    main()
