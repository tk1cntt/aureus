import os
import sys
import pandas as pd
import pytest

# Ensure engine is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState
from engine.signals.pivots import PivotSignal

def test_zigzag_engine_stability():
    """
    Story 5.1: Verify ZigZag engine is correctly reused, updated, or re-initialized.
    """
    state = SymbolState("BTCUSD")
    # Initial call
    signal = PivotSignal(ext_period=5, min_amplitude=100)
    
    df = pd.DataFrame([
        {'t': 100, 'o': 50000, 'h': 50100, 'l': 49900, 'c': 50000},
        {'t': 101, 'o': 50000, 'h': 50500, 'l': 49900, 'c': 50400}
    ])
    
    # 1. First initialization
    signal.calculate(df, state)
    engine_v1 = state.zigzag_engine
    assert engine_v1 is not None
    assert state.zigzag_config['ext_period'] == 5
    assert state.zigzag_config['min_amplitude'] == 100
    
    # 2. Same params: Should REUSE the same instance
    signal.calculate(df, state)
    assert state.zigzag_engine is engine_v1
    
    # 3. Changed min_amplitude: Should UPDATE (not re-init)
    signal_v2 = PivotSignal(ext_period=5, min_amplitude=200)
    signal_v2.calculate(df, state)
    assert state.zigzag_engine is engine_v1 # Same instance!
    assert state.zigzag_config['min_amplitude'] == 200
    assert engine_v1.mp == pytest.approx(200 * 0.01) # Assuming point=0.01
    
    # 4. Changed ext_period: Should RE-INITIALIZE (Structural change)
    signal_v3 = PivotSignal(ext_period=10, min_amplitude=200)
    signal_v3.calculate(df, state)
    assert state.zigzag_engine is not engine_v1 # New instance!
    assert state.zigzag_config['ext_period'] == 10
    
    # 5. Changed engine_type: Should RE-INITIALIZE
    signal_v4 = PivotSignal(ext_period=10, zigzag_engine="pro2") # Same type as default
    signal_v4.calculate(df, state)
    assert state.zigzag_engine is not None
    # If we had a second type, we would test switching here.

def test_dynamic_amplitude_stability():
    """
    Verify that dynamic amplitude (percentage based) updates correctly without wiping state.
    """
    state = SymbolState("BTCUSD")
    signal = PivotSignal(min_amplitude_pct=1.0, point=1.0) # 1% of price
    
    df = pd.DataFrame([
        {'t': 100, 'o': 100, 'h': 105, 'l': 95, 'c': 100}
    ])
    
    # Init: 1% of 100 = 1 point
    signal.calculate(df, state)
    engine = state.zigzag_engine
    assert state.zigzag_config['min_amplitude'] == 1
    
    # Update price to 200: 1% of 200 = 2 points
    df2 = pd.DataFrame([
        {'t': 101, 'o': 200, 'h': 205, 'l': 195, 'c': 200}
    ])
    signal.calculate(df2, state)
    assert state.zigzag_engine is engine # Reuse
    assert state.zigzag_config['min_amplitude'] == 2
    assert engine.mp == 2.0
