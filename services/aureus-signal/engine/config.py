"""
Aureus Signal Engine Configuration

Reads environment variables and provides computed configuration values.
Supports multi-timeframe deployment with auto-calculated defaults.
"""
import os
from typing import Dict


# Timeframe to seconds mapping
TIMEFRAME_SECONDS: Dict[str, int] = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}

# Default timeout: 2 hours worth of candles per timeframe
DEFAULT_TIMEOUT_SECONDS = 7200  # 2 hours


def get_timeframe_seconds(timeframe: str) -> int:
    """Convert timeframe string to seconds."""
    tf = timeframe.strip().upper()
    return TIMEFRAME_SECONDS.get(tf, 60)  # Default to M1


def calculate_timeout_candles(timeframe: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> int:
    """
    Calculate timeout candles from timeframe.
    
    Formula: timeout_seconds / timeframe_seconds
    Result: number of candles to wait before clearing triggered_t
    
    Examples:
        M1:  7200 / 60   = 120 candles (2 hours)
        M5:  7200 / 300  = 24 candles (2 hours)
        M15: 7200 / 900  = 8 candles (2 hours)
        H1:  7200 / 3600 = 2 candles (2 hours)
    """
    tf_seconds = get_timeframe_seconds(timeframe)
    return max(1, timeout_seconds // tf_seconds)  # At least 1 candle


class SignalEngineConfig:
    """Configuration for the signal engine, loaded from environment variables."""
    
    def __init__(self):
        # Timeframe
        self.timeframe = os.getenv("SIGNAL_TIMEFRAME", "M1").strip().upper()
        self.timeframe_seconds = get_timeframe_seconds(self.timeframe)
        
        # Strategy trigger timeout
        explicit_timeout = os.getenv("STRATEGY_TRIGGER_TIMEOUT_CANDLES")
        if explicit_timeout and explicit_timeout.strip():
            self.trigger_timeout_candles = int(explicit_timeout)
        else:
            # Auto-calculate: 2 hours worth of candles
            self.trigger_timeout_candles = calculate_timeout_candles(self.timeframe)
        
        # Signal history max size
        self.signal_history_max_size = int(os.getenv("SIGNAL_HISTORY_MAX_SIZE", "200"))
        
        # Auto-reset max wait candles
        self.auto_reset_max_wait = int(os.getenv("AUTO_RESET_MAX_WAIT_CANDLES", "50"))
    
    def __repr__(self) -> str:
        return (
            f"SignalEngineConfig("
            f"timeframe={self.timeframe}, "
            f"trigger_timeout={self.trigger_timeout_candles} candles, "
            f"history_max={self.signal_history_max_size}, "
            f"auto_reset_max_wait={self.auto_reset_max_wait}"
            f")"
        )


# Singleton instance
_config: SignalEngineConfig = None


def get_config() -> SignalEngineConfig:
    """Get or create the global config singleton."""
    global _config
    if _config is None:
        _config = SignalEngineConfig()
    return _config


def reset_config() -> None:
    """Reset the config singleton (useful for testing)."""
    global _config
    _config = None
