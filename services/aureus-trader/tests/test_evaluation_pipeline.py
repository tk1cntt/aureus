import pytest


@pytest.mark.asyncio
async def test_order_opened_does_not_insert_evaluation_and_keeps_snapshot(journal_manager, valid_strategy_match_event, mock_db_pool):
    mock_db_pool.set_result("fetchval", 1)
    created = await journal_manager.on_strategy_match(valid_strategy_match_event)
    assert created is True

    pre_open_eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(pre_open_eval_queries) == 0

    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "volume": 0.10,
        "sl": 3338.40,
        "tp": 3362.00,
        "time": 1744095600,
        "score_total": 0.801234,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "score_version": "scor-v1.0.0",
        "weights_snapshot": {"signal_quality": 0.30},
        "missing_data_policy": "impute_neutral_and_flag",
        "strategy_name": "chandelier_breakout",
        "symbol": "XAUUSD",
        "timeframe": "M5",
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is True

    post_open_eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(post_open_eval_queries) == 0

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1


@pytest.mark.asyncio
async def test_order_opened_without_score_payload_keeps_snapshot_path(journal_manager, mock_db_pool, caplog):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": 1744095600,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "score_version": "scor-v1.0.0",
        "weights_snapshot": {"signal_quality": 0.30},
        "missing_data_policy": "impute_neutral_and_flag",
        "strategy_name": "chandelier_breakout",
        "symbol": "XAUUSD",
        "timeframe": "M5",
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is True
    eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(eval_queries) == 0

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1

    assert any("UPDATE aureus_trade_journal" in q[1] for q in mock_db_pool._conn.queries)


@pytest.mark.asyncio
async def test_order_opened_without_evaluation_payload_keeps_journal_and_snapshot(journal_manager, mock_db_pool, caplog):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": 1744095600,
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    updated = await journal_manager.on_order_opened(order_opened_event)
    assert updated is True
    eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(eval_queries) == 0

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1

    assert any("UPDATE aureus_trade_journal" in q[1] for q in mock_db_pool._conn.queries)


@pytest.mark.asyncio
async def test_duplicate_order_opened_does_not_insert_evaluation(journal_manager, mock_db_pool):
    order_opened_event = {
        "type": "ORDER_OPENED",
        "trace_id": "tr-55-001",
        "ticket": 123456789,
        "open_price": 3348.15,
        "time": 1744095600,
        "score_total": 0.801234,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
        "score_version": "scor-v1.0.0",
        "weights_snapshot": {"signal_quality": 0.30},
        "missing_data_policy": "impute_neutral_and_flag",
        "strategy_name": "chandelier_breakout",
        "symbol": "XAUUSD",
        "timeframe": "M5",
    }

    mock_db_pool.set_result("execute", "UPDATE 1")
    first = await journal_manager.on_order_opened(order_opened_event)
    assert first is True

    mock_db_pool.set_result("execute", "UPDATE 0")
    second = await journal_manager.on_order_opened(order_opened_event)
    assert second is False

    eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(eval_queries) == 0
