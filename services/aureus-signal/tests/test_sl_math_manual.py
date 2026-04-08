import pytest
from engine.orders import get_point_size

def test_point_size():
    # Test standard forex
    assert get_point_size("EURUSD") == 0.00001
    assert get_point_size("GBPUSD") == 0.00001
    
    # Test JPY
    assert get_point_size("USDJPY") == 0.001
    
    # Test XAU
    assert get_point_size("XAUUSD") == 0.001
    assert get_point_size("GOLD") == 0.001
    
    # Test BTC
    assert get_point_size("BTCUSD") == 0.01
    
    # Test Indices
    assert get_point_size("USTEC") == 0.01
    assert get_point_size("US30") == 0.01

def test_sl_calculation_math():
    class DummyState:
        def __init__(self, symbol, close_price):
            self.symbol = symbol
            self.last_candle = {'c': str(close_price)}
            self.swing_points = []
            
    # Copy snippet of calculating sl
    def calc_sl(symbol, entry_price, config_value, side):
        entry = float(entry_price)
        point_size = get_point_size(symbol)
        price_delta = config_value * point_size
        return (entry - price_delta) if side == 'BUY' else (entry + price_delta)

    # 1. EURUSD: 500 config points, point size = 0.00001
    entry = 1.10000
    sl = calc_sl("EURUSD", entry, 500, "BUY")
    assert round(sl, 5) == 1.09500
    
    distance = abs(sl - entry)
    assert round(distance, 5) == 0.00500
    points_in_mt5_5digits = distance / 0.00001
    assert round(points_in_mt5_5digits) == 500

    # 2. XAUUSD: 500 config points
    # If MT5 XAUUSD uses 2 digits (point=0.01)
    entry_xau = 2000.00
    sl_xau = calc_sl("XAUUSD", entry_xau, 500, "BUY")
    distance_xau = abs(sl_xau - entry_xau)
    # With get_point_size("XAUUSD") == 0.001
    assert round(distance_xau, 3) == 0.500
    
    # If MT5 XAUUSD point is 0.01:
    points_in_mt5_xau_2digits = distance_xau / 0.01
    assert round(points_in_mt5_xau_2digits) == 50  # Only 50 MT5 points (5 pips)
    
    # If MT5 XAUUSD point is 0.001:
    points_in_mt5_xau_3digits = distance_xau / 0.001
    assert round(points_in_mt5_xau_3digits) == 500 # 500 MT5 points (50 pips)

    # 3. BTCUSD: 500 config points
    entry_btc = 68000.00
    sl_btc = calc_sl("BTCUSD", entry_btc, 500, "SELL")
    distance_btc = abs(sl_btc - entry_btc)
    # get_point_size("BTCUSD") == 0.01
    assert round(distance_btc, 2) == 5.0
    
    # If MT5 BTCUSD point is 0.01
    points_in_mt5_btc_2digits = distance_btc / 0.01
    assert round(points_in_mt5_btc_2digits) == 500 # 500 MT5 points!

if __name__ == "__main__":
    pytest.main(["-v", __file__])
