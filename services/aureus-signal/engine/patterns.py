
class PatternEngine:
    """Engine for detecting SMC patterns (FVG, Liquidity Sweep, MSS)."""

    def scan(self, symbol, df):
        """Scan for all patterns and return a list of signals."""
        signals = []
        
        # 1. Detect Fair Value Gap (FVG)
        fvg = self.detect_fvg(df)
        if fvg:
            signals.append(fvg)
            
        # 2. Detect Liquidity Sweep
        sweep = self.detect_liquidity_sweep(df)
        if sweep:
            signals.append(sweep)
            
        # 3. Detect Market Structure Shift (MSS)
        mss = self.detect_mss(df)
        if mss:
            signals.append(mss)
            
        return signals

    def detect_fvg(self, df):
        """Detect Fair Value Gap in the last 3 candles."""
        if len(df) < 3:
            return None
        
        # Get last 3 candles (c1, c2, c3 - where c3 is latest)
        c1 = df.iloc[-3]
        c2 = df.iloc[-2]
        c3 = df.iloc[-1]
        
        # Bullish FVG: Low(c3) > High(c1)
        if c3['l'] > c1['h']:
            return {
                "type": "SIGNAL",
                "subtype": "FVG",
                "direction": "BULLISH",
                "symbol": df.iloc[0]['symbol'] if 'symbol' in df.columns else "UNKNOWN",
                "t": int(c3['t']),
                "top": float(c3['l']),
                "bottom": float(c1['h']),
                "msg": f"Bullish FVG detected between {c1['h']} and {c3['l']}"
            }
            
        # Bearish FVG: High(c3) < Low(c1)
        if c3['h'] < c1['l']:
            return {
                "type": "SIGNAL",
                "subtype": "FVG",
                "direction": "BEARISH",
                "symbol": df.iloc[0]['symbol'] if 'symbol' in df.columns else "UNKNOWN",
                "t": int(c3['t']),
                "top": float(c1['l']),
                "bottom": float(c3['h']),
                "msg": f"Bearish FVG detected between {c3['h']} and {c1['l']}"
            }
            
        return None

    def detect_liquidity_sweep(self, df):
        """Detect Liquidity Sweep near recent highs/lows."""
        # Simple implementation: check if current high/low swept previous N candles
        if len(df) < 20:
            return None
            
        current = df.iloc[-1]
        lookback = df.iloc[-20:-1]
        
        prev_high = lookback['h'].max()
        prev_low = lookback['l'].min()
        
        # Bearish Sweep: current high > prev_high BUT current close < prev_high
        if current['h'] > prev_high and current['c'] < prev_high:
            return {
                "type": "SIGNAL",
                "subtype": "LIQUIDITY_SWEEP",
                "direction": "BEARISH",
                "t": int(current['t']),
                "price": float(prev_high),
                "msg": f"Bearish Liquidity Sweep at {prev_high}"
            }
            
        # Bullish Sweep: current low < prev_low BUT current close > prev_low
        if current['l'] < prev_low and current['c'] > prev_low:
            return {
                "type": "SIGNAL",
                "subtype": "LIQUIDITY_SWEEP",
                "direction": "BULLISH",
                "t": int(current['t']),
                "price": float(prev_low),
                "msg": f"Bullish Liquidity Sweep at {prev_low}"
            }
            
        return None

    def detect_mss(self, df):
        """Detect Market Structure Shift (Placeholder for now)."""
        # Complex logic requiring trend identification, keeping simple for MVP
        return None
