import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState


def test_state_tracks_signal_sequence_counter():
    state = SymbolState("XAUUSD")
    assert hasattr(state, "signal_seq")
    assert state.signal_seq == 0
    assert hasattr(state, "current_run_id")
    assert state.current_run_id == "live"
