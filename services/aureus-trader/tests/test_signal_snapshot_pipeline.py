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
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": 1744095600,
        "signal_snapshot": {
            "atr": 2.5,
            "ema_21": 3345.12,
            "ema_34": 3344.80,
            "ema_55": 3338.40,
            "ema_89": 3332.20,
            "ema_100": 3330.10,
            "ema_200": 3318.40,
            "vol_sma_20": 1250.5,
            "session": "LONDON",
            "candle_color_d1": "BULL",
            "candle_color_h1": "BEAR",
            "candle_color_m30": "BULL",
            "candle_color_m15": "BULL",
            "candle_color_m5": "BEAR",
            "bb_m1_up": 3350.1,
            "bb_m1_dn": 3340.1,
            "bb_m5_up": 3352.1,
            "bb_m5_dn": 3338.1,
            "bb_m15_up": 3354.1,
            "bb_m15_dn": 3336.1,
            "bb_m30_up": 3356.1,
            "bb_m30_dn": 3334.1,
            "bb_h1_up": 3360.1,
            "bb_h1_dn": 3330.1,
            "cisd_m5": "BULL",
            "cisd_m15": "BEAR",
            "cisd_m30": "BULL",
            "cisd_h1": "BEAR",
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

    assert "signal_schema_version" not in snapshot_query_text
    assert " signal_snapshot," not in snapshot_query_text
    assert " timeframe," not in snapshot_query_text

    assert snapshot_args[0] is not None
    assert snapshot_args[1] == "tr-55-001"
    assert snapshot_args[2] == 123456789
    assert snapshot_args[5] == 2.5  # atr
    assert snapshot_args[6] == 3345.12  # ema_21
    assert snapshot_args[8] == 3338.40  # ema_55
    assert snapshot_args[13] == 2  # session LONDON
    assert snapshot_args[14] == 1  # candle_color_d1 BULL
    assert snapshot_args[15] == -1  # candle_color_h1 BEAR
    assert snapshot_args[29] == 1  # cisd_m5 BULL
    assert snapshot_args[30] == -1  # cisd_m15 BEAR


@pytest.mark.asyncio
async def test_signal_snapshot_persist_with_partial_signal_payload(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": 1744095600,
        "signal_snapshot": {
            "ema_21": 3345.12,
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

    snapshot_args = snapshot_queries[0][2]
    assert snapshot_args[6] == 3345.12
    assert snapshot_args[5] is None
    assert snapshot_args[8] is None


@pytest.mark.asyncio
async def test_signal_snapshot_duplicate_order_opened_same_trade_no_extra_record(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": 1744095600,
        "signal_snapshot": {
            "ema_21": 3345.12,
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
async def test_signal_snapshot_missing_mt5_time_rejected(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "signal_snapshot": {"ema_21": 3345.12},
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is False


@pytest.mark.asyncio
async def test_signal_snapshot_invalid_mt5_time_rejected(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": "invalid-time",
        "signal_snapshot": {"ema_21": 3345.12},
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is False
