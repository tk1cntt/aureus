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
        "timeframe": "M15",
        "signal_schema_version": "sig-v2.0.0",
        "signal_snapshot": {
            "cisd_direction": "bull",
            "ema_21": 3345.12,
            "ema_55": 3338.40,
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
    assert "signal_schema_version" in snapshot_query_text
    assert "signal_snapshot" in snapshot_query_text
    assert "cisd_direction" in snapshot_query_text
    assert "ema21" in snapshot_query_text
    assert "ema55" in snapshot_query_text

    assert "debug_payload" not in snapshot_query_text
    assert "raw_reasoning" not in snapshot_query_text
    assert "ema21_above_ema55" not in snapshot_query_text

    assert snapshot_args[1] == "tr-55-storage-001"
    assert snapshot_args[2] == 123456789
    assert snapshot_args[5] == "M15"
    assert snapshot_args[6] == "sig-v2.0.0"
    assert snapshot_args[7]["cisd_direction"] == "bull"
    assert snapshot_args[8] == "bull"
    assert snapshot_args[9] == 3345.12
    assert snapshot_args[10] == 3338.40


@pytest.mark.asyncio
async def test_signal_snapshot_duplicate_trade_and_schema_version_is_blocked(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-storage-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": "2026-04-01T00:00:00Z",
        "timeframe": "M15",
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
