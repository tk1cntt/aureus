from __future__ import annotations

from unittest.mock import patch

import pytest

from settings import NautilusNodeSettings


def test_strict_mode_requires_sl_tp_enabled():
    with patch.dict(
        "os.environ",
        {
            "NAUTILUS_SYMBOL_WHITELIST": "XAUUSD",
            "NAUTILUS_RISK_MODE": "STRICT",
            "NAUTILUS_REQUIRE_SL_TP": "0",
        },
        clear=True,
    ):
        with pytest.raises(ValueError, match="STRICT mode requires SL/TP enforcement"):
            NautilusNodeSettings.from_env()


def test_invalid_symbol_whitelist_rejected():
    with patch.dict(
        "os.environ",
        {
            "NAUTILUS_SYMBOL_WHITELIST": "xauusd,EUR/USD",
            "NAUTILUS_RISK_MODE": "STRICT",
            "NAUTILUS_REQUIRE_SL_TP": "1",
        },
        clear=True,
    ):
        with pytest.raises(ValueError, match="Invalid symbol whitelist entry"):
            NautilusNodeSettings.from_env()


def test_valid_settings_pass_validation():
    with patch.dict(
        "os.environ",
        {
            "NAUTILUS_SYMBOL_WHITELIST": "XAUUSD,EURUSD",
            "NAUTILUS_RISK_MODE": "STRICT",
            "NAUTILUS_REQUIRE_SL_TP": "1",
            "NAUTILUS_MAX_POSITION_NOTIONAL": "200000",
            "NAUTILUS_MAX_ORDER_NOTIONAL": "10000",
        },
        clear=True,
    ):
        settings = NautilusNodeSettings.from_env()
        assert settings.symbol_whitelist == ["XAUUSD", "EURUSD"]
        assert settings.risk_mode == "STRICT"
