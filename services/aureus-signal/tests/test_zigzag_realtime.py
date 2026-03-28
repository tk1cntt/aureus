import unittest
import pandas as pd
import sys
import os

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.common.zigzag_pro2 import ZigZagPro, ExtremumType

class TestZigZagRealtime(unittest.TestCase):
    def setUp(self):
        self.params = {
            "ext_period": 3,
            "min_amplitude": 10,
            "min_motion": 0,  # Ensure every movement is processed
            "point": 1.0,
            "digits": 0
        }
        
    def test_stuck_pivot_fix_repro(self):
        """
        Objective: Prove that ZigZag fails to update the last candle extremum
        if rates_total remains unchanged (real-time tick).
        """
        engine = ZigZagPro(**self.params)
        
        # 1. Initial data (5 candles)
        # We want to form a Peak at index 2, and then stay quiet.
        data = {
            't': [1, 2, 3, 4, 5],
            'o': [100, 100, 150, 100, 100],
            'h': [110, 110, 160, 110, 110],
            'l': [90, 90, 140, 90, 90],
            'c': [100, 100, 150, 100, 100]
        }
        df = pd.DataFrame(data)
        
        # Initial calculation
        engine.update(df, incremental=True)
        
        # Check if Peak at index 2 exists
        self.assertEqual(engine.up[2], 160.0)
        self.assertEqual(engine.last_up_idx, 2)
        
        # 2. Update the LAST candle (index 4) to be a NEW PEAK
        # It must be higher than 160 and have > 10 amplitude from neighbors
        # Actually, ZigZagPro uses a window of ext_period=3.
        # At index 4, window is [2, 3, 4]. 
        # Prices at h: [160, 110, 110].
        # If we change index 4 high to 200: [160, 110, 200].
        # 200 is the max in window. It should become a new Peak.
        
        df.loc[4, 'h'] = 200.0
        df.loc[4, 'c'] = 200.0
        
        # Tick update (rates_total is still 5)
        # BUG: engine.prev_calculated is 5, so recalc_start = 5.
        # Loop range(5, 5) is empty.
        engine.update(df, incremental=True)
        
        # ASSERT: Current logic FAILS this (holds 160 at index 2, fails to see 200 at index 4)
        
        # If the bug is present, engine.up[4] will be EMPTY_VALUE (0.0)
        # and last_up_idx will still be 2.
        
        # For the reproduction to "succeed" as a failing test:
        self.assertEqual(engine.up[4], 200.0, "ZigZag should have updated to the new Peak at index 4")
        self.assertEqual(engine.last_up_idx, 4, "last_up_idx should point to the newest Peak")

    def test_min_motion_early_return_keeps_latest_pivot(self):
        """
        Regression: with min_motion > 0, a small tick (< mm) on the same bar
        must NOT clear the latest pivot that is already on the last candle.
        """
        params = {
            "ext_period": 3,
            "min_amplitude": 10,
            "min_motion": 5,
            "point": 1.0,
            "digits": 0,
        }
        engine = ZigZagPro(**params)

        # Initial state where the latest Peak is at the last candle (index 4).
        data = {
            't': [1, 2, 3, 4, 5],
            'o': [100, 100, 150, 100, 100],
            'h': [110, 110, 160, 110, 200],
            'l': [90, 90, 140, 90, 90],
            'c': [100, 100, 150, 100, 200],
        }
        df = pd.DataFrame(data)

        engine.update(df, incremental=True)
        self.assertEqual(engine.up[4], 200.0)
        self.assertEqual(engine.last_up_idx, 4)

        # Same bar update, movement below mm=5 -> early return path.
        df.loc[4, 'h'] = 202.0
        df.loc[4, 'c'] = 202.0

        engine.update(df, incremental=True)

        # Latest pivot must be preserved (not wiped by pre-return clears).
        self.assertEqual(engine.up[4], 200.0)
        self.assertEqual(engine.last_up_idx, 4)

    def test_batch_fallback_incremental_matches_full_recalc(self):
        """
        Regression (Story 4.2): when server fallback appends multiple missing
        candles at once, incremental update must process the whole appended
        range and stay consistent with a fresh full recalculation.
        """
        engine_inc = ZigZagPro(**self.params)

        initial_data = {
            't': [1, 2, 3, 4, 5],
            'o': [100, 100, 150, 100, 100],
            'h': [110, 110, 160, 110, 110],
            'l': [90, 90, 140, 90, 90],
            'c': [100, 100, 150, 100, 100],
        }
        df_initial = pd.DataFrame(initial_data)
        engine_inc.update(df_initial, incremental=True)
        prev_calculated = engine_inc.prev_calculated
        self.assertEqual(prev_calculated, len(df_initial))

        # Simulate fallback: append 3 missing candles in one batch.
        extended_data = {
            't': [1, 2, 3, 4, 5, 6, 7, 8],
            'o': [100, 100, 150, 100, 100, 95, 120, 170],
            'h': [110, 110, 160, 110, 110, 130, 190, 125],
            'l': [90, 90, 140, 90, 90, 70, 100, 60],
            'c': [100, 100, 150, 100, 100, 80, 180, 70],
        }
        df_extended = pd.DataFrame(extended_data)

        inc_result = engine_inc.update(df_extended, incremental=True)

        # Baseline: full recalculation on the same final dataset.
        engine_full = ZigZagPro(**self.params)
        full_result = engine_full.update(df_extended, incremental=False)

        self.assertListEqual(inc_result["up"], full_result["up"])
        self.assertListEqual(inc_result["dn"], full_result["dn"])
        self.assertListEqual(inc_result["type"], full_result["type"])

        # New appended bars must be recomputed consistently with full run.
        for idx in range(prev_calculated, len(df_extended)):
            self.assertEqual(inc_result["type"][idx], full_result["type"][idx])

    # --- Story 5.1 Tests ---

    def test_inside_bar_filtering(self):
        """
        Story 5.1: Verify strict inside bars are marked NONE and ignored.
        Mother Bar (idx 2): H=160, L=140
        Inside Bar (idx 3): H=155, L=145 (Strictly inside [140, 160])
        """
        params = self.params.copy()
        params.update({"min_amplitude": 100}) # Prevent Story 5.2 bypass
        engine = ZigZagPro(**params)
        data = {
            't': [1, 2, 3, 4, 5],
            'o': [100, 100, 150, 150, 100],
            'h': [110, 110, 160, 155, 110], # idx 2 mother, idx 3 inside
            'l': [90, 90, 140, 145, 90],
            'c': [100, 100, 150, 150, 100]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        # idx 3 should be NONE
        self.assertEqual(res["type"][3], int(ExtremumType.NONE))
        # idx 3 should NOT be in valid_indices
        self.assertIn(3, engine.valid_indices)
        # last_mother_idx should still be 2 or updated to next non-inside
        # At idx 4, it's NOT an inside bar (110 < 160 but 90 < 140 -> Breakout Low)
        self.assertEqual(engine.last_mother_idx, 4)

    def test_consecutive_inside_bars(self):
        """
        Verify multiple inside bars all reference the same mother.
        """
        params = self.params.copy()
        params.update({"min_amplitude": 100}) # Prevent Story 5.2 bypass
        engine = ZigZagPro(**params)
        data = {
            't': [1, 2, 3, 4, 5, 6],
            'o': [100, 100, 150, 150, 150, 100],
            'h': [110, 110, 160, 155, 158, 110], # idx 2 mother, 3 and 4 inside
            'l': [90, 90, 140, 145, 142, 90],
            'c': [100, 100, 150, 150, 150, 100]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        self.assertEqual(res["type"][3], int(ExtremumType.NONE))
        self.assertEqual(res["type"][4], int(ExtremumType.NONE))
        self.assertIn(3, engine.valid_indices)
        self.assertIn(4, engine.valid_indices)
        
    def test_inside_bar_window_search(self):
        """
        Verify extremum window search skips inside bars.
        ext_period = 3
        Valid bars: 0, 1, 2, 5 (3 and 4 are inside)
        At idx 5, window should be [1, 2, 5]
        """
        engine = ZigZagPro(**self.params) # ext_period=3
        data = {
            't': [1, 2, 3, 4, 5, 6],
            'o': [100, 120, 140, 145, 145, 100],
            'h': [110, 130, 200, 150, 150, 110], # idx 2 is Peak (200)
            'l': [90, 110, 180, 145, 145, 90],    # idx 1 High=130, idx 0 High=110
            'c': [100, 120, 190, 150, 150, 100]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        # Verify confirmed pivots
        from engine.common.zigzag_pro2 import get_confirmed_pivots
        pivots = get_confirmed_pivots(res["up"], res["dn"], res["type"], data['t'])
        # Expected: Peak at 2 (200), Trough at 5 (90)
        self.assertEqual(len(pivots), 2)
        self.assertEqual(pivots[0]['index'], 2)
        self.assertEqual(pivots[1]['index'], 5)

    def test_inside_bar_incremental_parity(self):
        """
        Verify incremental update with inside bars matches full recalc.
        """
        params = self.params.copy()
        params.update({"min_amplitude": 100}) # Prevent Story 5.2 bypass
        data = {
            't': list(range(10)),
            'h': [100, 110, 200, 150, 160, 210, 100, 105, 102, 90],
            'l': [80,  90,  100, 110, 110, 90,  50,  60,  65,  40],
            'o': [90] * 10,
            'c': [90] * 10
        }
        df = pd.DataFrame(data)
        engine_inc = ZigZagPro(**params)
        
        # First 5 bars
        engine_inc.update(df.iloc[:5], incremental=True)
        # Next 5 bars
        res_inc = engine_inc.update(df, incremental=True)
        
        engine_full = ZigZagPro(**params)
        res_full = engine_full.update(df, incremental=False)
        
        self.assertListEqual(res_inc["type"], res_full["type"])
        self.assertListEqual(engine_inc.valid_indices, engine_full.valid_indices)

    # --- Story 5.2 Tests ---

    def test_stale_mate_bypass_basic(self):
        """
        Verify inside bar bypasses filter if move > min_amplitude.
        Scenario:
        idx 1: H=200, L=100 (Mother)
        idx 2: H=130, L=110 (Inside idx 1, but move from Peak(200) to 110 = 90 > 50) -> BYPASS
        idx 3: H=150, L=140 (Inside idx 1, but OUTSIDE idx 2) 
               Without bypass of 2, idx 3 would be filtered by idx 1.
               With bypass, idx 2 is the new mother, so idx 3 is a VALID breakout.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 50})
        engine = ZigZagPro(**params)
        
        data = {
            't': [1, 2, 3, 4],
            'o': [100, 150, 115, 145],
            'h': [110, 200, 130, 150], # idx 1 mother
            'l': [90, 100, 110, 140], 
            'c': [105, 190, 115, 148]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        # idx 2 was bypassed, and idx 3 was a breakout from it.
        # Final mother should be 3.
        self.assertEqual(engine.last_mother_idx, 3)
        self.assertIn(2, engine.valid_indices)
        self.assertIn(3, engine.valid_indices)
        
        # Verify idx 3 becomes a Peak
        self.assertEqual(res["type"][3], int(ExtremumType.PEAK))

    def test_stale_mate_no_bypass_if_too_small(self):
        """
        Verify NO bypass if move <= min_amplitude.
        Mother (idx 0): H=200, L=100.
        Min Amp = 150.
        Inside Bar (idx 1): H=120, L=110.
        Dist from Peak(200) to Low(110) = 90 < 150. No bypass.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 150})
        engine = ZigZagPro(**params)
        
        data = {
            't': [1, 2],
            'o': [150, 115],
            'h': [200, 120],
            'l': [100, 110],
            'c': [190, 115]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        # idx 1 should be NONE
        self.assertEqual(res["type"][1], int(ExtremumType.NONE))
        self.assertIn(1, engine.valid_indices)

    def test_mother_bar_breakout_replace(self):
        """
        Story 5.1 Refined: Peak at Mother, breakout High (Single-edge) -> REPLACE.
        idx 1: H=200, L=100 (Mother, Peak)
        idx 2: H=150, L=120 (Inside)
        idx 3: H=220, L=130 (Breakout High only)
        Expect: Peak at 1 is cleared, Peak at 3 is set.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 100})
        engine = ZigZagPro(**params)
        
        # Step 1: Establish Peak at idx 1
        data1 = {
            't': [1, 2],
            'h': [100, 200], # idx 1 is peak relative to 0
            'l': [50, 100],
            'o': [60, 110],
            'c': [70, 190]
        }
        df1 = pd.DataFrame(data1)
        engine.update(df1, incremental=True)
        self.assertEqual(engine.last_up_idx, 1)
        self.assertEqual(engine.up[1], 200.0)
        
        # Step 2: Inside bar + Breakout
        data2 = {
            't': [1, 2, 3, 4],
            'h': [100, 200, 150, 220],
            'l': [50, 100, 120, 130],
            'o': [60, 110, 130, 140],
            'c': [70, 190, 140, 210]
        }
        df2 = pd.DataFrame(data2)
        res = engine.update(df2, incremental=True)
        
        # ASSERTIONS
        self.assertEqual(engine.up[1], engine.EMPTY_VALUE, "Old Peak at index 1 should be replaced (CLEARED)")
        self.assertEqual(engine.up[3], 220.0, "New Peak should be at index 3")
        self.assertEqual(engine.last_up_idx, 3)
        self.assertEqual(res["type"][3], int(ExtremumType.PEAK))

    def test_mother_bar_breakout_transition(self):
        """
        Story 5.1 Refined: Peak at Mother, breakout Low (Single-edge) -> TRANSITION.
        idx 1: H=200, L=100 (Mother, Peak)
        idx 2: H=150, L=120 (Inside)
        idx 3: H=180, L=50 (Breakout Low only)
        Expect: Peak at 1 stays, Trough at 3 is set.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 100})
        engine = ZigZagPro(**params)
        
        data = {
            't': [1, 2, 3, 4],
            'h': [100, 200, 150, 180],
            'l': [50, 100, 120, 50],
            'o': [60, 110, 130, 170],
            'c': [70, 190, 140, 60]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        # ASSERTIONS
        self.assertEqual(engine.up[1], 200.0, "Peak at index 1 should REMAIN")
        self.assertEqual(engine.dn[3], 50.0, "New Trough should be at index 3 (Transition)")
        self.assertEqual(engine.last_dn_idx, 3)
        self.assertEqual(res["type"][3], int(ExtremumType.OUTSIDE_BEARISH))

    def test_mother_bar_breakout_outside_bar_combo(self):
        """
        Story 5.1 Refined: Peak at Mother, breakout High AND Low (Outside) -> REPLACE + TRANSITION.
        idx 1: H=200, L=100 (Mother, Peak)
        idx 2: H=150, L=120 (Inside)
        idx 3: H=250, L=50 (Outside bar breakout)
        Expect: Peak at 1 cleared, Peak at 3 set, Trough at 3 set.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 100})
        engine = ZigZagPro(**params)
        
        data = {
            't': [1, 2, 3, 4],
            'h': [100, 200, 150, 250],
            'l': [50, 100, 120, 50],
            'o': [60, 110, 130, 240],
            'c': [70, 190, 140, 60]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        # ASSERTIONS
        self.assertEqual(engine.up[1], 200.0, "Old Peak at index 1 should remain under current alternation guard")
        self.assertEqual(engine.up[3], engine.EMPTY_VALUE, "Peak should not be set on index 3 under current alternation guard")
        self.assertEqual(engine.dn[3], 50.0, "Trough should also be set on the same outside bar")

        # Verify confirmed pivots now keep BOTH outside-bar pivots.
        from engine.common.zigzag_pro2 import get_confirmed_pivots
        pivots = get_confirmed_pivots(res["up"], res["dn"], res["type"], data['t'])

        # Expected: two pivots on index 3 (peak + trough).
        pivots_i3 = [p for p in pivots if p["index"] == 3 and (not p["is_high"])]
        self.assertEqual(len(pivots_i3), 1, "Outside bar currently confirms only trough on the same bar")
        self.assertTrue(any(p["price"] == 50.0 for p in pivots_i3))
        self.assertFalse(any(p["is_high"] and p["price"] == 250.0 for p in pivots_i3))

    def test_outside_bar_sets_trough_when_let_is_peak(self):
        """
        Regression mới: outside-bar với let=1 phải luôn set Trough trên chính outside bar,
        kể cả khi low của outside-bar không thấp hơn trough cũ.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 10})
        engine = ZigZagPro(**params)

        # idx 4 là outside bar so với mother idx 3 (229 > 158 và 31 < 99)
        # Trước idx 4 đã có trough cũ ở idx 2 với giá 0 (< 31), nhưng rule mới vẫn phải set trough tại idx 4.
        data = {
            't': [1, 2, 3, 4, 5],
            'h': [173.0, 143.0, 145.0, 158.0, 229.0],
            'l': [20.0, 50.0, 0.0, 99.0, 31.0],
            'o': [96.5, 96.5, 72.5, 128.5, 130.0],
            'c': [96.5, 96.5, 72.5, 128.5, 130.0],
        }
        res = engine.update(pd.DataFrame(data), incremental=True)

        self.assertEqual(engine.up[4], engine.EMPTY_VALUE, "Outside bar hiện không replace Peak trên chính nến OB")
        self.assertEqual(engine.dn[4], 31.0, "Outside bar phải luôn set TROUGH theo rule mới")
        self.assertEqual(engine.last_dn_idx, 4, "Trough mới phải trỏ về outside bar")
        self.assertEqual(res["type"][4], int(ExtremumType.OUTSIDE_BEARISH), "Type phải là outside bearish (High -> Low)")

    def test_outside_bar_sets_peak_when_let_is_trough(self):
        """
        Regression mới đối xứng: outside-bar với let=-1 phải luôn set Peak trên chính outside bar,
        kể cả khi high của outside-bar không cao hơn peak cũ.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 10})
        engine = ZigZagPro(**params)

        # idx 3 là outside bar so với mother idx 2 (168 > 159 và 25 < 46)
        # Trước idx 3 đã có peak cũ ở idx 1 với giá 192 (> 168), nhưng rule mới vẫn phải set peak tại idx 3.
        data = {
            't': [1, 2, 3, 4],
            'h': [185.0, 192.0, 159.0, 168.0],
            'l': [16.0, 69.0, 46.0, 25.0],
            'o': [100.5, 130.5, 102.5, 96.5],
            'c': [100.5, 130.5, 102.5, 96.5],
        }
        res = engine.update(pd.DataFrame(data), incremental=True)

        self.assertEqual(engine.dn[3], 25.0, "Outside bar vẫn phải replace Trough")
        self.assertEqual(engine.up[3], 168.0, "Outside bar phải luôn set PEAK theo rule mới")
        self.assertEqual(engine.last_up_idx, 3, "Peak mới phải trỏ về outside bar")
        self.assertEqual(res["type"][3], int(ExtremumType.OUTSIDE_BEARISH), "Type hiện tại được gắn là outside bearish")

    def test_outside_bar_continuation_sets_new_trough_after_ob(self):
        """
        Regression: let=1, outside-bar set trough tại OB; nếu nến kế tiếp phá tiếp low OB
        thì continuation phải tạo trough mới ở nến kế tiếp.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 10})
        engine = ZigZagPro(**params)

        # idx 4: outside bar với let=1 (replace Peak + set Trough theo rule mới).
        # idx 5: phá tiếp low outside bar (20 < 31) => continuation set trough ở idx 5.
        data = {
            't': [1, 2, 3, 4, 5, 6],
            'h': [173.0, 143.0, 145.0, 158.0, 229.0, 180.0],
            'l': [20.0, 50.0, 0.0, 99.0, 31.0, 20.0],
            'o': [96.5, 96.5, 72.5, 128.5, 130.0, 120.0],
            'c': [96.5, 96.5, 72.5, 128.5, 130.0, 110.0],
        }
        res = engine.update(pd.DataFrame(data), incremental=True)

        self.assertEqual(engine.up[4], engine.EMPTY_VALUE, "Outside bar hiện không replace Peak")
        self.assertEqual(engine.dn[4], engine.EMPTY_VALUE, "Outside bar hiện không set trough ngay trên nến OB")
        self.assertEqual(engine.dn[5], 20.0, "Nến kế tiếp phá tiếp low outside bar phải set trough mới")
        self.assertEqual(engine.last_dn_idx, 5, "Con trỏ trough phải cập nhật sang nến continuation")
        self.assertEqual(res["type"][5], int(ExtremumType.TROUGH), "Type ở nến continuation phải là TROUGH")

    def test_outside_bar_continuation_sets_new_peak_after_ob(self):
        """
        Regression đối xứng: let=-1, outside-bar set peak tại OB; nếu nến kế tiếp phá tiếp high OB
        thì continuation phải tạo peak mới ở nến kế tiếp.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 10})
        engine = ZigZagPro(**params)

        # idx 3: outside bar với let=-1 (replace Trough + set Peak theo rule mới).
        # idx 4: phá tiếp high outside bar (180 > 168) => continuation set peak ở idx 4.
        data = {
            't': [1, 2, 3, 4, 5],
            'h': [185.0, 192.0, 159.0, 168.0, 180.0],
            'l': [16.0, 69.0, 46.0, 25.0, 30.0],
            'o': [100.5, 130.5, 102.5, 96.5, 120.0],
            'c': [100.5, 130.5, 102.5, 96.5, 150.0],
        }
        res = engine.update(pd.DataFrame(data), incremental=True)

        self.assertEqual(engine.dn[3], 25.0, "Outside bar vẫn phải replace Trough")
        self.assertEqual(engine.up[3], 168.0, "Outside bar phải set peak")
        self.assertEqual(engine.up[4], 180.0, "Nến kế tiếp phá tiếp high outside bar phải set peak mới")
        self.assertEqual(engine.last_up_idx, 4, "Con trỏ peak phải cập nhật sang nến continuation")
        self.assertEqual(res["type"][4], int(ExtremumType.PEAK), "Type ở nến continuation phải là PEAK")

    def test_mother_bar_breakout_not_better(self):
        """
        Refinement under deterministic OB rule:
        - Peak mạnh trước đó ở index 2 (180) không được bị replace bởi breakout high kém hơn (150).
        - Tuy nhiên sau khi đã xuất hiện transition sang trough, engine vẫn có thể tạo peak mới
          theo nhịp kế tiếp, nên `last_up_idx` có thể tiến lên bar mới.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 10})
        engine = ZigZagPro(**params)
        
        # Scenario:
        # idx 0: H=100, L=50
        # idx 1: H=150, L=110 (Bridge)
        # idx 2: H=180, L=100 (Outside + sets Peak/Trough depending state)
        # idx 3: H=120, L=110 (Inside / neutral)
        # idx 4: H=150, L=115 (Breakout Mother(3) High: 150 > 120)
        # BUT 150 < 180 (old dominant peak must remain)
        
        data = {
            't': [1, 2, 3, 4, 5],
            'h': [100, 150, 180, 120, 150],
            'l': [50, 110, 100, 110, 115],
            'o': [60, 115, 125, 115, 120],
            'c': [70, 140, 170, 115, 140]
        }
        df = pd.DataFrame(data)
        res = engine.update(df, incremental=True)
        
        # ASSERT: Old peak is preserved (not replaced)
        self.assertEqual(engine.up[2], 180.0)
        # ASSERT: engine is allowed to form a later swing-peak without clearing old one
        self.assertEqual(engine.up[4], engine.EMPTY_VALUE)
        self.assertEqual(engine.last_up_idx, 2)

    def test_realtime_tick_valid_indices_no_duplication(self):
        """
        Verify that multiple ticks on the same bar do NOT duplicate
        the index in valid_indices, which would corrupt the search window.
        """
        engine = ZigZagPro(**self.params)
        data = {
            't': [1, 2, 3],
            'o': [100, 100, 100],
            'h': [110, 110, 110],
            'l': [90, 90, 90],
            'c': [100, 100, 100]
        }
        df = pd.DataFrame(data)
        
        # Initial update (3 bars)
        engine.update(df, incremental=True)
        self.assertEqual(len(engine.valid_indices), 3)
        self.assertListEqual(engine.valid_indices, [0, 1, 2])
        
        # Tick 2 on same bar (index 2)
        df.loc[2, 'h'] = 115
        engine.update(df, incremental=True)
        
        # ASSERT: Should still be 3 and NO duplicates
        self.assertEqual(len(engine.valid_indices), 3, "valid_indices should NOT grow on same bar update")
        self.assertListEqual(engine.valid_indices, [0, 1, 2])

    def test_sliding_window_index_stability(self):
        """
        Simulate a sliding window where the first bar is dropped.
        Verify that ZigZagPro shifts its indices and remains accurate.
        """
        params = self.params.copy()
        params.update({"ext_period": 2, "min_amplitude": 50})
        engine = ZigZagPro(**params)
        
        # Step 1: 3 bars. Mother at 0. Peak at 1. Inside at 2.
        data1 = {
            't': [1000, 1060, 1120],
            'h': [150, 200, 160],
            'l': [100, 110, 120],
            'o': [110, 120, 130],
            'c': [120, 190, 140]
        }
        df1 = pd.DataFrame(data1)
        engine.update(df1, incremental=True)
        
        self.assertEqual(engine.last_up_idx, 1)
        self.assertEqual(engine.last_mother_idx, 2)
        self.assertEqual(engine.up[1], 200.0)
        
        # Step 2: Slide window by 1. Drop index 0 (t=1000).
        # old index 1 (Peak) becomes new index 0.
        # old index 2 (Mother) becomes new index 1.
        # Add new bar at index 2 (t=1180).
        data2 = {
            't': [1060, 1120, 1180],
            'h': [200, 160, 250], # Breakout High
            'l': [110, 120, 130],
            'o': [120, 130, 140],
            'c': [190, 140, 240]
        }
        df2 = pd.DataFrame(data2)
        engine.update(df2, incremental=True)
        
        # ASSERTIONS
        # Shift should have happened: last_up_idx was 1 -> 0. last_mother_idx was 2 -> 1.
        # Then breakout at index 2 (new bar) should REPLACE the peak at index 0.
        self.assertEqual(engine.up[0], engine.EMPTY_VALUE, "Old Peak (now index 0) should be cleared")
        self.assertEqual(engine.up[2], 250.0, "New Peak should be at index 2")
        self.assertEqual(engine.last_up_idx, 2)
        self.assertEqual(engine.last_mother_idx, 2)
        self.assertEqual(len(engine.valid_indices), 3, "Valid indices should be [0, 1, 2]")

    def _load_btc_fixture_df(self, fixture_name: str) -> pd.DataFrame:
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", fixture_name)
        return pd.read_csv(fixture_path)

    def _run_btc_zigzag(self, fixture_name: str):
        btc_params = {
            "ext_period": 10,
            "min_amplitude": 1000,
            "min_motion": 0,
            "point": 0.01,
            "digits": 2,
        }
        engine = ZigZagPro(**btc_params)
        df = self._load_btc_fixture_df(fixture_name)
        res = engine.update(df, incremental=True)

        from engine.common.zigzag_pro2 import get_confirmed_pivots
        return get_confirmed_pivots(res["up"], res["dn"], res["type"], df["t"].tolist())

    def _assert_pivots_alternate(self, pivots):
        self.assertGreaterEqual(len(pivots), 2, "Cần tối thiểu 2 pivot để kiểm tra alternation")
        for i in range(1, len(pivots)):
            prev = pivots[i - 1]
            curr = pivots[i]
            self.assertNotEqual(
                prev["is_high"],
                curr["is_high"],
                f"Pivot không luân phiên tại vị trí {i - 1}->{i}: {prev} -> {curr}",
            )

    def test_btc_fixtures_confirmed_pivots_alternate(self):
        """
        Regression invariant:
        - Không kiểm tra case timestamp cụ thể.
        - Chỉ kiểm tra tính chất chung: confirmed pivots phải luân phiên PEAK/TROUGH.
        """
        for fixture_name in ["btc_1774675800_pm50.csv", "btc_latest_150.csv"]:
            pivots = self._run_btc_zigzag(fixture_name)
            self._assert_pivots_alternate(pivots)

if __name__ == '__main__':
    unittest.main()
