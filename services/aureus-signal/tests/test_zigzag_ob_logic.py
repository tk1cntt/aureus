import pytest
import pandas as pd
from engine.common.zigzag_pro2 import ZigZagPro, ExtremumType, PivotState

def test_zigzag_ob_breakout_low_dynamic_origin():
    """
    Test Case: TROUGH -> OB -> Phá Low
    Logic: Sau Trough, gặp OB, sau đó phá Low. 
    Kết quả mong đợi: OB High trở thành Peak, Low của nến phá vỡ trở thành Trough mới.
    """
    # ext_period=2, mp=10
    zz = ZigZagPro(ext_period=2, min_amplitude=10, point=1.0, digits=0)
    
    # Cần ít nhất 2 nến đầu để khởi tạo search window
    data = [
        {'t': 100, 'o': 100, 'h': 110, 'l': 90, 'c': 100},  # 0
        {'t': 101, 'o': 100, 'h': 105, 'l': 85, 'c': 90},   # 1
        {'t': 102, 'o': 85,  'h': 90,  'l': 70, 'c': 80},   # 2: Trough
        {'t': 103, 'o': 80,  'h': 115, 'l': 105, 'c': 110}, # 3: Recovery
    ]
    df = pd.DataFrame(data)
    zz.update(df)
    
    assert zz.last_dn_idx == 2
    assert zz.dn[2] == 70
    
    # OB tại bar 4: High=130, Low=60 
    data_ob = data + [
        {'t': 104, 'o': 100, 'h': 130, 'l': 60, 'c': 110},  # 4: OB
    ]
    zz.update(pd.DataFrame(data_ob), incremental=True)
    assert zz.ob_waiting == True
    
    # Phá Low tại bar 5: Low=55
    data_break = data_ob + [
        {'t': 105, 'o': 110, 'h': 115, 'l': 55, 'c': 60},   # 5: Break Low
    ]
    zz.update(pd.DataFrame(data_break), incremental=True)
    
    # Kết quả: OB High (bar 4) là Peak, Bar 5 là Trough
    assert zz.ob_waiting == False
    assert zz.up[4] == 130
    assert zz.dn[5] == 55
    assert zz.last_up_idx == 4
    assert zz.last_dn_idx == 5

def test_zigzag_ob_pending_ib_exit():
    """
    Test Case: OB -> 5 nến IB -> Thoát mặc định (Double Pivot)
    """
    zz = ZigZagPro(ext_period=2, min_amplitude=10, point=1.0, digits=0)
    
    # 1. Thiết lập Peak tại bar 1
    data = [
        {'t': 100, 'o': 100, 'h': 150, 'l': 140, 'c': 145}, # 0
        {'t': 101, 'o': 145, 'h': 170, 'l': 155, 'c': 160}, # 1: Peak
        {'t': 102, 'o': 160, 'h': 140, 'l': 130, 'c': 135}, # 2: Low 130, High 140
    ]
    zz.update(pd.DataFrame(data))
    assert zz.last_up_idx == 1
    
    # 2. OB tại bar 3 (High 145 > 140, Low 120 < 130)
    data_ob = data + [
        {'t': 103, 'o': 135, 'h': 145, 'l': 120, 'c': 130}, # 3: OB (H=145, L=120)
    ]
    zz.update(pd.DataFrame(data_ob), incremental=True)
    assert zz.ob_waiting == True
    
    # 3. 5 nến IB
    ib_candles = []
    for j in range(5):
        ib_candles.append({'t': 104+j, 'o': 130, 'h': 135, 'l': 125, 'c': 130})
    
    data_final = data_ob + ib_candles
    zz.update(pd.DataFrame(data_final), incremental=True)
    
    # BAR 3: OB High (145) trở thành Peak (vì last là Trough tại bar 2)
    # BAR 8: Current Low (125) trở thành Trough
    assert zz.ob_waiting == False
    assert zz.up[3] == 145
    assert zz.dn[8] == 125
    assert zz.last_up_idx == 3
    assert zz.last_dn_idx == 8

def test_zigzag_ob_priority_replace():
    """
    Test Case: PEAK -> OB (High cao hơn Peak cũ)
    """
    zz = ZigZagPro(ext_period=2, min_amplitude=10, point=1.0, digits=0)
    
    data = [
        {'t': 100, 'o': 100, 'h': 120, 'l': 110, 'c': 115}, # 0
        {'t': 101, 'o': 115, 'h': 130, 'l': 120, 'c': 125}, # 1: Peak
        {'t': 102, 'o': 125, 'h': 115, 'l': 111, 'c': 112}, # 2: 130 - 111 = 19 > 10. Vẫn là Trough.
    ]
    # Ta muốn bar 2 là Trough để test xem OB sau đó có thay thế Peak tại 1 không.
    # Actually, if bar 2 is a Trough, OB at 3 will have let == -1.
    # To test Peak replacement, let must be 1. So bar 2 must NOT be a Trough.
    data_no_trough = [
        {'t': 100, 'o': 100, 'h': 120, 'l': 110, 'c': 115}, # 0
        {'t': 101, 'o': 115, 'h': 130, 'l': 120, 'c': 125}, # 1: Peak
        {'t': 102, 'o': 125, 'h': 128, 'l': 125, 'c': 127}, # 2: 130 - 125 = 5 < 10. KHÔNG là Trough.
    ]
    zz.update(pd.DataFrame(data_no_trough))
    assert zz.last_up_idx == 1
    
    # OB tại bar 3 (High 145 > 128, Low 100 < 125)
    data_ob = data_no_trough + [
        {'t': 104, 'o': 115, 'h': 145, 'l': 100, 'c': 120}, # 3: OB
    ]
    zz.update(pd.DataFrame(data_ob), incremental=True)
    
    # Peak cũ (1) bị xóa, Peak mới dời về (3)
    assert zz.up[1] == zz.EMPTY_VALUE
    assert zz.up[3] == 145
    assert zz.last_up_idx == 3
    assert zz.ob_waiting == True

def test_zigzag_ob_sweep_trough_break_low():
    """
    Test Case: Trough -> OB (Sweep Trough) -> Break Low
    Expectation:
    1. OB bar replaces old Trough (Sweep).
    2. Break Low triggers OB Peak (at OB High) and New Trough (at Breaking bar).
    """
    # ext_period=2, mp=10
    zz = ZigZagPro(ext_period=2, min_amplitude=10, point=1.0, digits=0)
    
    # 1. Trough at bar 1 (Low 100), Peak at 0 (High 150)
    data = [
        {'t': 100, 'h': 150, 'l': 130, 'o': 140, 'c': 145}, # 0: Peak (SearchWindow=2)
        {'t': 101, 'h': 120, 'l': 100, 'o': 115, 'c': 110}, # 1: Trough
        {'t': 102, 'h': 115, 'l': 102, 'o': 110, 'c': 105}, # 2: Inside bar
    ]
    zz.update(pd.DataFrame(data))
    assert zz.last_dn_idx == 1
    
    # 2. OB at bar 3 (High 160, Low 90) -> Sweeps bar 1 (90 < 100)
    data_ob = data + [
        {'t': 103, 'h': 160, 'l': 90, 'o': 125, 'c': 115}, # 3: OB (H=160, L=90)
    ]
    zz.update(pd.DataFrame(data_ob), incremental=True)
    
    # OB should replace old Trough at 1 and stay waiting
    assert zz.dn[1] == zz.EMPTY_VALUE
    assert zz.dn[3] == 90
    assert zz.last_dn_idx == 3
    assert zz.ob_waiting == True
    
    # 3. Bar 4 breaks OB Low (Low 85)
    data_break = data_ob + [
        {'t': 104, 'h': 100, 'l': 85, 'o': 95, 'c': 90}, # 4: Break Low
    ]
    zz.update(pd.DataFrame(data_break), incremental=True)
    
    # Result: Peak at OB High (3), Trough at Breaking Bar (4)
    assert zz.ob_waiting == False
    assert zz.up[3] == 160
    assert zz.dn[4] == 85
    assert zz.last_up_idx == 3
    assert zz.last_dn_idx == 4
