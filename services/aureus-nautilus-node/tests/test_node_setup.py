import pytest
from nautilus_trader.live.node import TradingNode
from config import get_node_config

def test_node_configuration_creates_valid_node():
    config = get_node_config()
    node = TradingNode(config=config)
    assert node is not None
