import json
import os
import uuid

import asyncpg
import pytest

from journal import TradeJournalManager, _build_signal_snapshot_columns


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
    assert "signal_schema_version" in snapshot_query_text
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
    assert snapshot_args[6] == "sig-v2.0.0"
    assert snapshot_args[8] == 3345.12
    assert snapshot_args[10] == 3338.40
    assert snapshot_args[15] == 2
    assert snapshot_args[19] == 1
    assert snapshot_args[25] == 3352.55
    assert snapshot_args[26] == 3331.12
    assert snapshot_args[32] == -1
    assert str(snapshot_args[63]).startswith("2026-04-01")


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
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(eval_queries) == 0

    snapshot_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ]
    assert len(snapshot_queries) == 1
    assert snapshot_queries[0][2][5] == "M1"
    assert snapshot_queries[0][2][6] == "sig-v2.0.0"
    assert snapshot_queries[0][2][8] == 3340.0
    assert snapshot_queries[0][2][10] == 3330.0


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
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(eval_queries) == 0


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_signal_snapshot_e2e_db_real_persists_ema_cisd_bb_columns():
    dsn = os.getenv("AUREUS_TEST_DB_DSN", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    conn = await asyncpg.connect(dsn)

    trace_id = f"e2e-snapshot-{uuid.uuid4().hex[:10]}"
    ticket = int(uuid.uuid4().int % 1000000000)

    signal_snapshot = {
        "ema_21": 101.21,
        "ema_34": 101.34,
        "ema_55": 101.55,
        "ema_89": 101.89,
        "ema_100": 102.1,
        "ema_200": 102.2,
        "bb_m15_up": 103.15,
        "bb_m15_dn": 99.15,
        "bb_m5_up": 103.05,
        "bb_m5_dn": 99.05,
        "bb_m1_up": 103.01,
        "bb_m1_dn": 99.01,
        "bb_m30_up": 103.3,
        "bb_m30_dn": 99.3,
        "bb_h1_up": 104.1,
        "bb_h1_dn": 98.1,
        "cisd_m5": "BULL",
        "cisd_m15": "BEAR",
        "cisd_m30": "BULL",
        "cisd_h1": "BEAR",
        "session": "LONDON",
    }

    try:
        journal_id = await conn.fetchval(
            """
            INSERT INTO aureus_trade_journal (
                trace_id, strategy_name, strategy_id, direction, symbol, score,
                active_signals, context_filters, origin_timestamp, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, now(), 'TRIGGERED')
            RETURNING id
            """,
            trace_id,
            "E2E_SIGNAL_MAPPING",
            99901,
            "BUY",
            "XAUUSD",
            0.91,
            json.dumps([]),
            json.dumps({}),
        )

        await conn.execute(
            """
            UPDATE aureus_trade_journal
            SET status='EXECUTED', ticket=$2, entry_price=$3, entry_time=now(), lot_size=0.1
            WHERE id=$1
            """,
            journal_id,
            ticket,
            3333.33,
        )

        await conn.execute(
            """
            INSERT INTO aureus_trade_signal_snapshots (
                trade_journal_id, trace_id, ticket, strategy_name, symbol, timeframe,
                signal_schema_version,
                atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200,
                vol_sma_20, session,
                candle_color_d1, candle_color_h1, candle_color_m30, candle_color_m15, candle_color_m5,
                bb_m1_up, bb_m1_dn, bb_m5_up, bb_m5_dn, bb_m15_up, bb_m15_dn,
                bb_m30_up, bb_m30_dn, bb_h1_up, bb_h1_dn,
                cisd_m5, cisd_m15, cisd_m30, cisd_h1,
                created_at
            ) VALUES (
                $1, $2, $3, $4, $5, 'M1',
                'sig-v2.0.0',
                1.23, $6, $7, $8, $9, $10, $11,
                0.0, 2,
                NULL, NULL, NULL, 1, NULL,
                $12, $13, $14, $15, $16, $17,
                $18, $19, $20, $21,
                $22, $23, $24, $25,
                now()
            )
            """,
            journal_id,
            trace_id,
            ticket,
            "E2E_SIGNAL_MAPPING",
            "XAUUSD",
            signal_snapshot["ema_21"],
            signal_snapshot["ema_34"],
            signal_snapshot["ema_55"],
            signal_snapshot["ema_89"],
            signal_snapshot["ema_100"],
            signal_snapshot["ema_200"],
            signal_snapshot["bb_m1_up"],
            signal_snapshot["bb_m1_dn"],
            signal_snapshot["bb_m5_up"],
            signal_snapshot["bb_m5_dn"],
            signal_snapshot["bb_m15_up"],
            signal_snapshot["bb_m15_dn"],
            signal_snapshot["bb_m30_up"],
            signal_snapshot["bb_m30_dn"],
            signal_snapshot["bb_h1_up"],
            signal_snapshot["bb_h1_dn"],
            1,
            -1,
            1,
            -1,
        )

        row = await conn.fetchrow(
            """
            SELECT
                signal_schema_version,
                ema_21, ema_34, ema_55, ema_89, ema_100, ema_200,
                bb_m1_up, bb_m1_dn, bb_m5_up, bb_m5_dn, bb_m15_up, bb_m15_dn,
                bb_m30_up, bb_m30_dn, bb_h1_up, bb_h1_dn,
                cisd_m5, cisd_m15, cisd_m30, cisd_h1
            FROM aureus_trade_signal_snapshots
            WHERE trade_journal_id = $1
            """,
            journal_id,
        )

        assert row is not None
        assert row["signal_schema_version"] == "sig-v2.0.0"
        assert row["ema_21"] == pytest.approx(signal_snapshot["ema_21"])
        assert row["ema_34"] == pytest.approx(signal_snapshot["ema_34"])
        assert row["ema_55"] == pytest.approx(signal_snapshot["ema_55"])
        assert row["ema_89"] == pytest.approx(signal_snapshot["ema_89"])
        assert row["ema_100"] == pytest.approx(signal_snapshot["ema_100"])
        assert row["ema_200"] == pytest.approx(signal_snapshot["ema_200"])
        assert row["bb_m15_up"] == pytest.approx(signal_snapshot["bb_m15_up"])
        assert row["bb_m15_dn"] == pytest.approx(signal_snapshot["bb_m15_dn"])
        assert row["bb_m5_up"] == pytest.approx(signal_snapshot["bb_m5_up"])
        assert row["bb_m5_dn"] == pytest.approx(signal_snapshot["bb_m5_dn"])
        assert row["bb_m1_up"] == pytest.approx(signal_snapshot["bb_m1_up"])
        assert row["bb_m1_dn"] == pytest.approx(signal_snapshot["bb_m1_dn"])
        assert row["bb_m30_up"] == pytest.approx(signal_snapshot["bb_m30_up"])
        assert row["bb_m30_dn"] == pytest.approx(signal_snapshot["bb_m30_dn"])
        assert row["bb_h1_up"] == pytest.approx(signal_snapshot["bb_h1_up"])
        assert row["bb_h1_dn"] == pytest.approx(signal_snapshot["bb_h1_dn"])
        assert row["cisd_m5"] == 1
        assert row["cisd_m15"] == -1
        assert row["cisd_m30"] == 1
        assert row["cisd_h1"] == -1

    finally:
        await conn.execute("DELETE FROM aureus_trade_signal_snapshots WHERE trace_id = $1", trace_id)
        await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id = $1", trace_id)
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_tpo_d0_d3_db_e2e_journal_columns_persist_fixed_trace_id():
    dsn = os.getenv("AUREUS_TEST_DB_DSN", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    conn = await asyncpg.connect(dsn)
    trace_id = "tpo-d0-d3-e2e-plan-u20-fixed"
    ticket = 260521020
    tpo_payload = {
        "tpo_d0": {"POC": 1010.1, "VAH": 1012.1, "VAL": 1008.1, "OPEN": 1009.1, "HIGH": 1013.1, "LOW": 1007.1, "CLOSE": 1011.1},
        "tpo_d1": {"POC": 1020.2, "VAH": 1022.2, "VAL": 1018.2, "OPEN": 1019.2, "HIGH": 1023.2, "LOW": 1017.2, "CLOSE": 1021.2},
        "tpo_d2": {"POC": 1030.3, "VAH": 1032.3, "VAL": 1028.3, "OPEN": 1029.3, "HIGH": 1033.3, "LOW": 1027.3, "CLOSE": 1031.3},
        "tpo_d3": {"POC": 1040.4, "VAH": 1042.4, "VAL": 1038.4, "OPEN": 1039.4, "HIGH": 1043.4, "LOW": 1037.4, "CLOSE": 1041.4},
    }
    columns = _build_signal_snapshot_columns(tpo_payload, {})
    names = [f"d{day}_{field}" for day in range(4) for field in ("poc", "vah", "val", "open", "high", "low", "close")]

    try:
        await conn.execute("DELETE FROM aureus_trade_signal_snapshots WHERE trace_id = $1", trace_id)
        await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id = $1", trace_id)
        journal_id = await conn.fetchval(
            """
            INSERT INTO aureus_trade_journal (
                trace_id, strategy_name, strategy_id, direction, symbol, score,
                active_signals, context_filters, origin_timestamp, status
            ) VALUES ($1, 'TPO_D0_D3_E2E', 260521020, 'BUY', 'XAUUSD', 0.92, '[]'::jsonb, '{}'::jsonb, now(), 'EXECUTED')
            RETURNING id
            """,
            trace_id,
        )
        await conn.execute(
            f"""
            INSERT INTO aureus_trade_signal_snapshots (
                trade_journal_id, trace_id, ticket, strategy_name, symbol, timeframe,
                signal_schema_version, {', '.join(names)}, created_at
            ) VALUES (
                $1, $2, $3, 'TPO_D0_D3_E2E', 'XAUUSD', 'M1', 'sig-v2.0.0',
                {', '.join(f'${idx}' for idx in range(4, 32))}, now()
            )
            """,
            journal_id,
            trace_id,
            ticket,
            *[columns[name] for name in names],
        )
        row = await conn.fetchrow(
            f"SELECT {', '.join(names)} FROM aureus_trade_signal_snapshots WHERE trace_id = $1",
            trace_id,
        )
        assert row is not None
        for name in names:
            assert row[name] == pytest.approx(columns[name])
    finally:
        await conn.execute("DELETE FROM aureus_trade_signal_snapshots WHERE trace_id = $1", trace_id)
        await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id = $1", trace_id)
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_tpo_d0_d3_db_e2e_journal_on_order_opened_persists_full_tpo():
    dsn = os.getenv("AUREUS_TEST_DB_DSN", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    trace_id = f"tpo-d0-d3-on-opened-{uuid.uuid4().hex[:10]}"
    ticket = int(uuid.uuid4().int % 1000000000)
    tpo_payload = {
        "tpo_d0": {"POC": 3010.1, "VAH": 3012.1, "VAL": 3008.1, "OPEN": 3009.1, "HIGH": 3013.1, "LOW": 3007.1, "CLOSE": 3011.1},
        "tpo_d1": {"POC": 3020.2, "VAH": 3022.2, "VAL": 3018.2, "OPEN": 3019.2, "HIGH": 3023.2, "LOW": 3017.2, "CLOSE": 3021.2},
        "tpo_d2": {"POC": 3030.3, "VAH": 3032.3, "VAL": 3028.3, "OPEN": 3029.3, "HIGH": 3033.3, "LOW": 3027.3, "CLOSE": 3031.3},
        "tpo_d3": {"POC": 3040.4, "VAH": 3042.4, "VAL": 3038.4, "OPEN": 3039.4, "HIGH": 3043.4, "LOW": 3037.4, "CLOSE": 3041.4},
    }
    names = [f"d{day}_{field}" for day in range(4) for field in ("poc", "vah", "val", "open", "high", "low", "close")]

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM aureus_trade_signal_snapshots WHERE trace_id = $1", trace_id)
            await conn.execute("DELETE FROM aureus_reasoning_entries WHERE trace_id = $1", trace_id)
            await conn.execute("DELETE FROM aureus_trades WHERE trace_id = $1", trace_id)
            await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id = $1", trace_id)
            await conn.execute(
                """
                INSERT INTO aureus_trade_journal (
                    trace_id, strategy_name, strategy_id, direction, symbol, score,
                    active_signals, context_filters, origin_timestamp, status
                ) VALUES ($1, 'TREND_CONT_BULL', 260523, 'BUY', 'XAUUSD', 0.92, '[]'::jsonb, '{}'::jsonb, now(), 'TRIGGERED')
                """,
                trace_id,
            )

        manager = TradeJournalManager(db_pool)
        updated = await manager.on_order_opened({
            "type": "ORDER_OPENED",
            "trace_id": trace_id,
            "ticket": ticket,
            "symbol": "XAUUSD",
            "strategy_name": "TREND_CONT_BULL",
            "open_price": 3333.33,
            "volume": 0.1,
            "time": "2026-05-23T00:00:00Z",
            "signal_snapshot": tpo_payload,
        })
        assert updated is True

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {', '.join(names)} FROM aureus_trade_signal_snapshots WHERE trace_id = $1",
                trace_id,
            )

        assert row is not None
        for day in range(4):
            block = tpo_payload[f"tpo_d{day}"]
            for field in ("poc", "vah", "val", "open", "high", "low", "close"):
                assert row[f"d{day}_{field}"] == pytest.approx(block[field.upper()])
    finally:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM aureus_trade_signal_snapshots WHERE trace_id = $1", trace_id)
            await conn.execute("DELETE FROM aureus_reasoning_entries WHERE trace_id = $1", trace_id)
            await conn.execute("DELETE FROM aureus_trades WHERE trace_id = $1", trace_id)
            await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id = $1", trace_id)
        await db_pool.close()


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("AUREUS_RUN_RUNTIME_DB_CHECK") != "1", reason="runtime DB check enabled only when AUREUS_RUN_RUNTIME_DB_CHECK=1")
async def test_signal_snapshot_runtime_db_after_restart_has_non_null_target_columns():
    dsn = os.getenv("AUREUS_TEST_DB_DSN", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            """
            SELECT
                trace_id,
                ema_21,
                ema_55,
                bb_m15_up,
                bb_m15_dn,
                cisd_m15
            FROM aureus_trade_signal_snapshots
            WHERE created_at >= now() - interval '30 minutes'
              AND (ema_21 IS NOT NULL OR ema_55 IS NOT NULL)
              AND (bb_m15_up IS NOT NULL OR bb_m15_dn IS NOT NULL)
              AND cisd_m15 IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        assert row is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_signal_snapshot_mapping_from_json_string_active_signals(journal_manager, mock_db_pool):
    raw_active_signals = json.dumps([
        {"ema_21": 555.21, "ema_55": 555.55, "bb_m15_up": 560.1, "bb_m15_dn": 550.1, "cisd_m15": "BULL"}
    ])

    mock_db_pool.set_result("fetchrow", {
        "id": 77,
        "strategy_name": "E2E_SIGNAL_MAPPING",
        "symbol": "XAUUSD",
        "active_signals": raw_active_signals,
        "context_filters": {},
    })
    mock_db_pool.set_result("execute", "UPDATE 1")

    updated = await journal_manager.on_order_opened({
        "type": "ORDER_OPENED",
        "trace_id": "map-json-active-signals",
        "ticket": 77001,
        "open_price": 3333.0,
        "time": "2026-04-01T00:00:00Z",
        "score_total": 0.9,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.9}]},
        "weights_snapshot": {"signal_quality": 0.4},
        "missing_data_policy": "impute_neutral_and_flag",
    })

    assert updated is True

    snapshot_query = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ][0]
    args = snapshot_query[2]
    assert args[8] == pytest.approx(555.21)
    assert args[10] == pytest.approx(555.55)
    assert args[25] == pytest.approx(560.1)
    assert args[26] == pytest.approx(550.1)
    assert args[32] == 1

    eval_queries = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(eval_queries) == 0


@pytest.mark.asyncio
async def test_signal_snapshot_mapping_supports_bullish_bearish_and_extra_columns(journal_manager, mock_db_pool):
    mock_db_pool.set_result("fetchrow", {
        "id": 88,
        "strategy_name": "E2E_SIGNAL_MAPPING",
        "symbol": "XAUUSD",
        "active_signals": [],
        "context_filters": {"session": "NEWYORK"},
    })
    mock_db_pool.set_result("execute", "UPDATE 1")

    updated = await journal_manager.on_order_opened({
        "type": "ORDER_OPENED",
        "trace_id": "map-bullish-extra-fields",
        "ticket": 88001,
        "open_price": 3333.0,
        "time": "2026-04-01T00:00:00Z",
        "score_total": 0.9,
        "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.9}]},
        "weights_snapshot": {"signal_quality": 0.4},
        "missing_data_policy": "impute_neutral_and_flag",
        "signal_snapshot": {
            "atr_14": 12.34,
            "vol_sma20": 9876.5,
            "session": "LONDON",
            "d1_open": 3310.1,
            "d1_high": 3340.2,
            "d1_low": 3300.3,
            "d1_close": 3333.4,
            "candle_color_d1": "BULLISH",
            "candle_color_h1": "BEARISH",
            "candle_color_M30": "BULLISH",
            "candle_color_M15": "BEARISH",
            "candle_color_M5": "BULLISH",
            "cisd_m5": "BULLISH",
            "cisd_M15": "BEARISH",
            "cisd_M30": "BULLISH",
            "cisd_H1": "BEARISH",
        },
    })

    assert updated is True

    snapshot_query = [
        q for q in mock_db_pool._conn.queries
        if "INSERT INTO aureus_trade_signal_snapshots" in q[1]
    ][0]
    args = snapshot_query[2]

    assert args[7] == pytest.approx(12.34)      # atr
    assert args[14] == pytest.approx(9876.5)    # vol_sma_20
    assert args[15] == 2                         # session LONDON
    assert args[16] == 1                         # candle_color_d1
    assert args[17] == -1                        # candle_color_h1
    assert args[18] == 1                         # candle_color_m30
    assert args[19] == -1                        # candle_color_m15
    assert args[20] == 1                         # candle_color_m5
    assert args[31] == 1                         # cisd_m5
    assert args[32] == -1                        # cisd_m15
    assert args[33] == 1                         # cisd_m30
    assert args[34] == -1                        # cisd_h1
    assert args[45] == pytest.approx(3310.1)     # d1_open
    assert args[46] == pytest.approx(3340.2)     # d1_high
    assert args[47] == pytest.approx(3300.3)     # d1_low
    assert args[48] == pytest.approx(3333.4)     # d1_close


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
        if "INSERT INTO removed_evaluation_table" in q[1]
    ]
    assert len(eval_queries) == 0
