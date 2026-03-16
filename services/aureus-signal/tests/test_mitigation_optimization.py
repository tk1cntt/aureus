import pytest
import pandas as pd
import sys
import os
from unittest.mock import MagicMock

# Ensure we can import from engine
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState
from engine.signals.structure import StructureSignal

def test_verify_mitigations_gap_check_vectorized():
    """
    Test Case: _verify_mitigations should detect touches anywhere in the range (Vectorized/Gap-Safe).
    Story 4.2 / AC 1 & 2
    """
    state = SymbolState("BTCUSD")
    signal = StructureSignal()
    
    # Create an active bullish OB
    ob = {
        "ob_type": "BULLISH",
        "top": 100.0,
        "bottom": 90.0,
        "t_start": 1000,
        "t_breakout": 1010,
        "mitigated": False,
        "last_check_t": 1010
    }
    state.add_ob(ob)
    
    # Data where a MIDDLE candle touches, but the LATEST doesn't.
    # Story 4.2 (Gap-Safe) MUST detect this.
    data = [
        {'t': 1011, 'o': 110, 'h': 120, 'l': 85,  'c': 110}, # TOUCH in middle
        {'t': 1012, 'o': 110, 'h': 120, 'l': 105, 'c': 115}, # NO TOUCH at end
    ]
    df = pd.DataFrame(data)
    
    signal._verify_mitigations(df, state)
    
    # The OB SHOULD be mitigated because 1011 touched it.
    assert state.obs[0]['mitigated']
    assert state.obs[0]['t_mitigation'] == 1011

def test_verify_mitigations_fast_path_trigger():
    """
    Test Case: _verify_mitigations should trigger a sweep if the latest candle touches.
    Story 4.1 / Task 1 & 2
    """
    state = SymbolState("BTCUSD")
    signal = StructureSignal()
    
    # Create an active bullish OB
    ob = {
        "ob_type": "BULLISH",
        "top": 100.0,
        "bottom": 90.0,
        "t_start": 1000,
        "t_breakout": 1010,
        "mitigated": False
    }
    state.add_ob(ob)
    
    # Data where the latest candle touches the zone
    data = [
        {'t': 1011, 'o': 110, 'h': 120, 'l': 105, 'c': 115}, # NO TOUCH
        {'t': 1012, 'o': 110, 'h': 120, 'l': 95,  'c': 100}, # TOUCH at end
    ]
    df = pd.DataFrame(data)
    
    signal._verify_mitigations(df, state)
    
    # The OB should now be mitigated
    assert state.obs[0]['mitigated']
    assert state.obs[0]['t_mitigation'] == 1012

def test_verify_mitigations_gap_detection():
    """
    Test Case: _verify_mitigations should detect a touch even if it happens 
    in the middle of a multi-candle gap (Story 4.2).
    """
    state = SymbolState("BTCUSD")
    signal = StructureSignal()
    
    # Create an active bullish OB
    # breakout at 1010
    ob = {
        "ob_type": "BULLISH",
        "top": 100.0,
        "bottom": 90.0,
        "t_start": 1000,
        "t_breakout": 1010,
        "mitigated": False,
        "last_check_t": 1010
    }
    state.add_ob(ob)
    
    # Gap data: 1011 touched, 1012 didn't.
    # Latest is 1012.
    data = [
        {'t': 1011, 'o': 110, 'h': 120, 'l': 95,  'c': 110}, # TOUCH 
        {'t': 1012, 'o': 110, 'h': 120, 'l': 105, 'c': 115}, # NO TOUCH
    ]
    df = pd.DataFrame(data)
    
    signal._verify_mitigations(df, state)
    
    # With Story 4.2, this SHOULD be mitigated now!
    assert state.obs[0]['mitigated']
    assert state.obs[0]['t_mitigation'] == 1011 # Correct first touch time
