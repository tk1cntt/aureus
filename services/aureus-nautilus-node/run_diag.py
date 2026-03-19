#!/usr/bin/env python3
"""Run test_node_setup and print full traceback."""
import sys
sys.path.insert(0, "/app")

try:
    from nautilus_trader.live.node import LiveTradingNode
    print("LiveTradingNode import OK")
except Exception as e:
    print(f"LiveTradingNode import FAIL: {e}")

try:
    from config import get_node_config
    print("get_node_config import OK")
except Exception as e:
    print(f"get_node_config import FAIL: {e}")

try:
    config = get_node_config()
    print(f"Config created: {type(config)}")
except Exception as e:
    print(f"Config creation FAIL: {e}")
    import traceback
    traceback.print_exc()

try:
    config = get_node_config()
    node = LiveTradingNode(config=config)
    print(f"Node created OK, clock={node.clock}")
except Exception as e:
    print(f"Node creation FAIL: {e}")
    import traceback
    traceback.print_exc()
