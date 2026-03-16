import pytest
import sys
import os

# Ensure we can import from engine
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState

def test_symbol_state_t_map_initialization():
    """
    Test Case: SymbolState should initialize with an empty t_map.
    Story 3.1 / Task 1
    """
    state = SymbolState("BTCUSD")
    # This should fail initially until implemented
    assert hasattr(state, 't_map'), "SymbolState should have t_map attribute"
    assert isinstance(state.t_map, dict), "t_map should be a dictionary"
    assert len(state.t_map) == 0, "t_map should be empty initially"

def test_symbol_state_reset_clears_t_map():
    """
    Test Case: reset() should clear t_map.
    Story 3.1 / Task 1
    """
    state = SymbolState("BTCUSD")
    state.t_map = {123456789: 0}
    state.reset()
    assert len(state.t_map) == 0, "reset() should clear t_map"

def test_symbol_state_serialization():
    """
    Test Case: SymbolState serialization should include t_map.
    Story 3.1 / Task 2
    """
    state = SymbolState("BTCUSD")
    test_map = {111: 1, 222: 2}
    state.t_map = test_map.copy()
    
    # Test to_dict
    serialized = state.to_dict()
    assert "t_map" in serialized, "serialized dict should contain t_map"
    assert serialized["t_map"] == test_map, "t_map should match in serialized dict"
    
    # Test from_dict
    new_state = SymbolState("BTCUSD")
    new_state.from_dict(serialized)
    assert new_state.t_map == test_map, "t_map should be restored from dict"
