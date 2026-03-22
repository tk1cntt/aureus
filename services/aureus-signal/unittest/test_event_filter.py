import unittest
from unittest.mock import MagicMock
from engine.event_filter import has_structural_event

class TestEventFilter(unittest.TestCase):
    def setUp(self):
        self.c_state = MagicMock()
        self.c_state.transient_signals = {}
        self.trade_manager = MagicMock()
        self.trade_manager.last_tick_events = []

    def test_no_events_returns_false(self):
        self.assertFalse(has_structural_event(self.c_state, self.trade_manager))

    def test_choch_up_triggers(self):
        self.c_state.transient_signals = {'choch_up': {'tag': 'choch_up', 't': 1000}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_choch_down_triggers(self):
        self.c_state.transient_signals = {'choch_down': {'tag': 'choch_down', 't': 1000}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_bos_up_triggers(self):
        self.c_state.transient_signals = {'bos_up': {'tag': 'bos_up', 't': 1000}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_bos_down_triggers(self):
        self.c_state.transient_signals = {'bos_down': {'tag': 'bos_down', 't': 1000}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_sweep_bull_triggers(self):
        self.c_state.transient_signals = {'sweep_bull': {'tag': 'sweep_bull', 't': 1000}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_sweep_bear_triggers(self):
        self.c_state.transient_signals = {'sweep_bear': {'tag': 'sweep_bear', 't': 1000}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_ob_bull_new_triggers(self):
        self.c_state.transient_signals = {'ob_bull_new': {'ob_type': 'BULLISH'}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_ob_bull_mitigated_triggers(self):
        self.c_state.transient_signals = {'ob_bull_mitigated': {'ob_type': 'BULLISH'}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_ob_bear_mitigated_triggers(self):
        self.c_state.transient_signals = {'ob_bear_mitigated': {'ob_type': 'BEARISH'}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_fvg_bull_new_triggers(self):
        self.c_state.transient_signals = {'fvg_bull_new': {'direction': 'BULLISH'}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_fvg_bear_mitigated_triggers(self):
        self.c_state.transient_signals = {'fvg_bear_mitigated': {'direction': 'BEARISH'}}
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_unknown_tag_does_not_trigger(self):
        self.c_state.transient_signals = {'random_signal': {'data': True}}
        self.assertFalse(has_structural_event(self.c_state, self.trade_manager))

    def test_order_opened_triggers(self):
        self.c_state.transient_signals = {}
        self.trade_manager.last_tick_events = ["ORDER_OPENED"]
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_sl_hit_triggers(self):
        self.c_state.transient_signals = {}
        self.trade_manager.last_tick_events = ["SL_HIT"]
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_tp_hit_triggers(self):
        self.c_state.transient_signals = {}
        self.trade_manager.last_tick_events = ["TP_HIT"]
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

    def test_combined_structural_and_trade(self):
        self.c_state.transient_signals = {'choch_up': {'tag': 'choch_up'}}
        self.trade_manager.last_tick_events = ["ORDER_OPENED"]
        self.assertTrue(has_structural_event(self.c_state, self.trade_manager))

if __name__ == '__main__':
    unittest.main()
