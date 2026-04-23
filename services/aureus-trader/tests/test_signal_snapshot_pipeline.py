import pytest


@pytest.mark.asyncio
async def test_signal_snapshot_boundary_pre_open_zero_post_open_one(journal_manager, valid_strategy_match_event, mock_db_pool):
    mock_db_pool.set_result("fetchval", 1)
    created = await journal_manager.on_strategy_match(valid_strategy_match_event)
    assert created is True

    pre_open_snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(pre_open_snapshot_queries) == 0

    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-storage-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": "2026-04-01T00:00:00Z",
        "score_total": 0.812345,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "weights_snapshot": {"signal_quality": 0.30},
        "missing_data_policy": "impute_neutral_and_flag",
        "score_version": "scor-v1.0.0",
        "signal_schema_version": "sig-v2.0.0",
        "signal_snapshot": {
            "session": "LONDON",
            "ema_21": 3345.12,
            "ema_55": 3338.40,
            "candle_color_m15": "BULL",
            "bb_m15_up": 3352.55,
            "bb_m15_dn": 3331.12,
            "cisd_m15": "BEAR",
            "debug_payload": {"source": "debug"},
            "raw_reasoning": "internal",
            "ema21_above_ema55": True,
        },
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is True

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1
    snapshot_query_text = snapshot_queries[0][1]
    snapshot_args = snapshot_queries[0][2]

    assert "trade_journal_id" in snapshot_query_text
    assert "trace_id" in snapshot_query_text
    assert "ticket" in snapshot_query_text
    assert "strategy_name" in snapshot_query_text
    assert "symbol" in snapshot_query_text
    assert "timeframe" in snapshot_query_text
    assert "signal_schema_version" not in snapshot_query_text
    assert "signal_snapshot," not in snapshot_query_text
    assert "session" in snapshot_query_text
    assert "candle_color_m15" in snapshot_query_text
    assert "bb_m15_up" in snapshot_query_text
    assert "bb_m15_dn" in snapshot_query_text
    assert "cisd_m15" in snapshot_query_text
    assert "ema_21" in snapshot_query_text
    assert "ema_55" in snapshot_query_text

    assert "debug_payload" not in snapshot_query_text
    assert "raw_reasoning" not in snapshot_query_text
    assert "ema21_above_ema55" not in snapshot_query_text

    assert snapshot_args[1] == "tr-55-storage-001"
    assert snapshot_args[2] == 123456789
    assert snapshot_args[5] == "M1"
    assert snapshot_args[7] == 3345.12
    assert snapshot_args[9] == 3338.40
    assert snapshot_args[14] == 2
    assert snapshot_args[18] == 1
    assert snapshot_args[24] == 3352.55
    assert snapshot_args[25] == 3331.12
    assert snapshot_args[31] == -1
    assert str(snapshot_args[34]).startswith("2026-04-01")


@pytest.mark.asyncio
async def test_signal_snapshot_duplicate_trade_and_schema_version_is_blocked(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-storage-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": "2026-04-01T00:00:00Z",
        "timeframe": "M15",
        "score_total": 0.812345,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "weights_snapshot": {"signal_quality": 0.30},
        "missing_data_policy": "impute_neutral_and_flag",
        "score_version": "scor-v1.0.0",
        "signal_schema_version": "sig-v2.0.0",
        "signal_snapshot": {
            "cisd_direction": "bull",
            "ema_21": 3345.12,
            "ema_55": 3338.40,
        },
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    first = await journal_manager.on_order_opened(order_opened_event)
    assert first is True

    mock_db_pool.set_result("execute", "UPDATE 0")
    second = await journal_manager.on_order_opened(order_opened_event)
    assert second is False

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1


@pytest.mark.asyncio
async def test_signal_snapshot_defaults_timeframe_to_m1_when_missing(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-storage-002",
        "ticket": 987654321,
        "open_price": 3340.25,
        "time": "2026-04-01T00:00:00Z",
        "score_total": 0.8,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "weights_snapshot": {"signal_quality": 0.3},
        "missing_data_policy": "impute_neutral_and_flag",
        "signal_snapshot": {
            "ema_21": 3340.0,
            "ema_55": 3330.0,
        },
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)

    assert updated is True

    eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_evaluations" in q[1]
    ]
    assert len(eval_queries) == 1
    assert eval_queries[0][2][10] == "M1"

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1
    assert snapshot_queries[0][2][5] == "M1"
    assert snapshot_queries[0][2][7] == 3340.0
    assert snapshot_queries[0][2][9] == 3330.0


@pytest.mark.asyncio
async def test_signal_snapshot_skips_when_payload_unmappable(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-storage-003",
        "ticket": 987654322,
        "open_price": 3340.25,
        "time": "2026-04-01T00:00:00Z",
        "score_total": 0.8,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "weights_snapshot": {"signal_quality": 0.3},
        "missing_data_policy": "impute_neutral_and_flag",
        "signal_snapshot": {
            "debug_payload": {"x": 1},
            "raw_reasoning": "internal",
            "ema21_above_ema55": True,
        },
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)

    assert updated is True

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1

    eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_evaluations" in q[1]
    ]
    assert len(eval_queries) == 1
