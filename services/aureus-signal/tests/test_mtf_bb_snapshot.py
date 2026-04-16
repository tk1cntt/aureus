from engine.mtf_snapshot import build_bb_payload


def _make_bb_snapshot(**values):
    return {
        "M1": values.get("M1", {"upper": 101.0, "middle": 100.0, "lower": 99.0}),
        "M5": values.get("M5", {"upper": 106.0, "middle": 105.0, "lower": 104.0}),
        "M15": values.get("M15", {"upper": 111.0, "middle": 110.0, "lower": 109.0}),
        "M30": values.get("M30", {"upper": 116.0, "middle": 115.0, "lower": 114.0}),
        "H1": values.get("H1", {"upper": 121.0, "middle": 120.0, "lower": 119.0}),
    }


def test_build_bb_payload_contains_required_timeframe_keys():
    payload = build_bb_payload(_make_bb_snapshot())
    assert "bb_m1" in payload
    assert "bb_m5" in payload
    assert "bb_m15" in payload
    assert "bb_m30" in payload
    assert "bb_h1" in payload


def test_build_bb_payload_each_tf_has_upper_middle_lower():
    payload = build_bb_payload(_make_bb_snapshot())

    assert set(payload["bb_m1"].keys()) == {"upper", "middle", "lower"}
    assert set(payload["bb_m5"].keys()) == {"upper", "middle", "lower"}
    assert set(payload["bb_m15"].keys()) == {"upper", "middle", "lower"}
    assert set(payload["bb_m30"].keys()) == {"upper", "middle", "lower"}
    assert set(payload["bb_h1"].keys()) == {"upper", "middle", "lower"}


def test_build_bb_payload_returns_null_for_missing_tf_data():
    source = _make_bb_snapshot(M15=None, H1=None)

    payload = build_bb_payload(source)

    assert payload["bb_m1"] is not None
    assert payload["bb_m5"] is not None
    assert payload["bb_m15"] is None
    assert payload["bb_m30"] is not None
    assert payload["bb_h1"] is None
