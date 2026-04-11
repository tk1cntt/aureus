"""Tests for the signal engine configuration module."""
import os
import pytest
from engine.config import (
    SignalEngineConfig,
    get_config,
    reset_config,
    calculate_timeout_candles,
    get_timeframe_seconds,
)


class TestTimeframeConversion:
    """Test timeframe to seconds conversion."""

    def test_m1(self):
        assert get_timeframe_seconds("M1") == 60

    def test_m5(self):
        assert get_timeframe_seconds("M5") == 300

    def test_m15(self):
        assert get_timeframe_seconds("M15") == 900

    def test_h1(self):
        assert get_timeframe_seconds("H1") == 3600

    def test_h4(self):
        assert get_timeframe_seconds("H4") == 14400

    def test_d1(self):
        assert get_timeframe_seconds("D1") == 86400

    def test_unknown_defaults_to_m1(self):
        assert get_timeframe_seconds("UNKNOWN") == 60

    def test_case_insensitive(self):
        assert get_timeframe_seconds("m1") == 60
        assert get_timeframe_seconds("H1") == 3600


class TestTimeoutCalculation:
    """Test timeout candles calculation."""

    def test_m1_2hours(self):
        """M1: 2 hours = 120 candles."""
        assert calculate_timeout_candles("M1", 7200) == 120

    def test_m5_2hours(self):
        """M5: 2 hours = 24 candles."""
        assert calculate_timeout_candles("M5", 7200) == 24

    def test_m15_2hours(self):
        """M15: 2 hours = 8 candles."""
        assert calculate_timeout_candles("M15", 7200) == 8

    def test_h1_2hours(self):
        """H1: 2 hours = 2 candles."""
        assert calculate_timeout_candles("H1", 7200) == 2

    def test_h4_1hour(self):
        """H4: 1 hour = 1 candle."""
        assert calculate_timeout_candles("H4", 3600) == 1

    def test_minimum_1_candle(self):
        """Timeout should be at least 1 candle."""
        assert calculate_timeout_candles("D1", 3600) == 1  # Less than 1 day


class TestSignalEngineConfig:
    """Test the configuration class."""

    def setup_method(self):
        reset_config()
        # Clear env vars to test defaults
        for key in ["SIGNAL_TIMEFRAME", "STRATEGY_TRIGGER_TIMEOUT_CANDLES", 
                    "SIGNAL_HISTORY_MAX_SIZE", "AUTO_RESET_MAX_WAIT_CANDLES"]:
            if key in os.environ:
                del os.environ[key]

    def teardown_method(self):
        reset_config()

    def test_default_values(self):
        """Test default configuration."""
        cfg = SignalEngineConfig()
        assert cfg.timeframe == "M1"
        assert cfg.timeframe_seconds == 60
        assert cfg.trigger_timeout_candles == 120  # 2 hours / 60 seconds
        assert cfg.signal_history_max_size == 200
        assert cfg.auto_reset_max_wait == 50

    def test_custom_timeframe(self, monkeypatch):
        """Test custom timeframe."""
        monkeypatch.setenv("SIGNAL_TIMEFRAME", "M15")
        cfg = SignalEngineConfig()
        assert cfg.timeframe == "M15"
        assert cfg.timeframe_seconds == 900
        assert cfg.trigger_timeout_candles == 8  # 7200 / 900

    def test_explicit_timeout_override(self, monkeypatch):
        """Test explicit timeout override."""
        monkeypatch.setenv("SIGNAL_TIMEFRAME", "M1")
        monkeypatch.setenv("STRATEGY_TRIGGER_TIMEOUT_CANDLES", "60")
        cfg = SignalEngineConfig()
        assert cfg.trigger_timeout_candles == 60  # Not auto-calculated

    def test_custom_history_size(self, monkeypatch):
        """Test custom history size."""
        monkeypatch.setenv("SIGNAL_HISTORY_MAX_SIZE", "500")
        cfg = SignalEngineConfig()
        assert cfg.signal_history_max_size == 500

    def test_custom_auto_reset(self, monkeypatch):
        """Test custom auto-reset max wait."""
        monkeypatch.setenv("AUTO_RESET_MAX_WAIT_CANDLES", "100")
        cfg = SignalEngineConfig()
        assert cfg.auto_reset_max_wait == 100

    def test_singleton(self):
        """Test get_config returns singleton."""
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_reset_singleton(self):
        """Test reset_config allows new singleton."""
        cfg1 = get_config()
        reset_config()
        cfg2 = get_config()
        assert cfg1 is not cfg2

    def test_repr(self):
        """Test string representation."""
        cfg = SignalEngineConfig()
        repr_str = repr(cfg)
        assert "M1" in repr_str
        assert "120" in repr_str
        assert "200" in repr_str
