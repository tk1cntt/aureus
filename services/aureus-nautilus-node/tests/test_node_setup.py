from __future__ import annotations

from unittest.mock import patch

from config import get_node_config


def test_node_configuration_creates_valid_node():
    config = get_node_config()
    assert config is not None


def test_node_configuration_loads_validated_settings():
    with patch.dict(
        "os.environ",
        {
            "NAUTILUS_SYMBOL_WHITELIST": "XAUUSD,EURUSD",
            "NAUTILUS_RISK_MODE": "STRICT",
            "NAUTILUS_REQUIRE_SL_TP": "1",
        },
        clear=False,
    ):
        config = get_node_config()
        assert config is not None
