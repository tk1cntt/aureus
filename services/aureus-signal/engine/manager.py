import pandas as pd
from collections import defaultdict

from .state import SymbolState

class WindowManager:
    """Manages a sliding window of candles and persistent state for each symbol."""
    
    def __init__(self, max_window=3000):
        self.max_window = max_window
        self.windows = defaultdict(list)
        self.window_dicts = defaultdict(dict)  # O(1) lookup: t -> candle reference
        self.dfs = {}
        self.states = {}

    def reset(self, symbol):
        """Clears memory state for a specific symbol."""
        if symbol in self.windows: del self.windows[symbol]
        if symbol in self.window_dicts: del self.window_dicts[symbol]
        if symbol in self.dfs: del self.dfs[symbol]
        if symbol in self.states: del self.states[symbol]

    def update(self, symbol, data):
        """Append a new candle, update state, and return symbols context."""
        if symbol not in self.states:
            self.states[symbol] = SymbolState(symbol)
        
        state = self.states[symbol]
        # Convert numeric fields
        candle = {
            't': int(data['t']),
            'o': float(data['o']),
            'h': float(data['h']),
            'l': float(data['l']),
            'c': float(data['c']),
            'v': float(data['v']),
            'tf': data.get('tf', 'M1')
        }
        
        # Add to window list with deduplication and sorting
        window = self.windows[symbol]
        window_dict = self.window_dicts[symbol]
        
        # Fast path for live updates (matches last candle)
        if window and window[-1]['t'] == candle['t']:
            window[-1] = candle
            window_dict[candle['t']] = candle
        elif candle['t'] in window_dict:
            # O(1) lookup to find that timestamp exists, then update list + dict
            for idx, c in enumerate(window):
                if c['t'] == candle['t']:
                    window[idx] = candle
                    break
            window_dict[candle['t']] = candle
        else:
            # New candle — append and register in dict
            window.append(candle)
            window_dict[candle['t']] = candle
            # Sort if we inserted out of order
            if len(window) > 1 and candle['t'] < window[-2]['t']:
                window.sort(key=lambda x: x['t'])
        
        # Log ingestion
        if len(window) > 0:
            import logging
            mgr_logger = logging.getLogger("aureus-manager")
            mgr_logger.info(f"====>[Manager] Ingested {symbol} t={candle['t']} window_last={window[-1]['t']} size={len(window)}")
        
        # Keep window size
        if len(window) > self.max_window:
            removed_candles = window[:-self.max_window]
            self.windows[symbol] = window[-self.max_window:]
            window = self.windows[symbol]
            # Clean up dict entries for removed candles
            for rc in removed_candles:
                window_dict.pop(rc['t'], None)
            
        # Create/Update DataFrame
        df = pd.DataFrame(window)
        self.dfs[symbol] = df
        
        # Update price-action state (Lifespan logic)
        # IMPORTANT: state.update_with_candle handles OB/FVG mitigation lifecycle.
        # If this is an OLD candle (e.g. backfill), we might not want to run full update_with_candle
        # yet, but for now we assume it's fine.
        state.update_with_candle(candle)
        
        return df, state

    def get_df(self, symbol):
        return self.dfs.get(symbol)
