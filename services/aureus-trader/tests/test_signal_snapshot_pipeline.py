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
        "volume": 0.10,
        "time": 1744095600,
        "signal_schema_version": "sig-v1.0.0",
        "signal_snapshot": {
            "cisd_direction": "bull",
            "ema21": 3345.12,
            "ema55": 3338.40,
            "nested": {"momentum": "up"},
        },
        "cisd_direction": "bull",
        "ema21": 3345.12,
        "ema55": 3338.40,
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

    assert "ema21_above_ema55" not in snapshot_query_text
    assert snapshot_args[0] is not None  # trade_journal_id
    assert snapshot_args[1] == "tr-55-001"
    assert snapshot_args[2] == 123456789
    assert snapshot_args[3] == "sig-v1.0.0"
    assert snapshot_args[5] == "bull"
    assert snapshot_args[6] == 3345.12
    assert snapshot_args[7] == 3338.40


@pytest.mark.asyncio
async def test_signal_snapshot_reject_missing_signal_core_no_persist(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "signal_schema_version": "sig-v1.0.0",
        "signal_snapshot": {
            "nested": {"momentum": "up"},
        },
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is False

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 0


@pytest.mark.asyncio
async def test_order_opened_without_signal_payload_updates_journal_only(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "score_total": 0.801234,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "score_version": "scor-v1.0.0",
        "weights_snapshot": {"signal_quality": 0.30},
        "missing_data_policy": "impute_neutral_and_flag",
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is True

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 0


@pytest.mark.asyncio
async def test_signal_snapshot_duplicate_order_opened_same_schema_version_no_extra_record(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "signal_schema_version": "sig-v1.0.0",
        "signal_snapshot": {
            "cisd_direction": "bull",
            "ema21": 3345.12,
            "ema55": 3338.40,
        },
        "cisd_direction": "bull",
        "ema21": 3345.12,
        "ema55": 3338.40,
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
