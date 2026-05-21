"""Tests for indicator_snapshot.py — build_indicator_snapshot_for_telegram."""
from engine.indicator_snapshot import build_indicator_snapshot_for_telegram


class MockState:
    """Minimal mock of SymbolState for testing."""
    symbol = 'XAUUSD'
    emas = {}
    atr = None
    vol_sma_20 = None
    htf_trend = None
    transient_signals = {}
    tpo_profile = {}


def _make_state(**overrides):
    """Factory for mock state with sensible defaults."""
    state = MockState()
    state.emas = overrides.pop('emas', {
        21: {'current': 2341.20, 'prev': 2340.0, 'slope': 0.0005},
        34: {'current': 2343.50, 'prev': 2342.0, 'slope': 0.0006},
        55: {'current': 2346.80, 'prev': 2345.0, 'slope': 0.0008},
        89: {'current': 2351.00, 'prev': 2350.0, 'slope': 0.0004},
        100: {'current': 2355.40, 'prev': 2354.0, 'slope': 0.0006},
        200: {'current': 2370.10, 'prev': 2369.0, 'slope': 0.0005},
    })
    state.atr = overrides.pop('atr', 12.34)
    state.vol_sma_20 = overrides.pop('vol_sma_20', 1500.0)
    state.htf_trend = overrides.pop('htf_trend', 'BULLISH')
    state.transient_signals = overrides.pop('transient_signals', {})
    return state


def test_returns_expected_keys():
    """Verify snapshot has expected keys including MTF candle color + BB fields."""
    state = _make_state()
    snap = build_indicator_snapshot_for_telegram(state)
    expected = {
        'emas', 'atr_14', 'vol_sma_20', 'htf_trend', 'cisd_mtf', 'digits',
        'tpo_d0', 'tpo_d1', 'tpo_d2', 'tpo_d3', 'tpo_h1', 'tpo_m30',
        'candle_color_d1', 'candle_color_h1', 'candle_color_m30', 'candle_color_m15', 'candle_color_m5',
        'bb_m1', 'bb_m5', 'bb_m15', 'bb_m30', 'bb_h1',
    }
    assert set(snap.keys()) == expected
    for key in ['bb_m1', 'bb_m5', 'bb_m15', 'bb_m30', 'bb_h1']:
        assert key in snap
    for key in ['candle_color_d1', 'candle_color_h1', 'candle_color_m30', 'candle_color_m15', 'candle_color_m5']:
        assert key in snap
    assert snap['digits'] == 2


def test_ema_values_extracted():
    """Verify EMA values are read from state.emas."""
    state = _make_state()
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['emas']['periods'] == [21, 34, 55, 89, 100, 200]
    assert snap['emas']['values'][0] == 2341.20
    assert snap['emas']['values'][-1] == 2370.10


def test_atr_value_extracted():
    """Verify ATR is read from state.atr."""
    state = _make_state(atr=15.67)
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['atr_14'] == 15.67


def test_vol_sma_extracted():
    """Verify Volume SMA is read from state.vol_sma_20."""
    state = _make_state(vol_sma_20=2000.0)
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['vol_sma_20'] == 2000.0


def test_htf_trend_extracted():
    """Verify HTF Trend is read from state.htf_trend."""
    state = _make_state(htf_trend='BEARISH')
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['htf_trend'] == 'BEARISH'


def test_missing_values_are_none():
    """Verify missing/None values remain None in snapshot."""
    state = _make_state()
    state.emas = {}
    state.atr = None
    state.vol_sma_20 = None
    state.htf_trend = None
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['atr_14'] is None
    assert snap['vol_sma_20'] is None
    assert snap['htf_trend'] is None
    assert all(v is None for v in snap['emas']['values'])


def test_no_market_session_key():
    """Verify market_session is NOT in snapshot (D-14)."""
    state = _make_state()
    snap = build_indicator_snapshot_for_telegram(state)
    assert 'market_session' not in snap
    assert 'session' not in snap


def test_ema_cross_up_marker():
    """Verify cross_up transient signal produces 📈 emoji."""
    state = _make_state()
    state.transient_signals['ema_21_up'] = {
        'value': 2341.20,
        'data': {'cross': 'ema_21_cross_up'},
    }
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['emas']['cross_markers'][0] == " \U0001F4C8"


def test_ema_cross_down_marker():
    """Verify cross_down transient signal produces 📉 emoji."""
    state = _make_state()
    state.transient_signals['ema_34_down'] = {
        'value': 2343.50,
        'data': {'cross': 'ema_34_cross_down'},
    }
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['emas']['cross_markers'][1] == " \U0001F4C9"


def test_no_cross_empty_marker():
    """Verify no cross produces empty string marker."""
    state = _make_state()
    snap = build_indicator_snapshot_for_telegram(state)
    assert all(m == "" for m in snap['emas']['cross_markers'])


def test_all_values_are_primitives():
    """Verify snapshot contains only primitive types (JSON-serializable)."""
    import json
    state = _make_state()
    snap = build_indicator_snapshot_for_telegram(state)
    # Should not raise — all values are JSON-serializable
    json.dumps(snap)


def test_handles_missing_emas_attribute():
    """Verify function works when state has no emas attribute."""
    state = _make_state()
    del state.emas
    snap = build_indicator_snapshot_for_telegram(state)
    assert all(v is None for v in snap['emas']['values'])


def test_cisd_mtf_extracted_from_transient_signals():
    """Verify CISD MTF status is extracted from transient_signals (only bullish/bearish, no idle)."""
    state = _make_state()
    state.transient_signals = {
        'cisd_m5_bullish': {'tf': 'M5', 'status': 'bullish'},
        'cisd_m15_bearish': {'tf': 'M15', 'status': 'bearish'},
        'cisd_m30_idle': {'tf': 'M30', 'status': 'idle'},  # should be ignored
    }
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['cisd_mtf'] == {'M5': 'bullish', 'M15': 'bearish'}


def test_cisd_mtf_none_when_no_tags():
    """Verify CISD MTF is None when no CISD tags present."""
    state = _make_state()
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['cisd_mtf'] is None


def test_all_values_primitives_with_cisd_mtf():
    """Verify snapshot with CISD MTF is still JSON-serializable."""
    import json
    state = _make_state()
    state.transient_signals = {
        'cisd_m5_bullish': {'tf': 'M5', 'status': 'bullish'},
    }
    snap = build_indicator_snapshot_for_telegram(state)
    json.dumps(snap)  # Should not raise


def test_tpo_profile_fields_are_included():
    state = _make_state()
    state.tpo_profile = {
        'tpo_d0': {'POC': 2010.0, 'VAH': 2012.0, 'VAL': 2008.0},
        'tpo_d1': {'POC': 2010.1, 'VAH': 2012.3, 'VAL': 2008.7},
        'tpo_d2': {'POC': 2007.1, 'VAH': 2009.3, 'VAL': 2005.7},
        'tpo_d3': {'POC': 2004.1, 'VAH': 2006.3, 'VAL': 2002.7},
        'tpo_h1': {'POC': 2009.9, 'VAH': 2011.0, 'VAL': 2008.2},
        'tpo_m30': {'POC': 2010.0, 'VAH': 2010.8, 'VAL': 2009.1},
    }
    snap = build_indicator_snapshot_for_telegram(state)
    for key in ('tpo_d0', 'tpo_d1', 'tpo_d2', 'tpo_d3'):
        assert snap[key] == state.tpo_profile[key]
    assert snap['tpo_h1'] == state.tpo_profile['tpo_h1']
    assert snap['tpo_m30'] == state.tpo_profile['tpo_m30']


def test_tpo_profile_shape_metadata_is_preserved_for_display_only():
    state = _make_state()
    state.tpo_profile = {
        'tpo_d1': {
            'POC': 2010.1,
            'VAH': 2012.3,
            'VAL': 2008.7,
            'shape': 'D',
            'shape_confidence_pct': 82.5,
            'shape_scores_pct': {'D': 82.5, 'B': 7.5, 'p': 5.0, 'b': 5.0},
        },
        'tpo_h1': {
            'POC': 2009.9,
            'VAH': 2011.0,
            'VAL': 2008.2,
            'shape': 'B',
            'shape_confidence_pct': 74.0,
            'shape_scores_pct': {'D': 10.0, 'B': 74.0, 'p': 9.0, 'b': 7.0},
        },
        'tpo_m30': {
            'POC': 2010.0,
            'VAH': 2010.8,
            'VAL': 2009.1,
            'shape': 'p',
            'shape_confidence_pct': 66.25,
            'shape_scores_pct': {'D': 12.0, 'B': 11.75, 'p': 66.25, 'b': 10.0},
        },
    }
    snap = build_indicator_snapshot_for_telegram(state)
    for key in ('tpo_d0', 'tpo_d1', 'tpo_d2', 'tpo_d3'):
        assert key in snap
    for key in ('tpo_d1', 'tpo_h1', 'tpo_m30'):
        assert snap[key] == state.tpo_profile[key]
        assert 'shape' in snap[key]
        assert 'shape_confidence_pct' in snap[key]
        assert 'shape_scores_pct' in snap[key]
    assert 'shape_score_weight' not in snap
    assert 'strategy_score' not in snap
    assert 'shape_signal' not in snap


def test_tpo_profile_malformed_blocks_are_safe():
    state = _make_state()
    state.tpo_profile = {'tpo_d0': 'bad-block', 'tpo_d1': 'bad-block', 'tpo_d2': None, 'tpo_d3': ['bad'], 'tpo_h1': None, 'tpo_m30': ['bad']}
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['tpo_d0'] is None
    assert snap['tpo_d1'] is None
    assert snap['tpo_d2'] is None
    assert snap['tpo_d3'] is None
    assert snap['tpo_h1'] is None
    assert snap['tpo_m30'] is None


def test_tpo_profile_defaults_to_none_when_missing():
    state = _make_state()
    state.tpo_profile = None
    snap = build_indicator_snapshot_for_telegram(state)
    assert snap['tpo_d0'] is None
    assert snap['tpo_d1'] is None
    assert snap['tpo_d2'] is None
    assert snap['tpo_d3'] is None
    assert snap['tpo_h1'] is None
    assert snap['tpo_m30'] is None
