"""
Comprehensive test suite for TradeJournalManager.
Covers 6 pillars: Inbound, Outbound, Black-box, White-box, Abnormal, Migration/Schema.
Target: 100% line coverage, ≥95% branch coverage on journal.py.
"""
import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import reasoning_embeddings

from journal import TradeJournalManager, VALID_EXIT_REASONS, VALID_DIRECTIONS, PIP_VALUES


def test_order_closed_gateway_model_keeps_exit_reason_fields():
    import importlib.util
    import pathlib

    gateway_path = pathlib.Path(__file__).parents[2] / "aureus-gateway" / "main.py"
    spec = importlib.util.spec_from_file_location("aureus_gateway_main", gateway_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    event = module.OrderClosedEvent(
        type="ORDER_CLOSED",
        symbol="XAUUSD",
        ticket=12345,
        direction="BUY",
        volume=0.01,
        open_price=3250.50,
        close_price=3260.50,
        exit_price=3260.50,
        profit=10.0,
        commission=0.05,
        swap=0.01,
        magic=607000,
        exit_time=1744102800000,
        close_reason="DEAL_REASON_TP",
        exit_reason="TP",
        reason="TP",
        t=1744102800000,
    )

    dumped = event.model_dump()
    assert dumped["exit_price"] == 3260.50
    assert dumped["exit_reason"] == "TP"
    assert dumped["close_reason"] == "DEAL_REASON_TP"
    assert dumped["reason"] == "TP"



# =============================================================================
# Pillar 1: Inbound Tests — Data Input Validation
# =============================================================================

class TestOnStrategyMatchInputValidation:
    """TJ-IN-01 through TJ-IN-13: Input validation for on_strategy_match."""

    @pytest.mark.asyncio
    async def test_TJ_IN_01_valid_strategy_match_creates_entry(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """Valid strategy match → INSERT success with status=TRIGGERED."""
        mock_db_pool.set_result("fetchval", 1)
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is True
        assert len(mock_db_pool.acquired) == 1
        # Verify INSERT query called
        queries = mock_db_pool._conn.queries
        assert len(queries) == 1
        assert queries[0][0] == "fetchval"
        assert "INSERT INTO aureus_trade_journal" in queries[0][1]
        assert "INSERT INTO aureus_reasoning_entries" not in queries[0][1]

    @pytest.mark.asyncio
    async def test_TJ_IN_02_missing_trace_id(self, journal_manager, valid_strategy_match_event):
        """Missing trace_id → returns False."""
        valid_strategy_match_event.pop("trace_id")
        valid_strategy_match_event["data"].pop("trace_id", None)
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_03_missing_strategy_name(self, journal_manager, valid_strategy_match_event):
        """Missing strategy_name → returns False."""
        valid_strategy_match_event["data"]["strategy_name"] = ""
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_04_invalid_direction(self, journal_manager, valid_strategy_match_event):
        """Invalid direction → returns False."""
        valid_strategy_match_event["data"]["direction"] = "HODL"
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_05_missing_symbol(self, journal_manager, valid_strategy_match_event):
        """Missing symbol → returns False."""
        valid_strategy_match_event["data"]["symbol"] = ""
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_06_score_is_string(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """Score is non-numeric string → coerced to None (warning log), continues."""
        valid_strategy_match_event["data"]["score"] = "abc"
        mock_db_pool.set_result("fetchval", 1)
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is True
        # Verify score param in query args is None
        query_args = mock_db_pool._conn.queries[0][2]
        score_value = query_args[5]
        assert score_value is None

    @pytest.mark.asyncio
    async def test_TJ_IN_07_active_signals_not_list(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """active_signals is not a list → coerced to empty list, continues."""
        valid_strategy_match_event["data"]["active_signals"] = "not_a_list"
        mock_db_pool.set_result("fetchval", 1)
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_TJ_IN_07b_active_signals_dict_normalized(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """active_signals là dict snapshot → normalize sang list và vẫn insert thành công."""
        valid_strategy_match_event["data"]["active_signals"] = {
            "choch_up": {"value": True, "category": "structure"},
            "cisd_bull": {"value": 1, "category": "momentum"},
        }
        mock_db_pool.set_result("fetchval", 1)
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is True

        query_args = mock_db_pool._conn.queries[0][2]
        normalized = json.loads(query_args[6])
        assert isinstance(normalized, list)
        assert any(item.get("tag") == "choch_up" for item in normalized)
        assert any(item.get("tag") == "cisd_bull" for item in normalized)

    @pytest.mark.asyncio
    async def test_TJ_IN_08_origin_timestamp_unix_int(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """origin_timestamp is Unix int → converted to datetime successfully."""
        valid_strategy_match_event["data"]["origin_timestamp"] = 1712500800
        mock_db_pool.set_result("fetchval", 1)
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is True


class TestOnOrderOpenedInputValidation:
    """TJ-IN-09 through TJ-IN-10: Input validation for on_order_opened."""

    @pytest.mark.asyncio
    async def test_TJ_IN_09_missing_ticket(self, journal_manager, valid_order_opened_event):
        """Missing ticket → returns False."""
        valid_order_opened_event.pop("ticket")
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_10_invalid_entry_price(self, journal_manager, valid_order_opened_event):
        """entry_price <= 0 → returns False."""
        valid_order_opened_event["open_price"] = 0
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False

        valid_order_opened_event["open_price"] = -1
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_10b_missing_entry_price(self, journal_manager, valid_order_opened_event):
        """Missing entry_price → returns False (None <= 0 is False, but None is truthy check first)."""
        valid_order_opened_event.pop("open_price")
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_10c_missing_mt5_order_time(self, journal_manager, valid_order_opened_event):
        """Missing MT5 time/open_time → returns False (no fallback allowed)."""
        valid_order_opened_event.pop("time", None)
        valid_order_opened_event.pop("open_time", None)
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_10d_invalid_mt5_order_time_string(self, journal_manager, valid_order_opened_event):
        """Invalid MT5 time string → returns False (no fallback allowed)."""
        valid_order_opened_event["time"] = "not-a-time"
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False


class TestPendingOrderLifecycle:
    @pytest.mark.asyncio
    async def test_pending_placed_persists_pending_order_without_executed(self, journal_manager, mock_db_pool):
        result = await journal_manager.on_order_pending_placed({
            "type": "ORDER_PENDING_PLACED",
            "trace_id": "trace-test-journal-001",
            "cmd_id": "ord-pending-1",
            "pending_order_id": 9001,
            "price": 3250.5,
            "sl": 3247.5,
            "tp": 3256.5,
            "comment": "LIMIT|trace-test",
        })

        assert result is True
        query = mock_db_pool._conn.queries[0][1]
        args = mock_db_pool._conn.queries[0][2]
        assert "status = 'TRIGGERED'" in query
        assert "status = 'EXECUTED'" not in query.split("WHERE", 1)[0]
        assert args[0] == 9001
        assert args[1] == "ord-pending-1"

    @pytest.mark.asyncio
    async def test_order_filled_executes_with_position_and_deal_ticket(self, journal_manager, mock_db_pool):
        result = await journal_manager.on_order_filled({
            "type": "ORDER_FILLED",
            "trace_id": "trace-test-journal-001",
            "cmd_id": "ord-fill-1",
            "pending_order_id": 9001,
            "deal_ticket": 7001,
            "position_ticket": 8001,
            "open_price": 3251.0,
            "volume": 0.1,
            "time": 1775642400,
        })

        assert result is True
        args = mock_db_pool._conn.queries[0][2]
        assert args[0] == 8001
        assert args[3] == 8001
        assert args[8] == 9001
        assert args[9] == 7001

    @pytest.mark.asyncio
    async def test_order_filled_without_trace_id_uses_pending_or_cmd_fallback(self, journal_manager, mock_db_pool):
        result = await journal_manager.on_order_filled({
            "type": "ORDER_FILLED",
            "cmd_id": "ord-fill-no-trace",
            "pending_order_id": 9002,
            "deal_ticket": 7002,
            "position_ticket": 8002,
            "open_price": 3252.0,
            "volume": 0.2,
            "time": 1775642500,
        })

        assert result is True
        query = mock_db_pool._conn.queries[0][1]
        args = mock_db_pool._conn.queries[0][2]
        assert "pending_order_id = $9" in query
        assert "cmd_id = $11" in query
        assert args[0] == 8002
        assert args[3] == 8002
        assert args[7] is None
        assert args[8] == 9002
        assert args[9] == 7002
        assert args[10] == "ord-fill-no-trace"

    @pytest.mark.asyncio
    async def test_order_filled_without_trace_id_and_without_fallback_keys_returns_false(self, journal_manager, mock_db_pool):
        result = await journal_manager.on_order_filled({
            "type": "ORDER_FILLED",
            "deal_ticket": 7003,
            "position_ticket": 8003,
            "open_price": 3253.0,
            "volume": 0.2,
            "time": 1775642600,
        })

        assert result is False
        assert mock_db_pool._conn.queries == []


class TestReasoningBank:
    @pytest.mark.asyncio
    async def test_on_strategy_match_skips_reasoning_entry_without_parent_trade(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        valid_strategy_match_event["data"]["reasoning"] = "CISD + sweep aligned"
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_strategy_match(valid_strategy_match_event)

        assert result is True
        queries = mock_db_pool._conn.queries
        assert len(queries) == 1
        assert "INSERT INTO aureus_trade_journal" in queries[0][1]
        assert not any("INSERT INTO aureus_reasoning_entries" in q[1] for q in queries)

    @pytest.mark.asyncio
    async def test_on_strategy_match_reasoning_deferral_non_blocking(self, journal_manager, valid_strategy_match_event, mock_db_pool, caplog):
        valid_strategy_match_event["data"]["reasoning"] = "CISD + sweep aligned"
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_strategy_match(valid_strategy_match_event)

        assert result is True
        assert any("Reasoning entry deferred" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_on_strategy_match_enqueue_not_attempted_before_parent_trade(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        valid_strategy_match_event["data"]["reasoning"] = "CISD + sweep aligned"
        journal_manager.redis = MagicMock()
        mock_db_pool.set_result("fetchval", 1)

        with patch("journal.enqueue_reasoning_embedding_job", new=AsyncMock(side_effect=RuntimeError("redis down"))) as enqueue_mock:
            result = await journal_manager.on_strategy_match(valid_strategy_match_event)

        assert result is True
        enqueue_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_strategy_match_captures_raw_prompt_context_only(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        valid_strategy_match_event["data"].update({
            "reasoning": "real reasoning",
            "prompt_text": "raw prompt text",
            "context_text": "raw context text",
            "prompt_digest": "digest-should-not-embed",
            "input_context_hash": "hash-should-not-embed",
        })
        mock_db_pool.set_result("fetchval", 1)

        journal_manager.redis = MagicMock()
        with patch("journal.enqueue_reasoning_embedding_job", new=AsyncMock(return_value=True)) as enqueue_mock:
            result = await journal_manager.on_strategy_match(valid_strategy_match_event)

        assert result is True
        assert len(mock_db_pool._conn.queries) == 1
        enqueue_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_order_opened_ensures_parent_trade_before_reasoning_insert(self, journal_manager, valid_order_opened_event, mock_db_pool):
        result = await journal_manager.on_order_opened(valid_order_opened_event)

        assert result is True
        queries = mock_db_pool._conn.queries
        parent_insert_index = next(i for i, q in enumerate(queries) if "INSERT INTO aureus_trades" in q[1])
        reasoning_insert_index = next(i for i, q in enumerate(queries) if "INSERT INTO aureus_reasoning_entries" in q[1])
        assert parent_insert_index < reasoning_insert_index
        parent_query = queries[parent_insert_index][1]
        parent_args = queries[parent_insert_index][2]
        assert "VALUES ($1, $2, $3, 'MARKET'" not in parent_query
        assert "entry_type" in parent_query
        assert "sl" in parent_query
        assert "tp" in parent_query
        assert "volume" in parent_query
        assert "strategy_name" in parent_query
        assert "payload" in parent_query
        assert parent_args[0] == "trace-test-journal-001"
        assert parent_args[1] == "XAUUSD"
        assert parent_args[2] == "BUY"
        assert parent_args[3] == "LIMIT"
        assert parent_args[4] == 3250.50
        assert parent_args[5] == 12345
        assert parent_args[6] == 3247.50
        assert parent_args[7] == 3256.50
        assert parent_args[8] == 0.01
        assert parent_args[9] == "chandelier_breakout"
        payload = json.loads(parent_args[10])
        assert payload["source"] == "journal_parent_upsert"
        assert payload["event"]["entry_type"] == "LIMIT"

    @pytest.mark.asyncio
    async def test_on_order_opened_reasoning_insert_failure_non_blocking(self, journal_manager, valid_order_opened_event, mock_db_pool):
        class ReasoningFailConnection:
            def __init__(self):
                self.queries = []

            def transaction(self):
                class Ctx:
                    async def __aenter__(inner_self):
                        return self
                    async def __aexit__(inner_self, *args):
                        pass
                return Ctx()

            async def fetchrow(self, query, *args):
                self.queries.append(("fetchrow", query, args))
                return {
                    "id": 1,
                    "trace_id": "trace-test-journal-001",
                    "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
                    "direction": "BUY",
                    "symbol": "XAUUSD",
                    "active_signals": [],
                    "context_filters": {},
                    "strategy_name": "chandelier_breakout",
                }

            async def fetchval(self, query, *args):
                self.queries.append(("fetchval", query, args))
                if "INSERT INTO aureus_trade_signal_snapshots" in query:
                    return 1
                if "INSERT INTO aureus_reasoning_entries" in query:
                    raise RuntimeError("reasoning insert failed")
                return 1

            async def execute(self, query, *args):
                self.queries.append(("execute", query, args))
                return "UPDATE 1"

        conn = ReasoningFailConnection()
        mock_db_pool._conn = conn

        result = await journal_manager.on_order_opened(valid_order_opened_event)

        assert result is True
        assert any("INSERT INTO aureus_trades" in q[1] for q in conn.queries)
        assert any("INSERT INTO aureus_reasoning_entries" in q[1] for q in conn.queries)

    @pytest.mark.asyncio
    async def test_on_order_opened_enqueues_reasoning_embedding_job(self, journal_manager, valid_order_opened_event, mock_db_pool):
        journal_manager.redis = MagicMock()

        with patch("journal.enqueue_reasoning_embedding_job", new=AsyncMock(return_value=True)) as enqueue_mock:
            result = await journal_manager.on_order_opened(valid_order_opened_event)

        assert result is True
        enqueue_mock.assert_awaited_once()
        assert enqueue_mock.await_args.args[0] is journal_manager.redis
        assert enqueue_mock.await_args.args[3] == "trace-test-journal-001"

    def test_main_runtime_wires_redis_into_trade_journal_manager(self):
        with open("services/aureus-trader/main.py", "r", encoding="utf-8") as fh:
            source = fh.read()
        assert "TradeJournalManager(db_pool, redis_client=r)" in source

    @pytest.mark.asyncio
    async def test_on_order_opened_links_reasoning_entry(self, journal_manager, valid_order_opened_event, mock_db_pool):
        result = await journal_manager.on_order_opened(valid_order_opened_event)

        assert result is True
        queries = mock_db_pool._conn.queries
        reasoning_inserts = [q for q in queries if "INSERT INTO aureus_reasoning_entries" in q[1]]
        assert len(reasoning_inserts) == 1
        args = reasoning_inserts[0][2]
        assert args[0] == "trace-test-journal-001"
        assert args[1] == 1

    @pytest.mark.asyncio
    async def test_on_order_opened_maps_nested_data_session_to_signal_snapshot(self, journal_manager, valid_order_opened_event, mock_db_pool):
        valid_order_opened_event["data"] = {
            "session": "new_york",
            "signal_snapshot": {
                "atr": 2.5,
            },
        }

        result = await journal_manager.on_order_opened(valid_order_opened_event)

        assert result is True
        snapshot_inserts = [q for q in mock_db_pool._conn.queries if "INSERT INTO aureus_trade_signal_snapshots" in q[1]]
        assert len(snapshot_inserts) == 1
        args = snapshot_inserts[0][2]
        assert args[15] == 3

    @pytest.mark.asyncio
    async def test_on_order_opened_persists_d1_tpo_levels_to_signal_snapshot(self, journal_manager, valid_order_opened_event, mock_db_pool):
        valid_order_opened_event["signal_snapshot"] = {
            "tpo_d1": {"POC": 2010.1, "VAH": 2012.3, "VAL": 2008.7},
        }

        result = await journal_manager.on_order_opened(valid_order_opened_event)

        assert result is True
        snapshot_inserts = [q for q in mock_db_pool._conn.queries if "INSERT INTO aureus_trade_signal_snapshots" in q[1]]
        assert len(snapshot_inserts) == 1
        query = snapshot_inserts[0][1]
        args = snapshot_inserts[0][2]
        assert "d1_poc" in query
        assert "d1_vah" in query
        assert "d1_val" in query
        assert args[35] == 2010.1
        assert args[36] == 2012.3
        assert args[37] == 2008.7

    async def test_post_snapshot_generates_reasoning_text_without_prompt_context(self, journal_manager, mock_db_pool):
        strategy_event = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-test-journal-001",
            "data": {
                "strategy_name": "TREND_CONT_BULL",
                "strategy_id": 101,
                "direction": "BUY",
                "symbol": "XAUUSD",
                "score": 0.85,
                "active_signals": [{"tag": "cisd_bull", "status": "active"}],
                "context_filters": {"session": "london"},
            },
        }
        order_event = {
            "type": "ORDER_OPENED",
            "trace_id": "trace-test-journal-001",
            "ticket": 12345,
            "open_price": 3250.50,
            "volume": 0.01,
            "time": 1744095600,
            "timeframe": "M15",
            "signal_snapshot": {
                "active_signals": [{"tag": "cisd_bull", "status": "active"}],
                "context_filters": {"session": "london"},
                "trend": "bullish",
                "cisd_m15": "BULL",
                "tpo_shape": "D",
                "session": "london",
                "atr": 2.5,
                "ema21": 3249.1,
                "ema55": 3240.2,
                "bb_m5_up": 3260.0,
                "bb_m5_dn": 3230.0,
            },
        }

        mock_db_pool.set_result("fetchval", 1)
        assert await journal_manager.on_strategy_match(strategy_event) is True
        assert len(mock_db_pool._conn.queries) == 1
        assert "INSERT INTO aureus_trade_journal" in mock_db_pool._conn.queries[0][1]

        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD",
            "active_signals": [{"tag": "cisd_bull", "status": "active"}],
            "context_filters": {"session": "london"},
            "strategy_name": "TREND_CONT_BULL",
        })
        journal_manager.redis = MagicMock()
        with patch("journal.enqueue_reasoning_embedding_job", new=AsyncMock(side_effect=RuntimeError("redis down"))) as enqueue_mock:
            assert await journal_manager.on_order_opened(order_event) is True

        queries = mock_db_pool._conn.queries
        inserts = [q for q in queries if "INSERT INTO aureus_reasoning_entries" in q[1]]
        assert len(inserts) == 1
        insert_query = inserts[0][1]
        assert "active_signals" not in insert_query
        insert_args = inserts[0][2]
        assert len(insert_args) == 9
        generated_text = insert_args[7]
        assert "TREND_CONT_BULL" in generated_text
        assert "XAUUSD" in generated_text
        assert "BUY" in generated_text
        assert "london" in generated_text
        assert "cisd_m15=1" in generated_text
        assert "active_signals" not in generated_text
        assert "cisd_bull" not in generated_text
        enqueue_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_post_snapshot_does_not_overwrite_upstream_reasoning(self, journal_manager, valid_strategy_match_event, valid_order_opened_event, mock_db_pool):
        valid_strategy_match_event["data"].update({
            "reasoning": "Upstream reasoning stays",
            "prompt_text": "raw prompt",
            "context_text": "raw context",
        })
        mock_db_pool.set_result("fetchval", 1)

        assert await journal_manager.on_strategy_match(valid_strategy_match_event) is True
        assert await journal_manager.on_order_opened(valid_order_opened_event) is True

        inserts = [q for q in mock_db_pool._conn.queries if "INSERT INTO aureus_reasoning_entries" in q[1]]
        assert len(inserts) == 1
        assert "ON CONFLICT" not in inserts[0][1]

    @pytest.mark.asyncio
    async def test_on_order_closed_attaches_reasoning_outcome(self, journal_manager, valid_order_closed_event, mock_db_pool):
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_order_closed(valid_order_closed_event)

        assert result is True
        queries = mock_db_pool._conn.queries
        reasoning_updates = [q for q in queries if "UPDATE aureus_reasoning_entries" in q[1]]
        assert len(reasoning_updates) == 1
        args = reasoning_updates[0][2]
        assert args[0] == "trace-test-journal-001"


class TestOnOrderClosedInputValidation:
    """TJ-IN-11 through TJ-IN-13: Input validation for on_order_closed."""

    @pytest.mark.asyncio
    async def test_TJ_IN_11_missing_close_price(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """Missing close_price → returns False."""
        valid_order_closed_event.pop("close_price")
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_IN_12_invalid_exit_reason_normalized(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """Invalid exit reason → normalized to a valid value."""
        valid_order_closed_event["close_reason"] = "MAGIC"
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)
        result = await journal_manager.on_order_closed(valid_order_closed_event)
        # Should succeed with normalized reason
        assert result is True

    @pytest.mark.asyncio
    async def test_TJ_IN_13_valid_exit_reasons(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """All valid exit reasons accepted."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        for reason in VALID_EXIT_REASONS:
            valid_order_closed_event["close_reason"] = reason
            result = await journal_manager.on_order_closed(valid_order_closed_event)
            assert result is True


# =============================================================================
# Pillar 2: Outbound Tests — Data Output Verification
# =============================================================================

class TestOutboundStrategyMatch:
    """TJ-OUT-01: INSERT with all fields."""

    @pytest.mark.asyncio
    async def test_TJ_OUT_01_insert_all_fields(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """INSERT with all correct field types and values."""
        mock_db_pool.set_result("fetchval", 1)
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is True

        query_args = mock_db_pool._conn.queries[0][2]
        assert query_args[0] == "trace-test-journal-001"  # trace_id
        assert query_args[1] == "chandelier_breakout"     # strategy_name
        assert query_args[2] == 101                        # strategy_id
        assert query_args[3] == "BUY"                      # direction
        assert query_args[4] == "XAUUSD"                   # symbol
        assert query_args[5] == 0.85                      # score
        # Verify JSONB encoding
        assert json.loads(query_args[6]) == [              # active_signals
            {"tag": "liquidity_sweep", "weight": 0.7, "status": "active"},
            {"tag": "break_of_structure", "weight": 0.8, "status": "active"}
        ]


class TestOutboundOrderOpened:
    """TJ-OUT-02: UPDATE on ORDER_OPENED."""

    @pytest.mark.asyncio
    async def test_TJ_OUT_02_update_order_opened_fields(self, journal_manager, valid_order_opened_event, mock_db_pool):
        """Verify all ORDER_OPENED fields are passed correctly."""
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is True

        update_query = mock_db_pool._conn.queries[0][1]
        returning_clause = update_query.split("RETURNING", 1)[1]
        assert "timeframe" not in returning_clause.lower()

        query_args = mock_db_pool._conn.queries[0][2]
        assert query_args[0] == 12345      # ticket
        assert query_args[1] == 3250.50    # entry_price
        assert query_args[2] is not None   # entry_time (datetime)
        assert query_args[5] == 3247.50    # sl
        assert query_args[6] == 3256.50    # tp


class TestOutboundOrderClosed:
    """TJ-OUT-03 through TJ-OUT-09: UPDATE on ORDER_CLOSED."""

    @pytest.mark.asyncio
    async def test_TJ_OUT_04_duration_calculation(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """duration_seconds = (exit_time - entry_time).total_seconds()."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        # close_time=1744102800 - entry_time=1712574000 (10:00 UTC)
        # But event already has close_time as int, we use datetime.fromtimestamp
        # The entry_time from mock is 2026-04-08 10:00:00 UTC
        # close_time_raw = 1744102800 → 2025-04-08 (different year)
        # Let's set close_time to be 2 hours after entry_time
        entry_ts = datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc).timestamp()
        valid_order_closed_event["close_time"] = entry_ts + 7200  # +2 hours

        await journal_manager.on_order_closed(valid_order_closed_event)

        query_args = mock_db_pool._conn.queries[1][2]  # Second query is the UPDATE
        # query_args position 3 should be duration_seconds
        duration = query_args[3]
        assert duration == 7200  # 2 hours = 7200 seconds

    @pytest.mark.asyncio
    async def test_TJ_OUT_05_result_win(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """pnl > 0 → result = WIN."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        valid_order_closed_event["profit"] = 15.50
        await journal_manager.on_order_closed(valid_order_closed_event)

        query_args = mock_db_pool._conn.queries[1][2]
        assert query_args[8] == "WIN"

    @pytest.mark.asyncio
    async def test_TJ_OUT_06_result_loss(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """pnl < 0 → result = LOSS."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        valid_order_closed_event["profit"] = -15.50
        await journal_manager.on_order_closed(valid_order_closed_event)

        query_args = mock_db_pool._conn.queries[1][2]
        assert query_args[8] == "LOSS"

    @pytest.mark.asyncio
    async def test_TJ_OUT_07_result_breakeven(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """pnl ≈ 0 → result = BE."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        valid_order_closed_event["profit"] = 0.00
        await journal_manager.on_order_closed(valid_order_closed_event)

        query_args = mock_db_pool._conn.queries[1][2]
        assert query_args[8] == "BE"


# =============================================================================
# Pillar 3: Black-box Tests (via isolated unit tests emulating API)
# =============================================================================

class TestExitReasonNormalization:
    """TJ-BB: Test _normalize_exit_reason public behavior."""

    def test_TJ_BB_tp_hit_reasons(self, journal_manager):
        """TP-related reasons normalized to TP_HIT."""
        assert journal_manager._normalize_exit_reason("TP_HIT") == "TP_HIT"
        assert journal_manager._normalize_exit_reason("tp_hit") == "TP_HIT"
        assert journal_manager._normalize_exit_reason("take_profit") == "TP_HIT"
        assert journal_manager._normalize_exit_reason("TAKE_PROFIT") == "TP_HIT"

    def test_TJ_BB_sl_hit_reasons(self, journal_manager):
        """SL-related reasons normalized to SL_HIT."""
        assert journal_manager._normalize_exit_reason("SL_HIT") == "SL_HIT"
        assert journal_manager._normalize_exit_reason("stop_loss") == "SL_HIT"
        assert journal_manager._normalize_exit_reason("STOP_LOSS") == "SL_HIT"

    def test_TJ_BB_trailing_stop(self, journal_manager):
        """TRAILING_STOP normalized."""
        assert journal_manager._normalize_exit_reason("TRAILING_STOP") == "TRAILING_STOP"
        assert journal_manager._normalize_exit_reason("trailing") == "TRAILING_STOP"

    def test_TJ_BB_signal_exit(self, journal_manager):
        """SIGNAL_EXIT normalized."""
        assert journal_manager._normalize_exit_reason("SIGNAL_EXIT") == "SIGNAL_EXIT"
        assert journal_manager._normalize_exit_reason("signal_exit") == "SIGNAL_EXIT"
        assert journal_manager._normalize_exit_reason("SIGNAL") == "SIGNAL_EXIT"

    def test_TJ_BB_unknown_reasons_default(self, journal_manager):
        """Unknown reasons default to MANUAL_CLOSE."""
        assert journal_manager._normalize_exit_reason("MAGIC") == "MANUAL_CLOSE"
        assert journal_manager._normalize_exit_reason("") == "MANUAL_CLOSE"
        assert journal_manager._normalize_exit_reason(None) == "MANUAL_CLOSE"

    def test_TJ_BB_mt5_provider_reason_aliases(self, journal_manager):
        """MT5/provider close reasons normalize to canonical exit reasons."""
        expected = {
            "TP": "TP_HIT",
            "DEAL_REASON_TP": "TP_HIT",
            "SL": "SL_HIT",
            "DEAL_REASON_SL": "SL_HIT",
            "SO": "SL_HIT",
            "STOP_OUT": "SL_HIT",
            "CLIENT": "MANUAL_CLOSE",
            "MOBILE": "MANUAL_CLOSE",
            "WEB": "MANUAL_CLOSE",
            "EXPERT": "MANUAL_CLOSE",
        }
        for reason, normalized in expected.items():
            assert journal_manager._normalize_exit_reason(reason) == normalized

    @pytest.mark.asyncio
    async def test_TJ_BB_exit_reason_preferred_over_close_reason(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """ORDER_CLOSED consumes exit_reason before close_reason/reason."""
        valid_order_closed_event["exit_reason"] = "DEAL_REASON_SL"
        valid_order_closed_event["close_reason"] = "DEAL_REASON_TP"
        valid_order_closed_event["reason"] = "TP"
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        assert await journal_manager.on_order_closed(valid_order_closed_event) is True
        query_args = mock_db_pool._conn.queries[1][2]
        assert query_args[2] == "SL_HIT"


# =============================================================================
# Pillar 4: White-box Tests — Internal Logic
# =============================================================================

class TestBedJournalManagerInit:
    """TJ-WB-01: __init__ creates TradeJournalManager."""

    def test_TJ_WB_01_init_with_valid_db_pool(self, mock_db_pool):
        """__init__ with valid db_pool → creates TradeJournalManager."""
        manager = TradeJournalManager(mock_db_pool)
        assert manager.db == mock_db_pool

    def test_TJ_WB_08_pip_values(self):
        """PIP_VALUES dict has correct pip values."""
        assert PIP_VALUES["XAUUSD"] == 0.01
        assert PIP_VALUES["EURUSD"] == 0.0001
        assert PIP_VALUES["GBPJPY"] == 0.01
        assert PIP_VALUES["DEFAULT"] == 0.0001

    def test_TJ_WB_valid_directions(self):
        """VALID_DIRECTIONS contains only BUY and SELL."""
        assert VALID_DIRECTIONS == {"BUY", "SELL"}

    def test_TJ_WB_valid_exit_reasons(self):
        """VALID_EXIT_REASONS has 5 values."""
        assert len(VALID_EXIT_REASONS) == 5
        assert "TP_HIT" in VALID_EXIT_REASONS
        assert "SL_HIT" in VALID_EXIT_REASONS
        assert "TRAILING_STOP" in VALID_EXIT_REASONS
        assert "MANUAL_CLOSE" in VALID_EXIT_REASONS
        assert "SIGNAL_EXIT" in VALID_EXIT_REASONS


# =============================================================================
# Pillar 5: Abnormal Case Tests — Error Handling & Resilience
# =============================================================================

class TestAbnormalCases:
    """TJ-AB-01 through TJ-AB-18: Error handling, race conditions, E2E lifecycle."""

    @pytest.mark.asyncio
    async def test_TJ_AB_01_db_connection_error_on_strategy_match(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """DB connection error → returns False, does NOT crash."""
        mock_db_pool.set_result("fetchval", None)
        mock_db_pool._conn.results["fetchval"] = Exception("Connection refused")
        # Mock acquire to raise exception
        class FailingConnection:
            async def fetchval(self, *args):
                raise ConnectionError("DB connection refused")

        class FailingPoolContextManager:
            async def __aenter__(self):
                return FailingConnection()
            async def __aexit__(self, *args):
                pass

        mock_db_pool.acquire = lambda: FailingPoolContextManager()

        # Should NOT raise, just return False
        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_AB_05_duplicate_order_opened_idempotent(self, journal_manager, valid_order_opened_event, mock_db_pool):
        """Duplicate ORDER_OPENED → idempotent UPDATE (no duplicate entry)."""
        mock_db_pool.set_result("execute", "UPDATE 0")  # Already updated

        # First call
        mock_db_pool.set_result("execute", "UPDATE 1")
        result1 = await journal_manager.on_order_opened(valid_order_opened_event)

        # Second call (duplicate)
        mock_db_pool.set_result("execute", "UPDATE 0")
        result2 = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result2 is False  # No rows updated on second call

    @pytest.mark.asyncio
    async def test_TJ_AB_06_order_closed_nonexistent_entry(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """on_order_closed when entry doesn't exist → returns False, doesn't crash."""
        mock_db_pool.set_result("fetchrow", None)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_AB_07_trace_id_not_found(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """trace_id not found in journal → returns False, doesn't crash."""
        mock_db_pool.set_result("fetchrow", None)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_AB_08_already_closed_entry(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """ORDER_CLOSED on already CLOSED entry → returns False, warning logged."""
        # First fetchrow returns None → entry already CLOSED
        mock_db_pool.set_result("fetchrow", None)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_AB_09_database_exception_on_opened(self, journal_manager, valid_order_opened_event, mock_db_pool):
        """DB raises exception during on_order_opened → returns False, doesn't crash."""
        class FailingConnection:
            async def execute(self, *args):
                raise ConnectionError("Connection lost")

        class FailingContextManager:
            async def __aenter__(self):
                return FailingConnection()
            async def __aexit__(self, *args):
                pass

        mock_db_pool.acquire = lambda: FailingContextManager()

        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_TJ_AB_12_concurrent_matches_unique_entries(self, journal_manager, mock_db_pool):
        """Concurrent strategy matches → entries NOT overwritten."""
        mock_db_pool.set_result("fetchval", 1)

        event1 = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-concurrent-1",
            "data": {
                "strategy_name": "strategy_A",
                "direction": "BUY",
                "symbol": "XAUUSD",
                "score": 0.9
            }
        }
        event2 = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-concurrent-2",
            "data": {
                "strategy_name": "strategy_B",
                "direction": "SELL",
                "symbol": "EURUSD",
                "score": 0.8
            }
        }

        mock_db_pool.set_result("fetchval", 1)
        result1 = await journal_manager.on_strategy_match(event1)
        result2 = await journal_manager.on_strategy_match(event2)

        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_TJ_AB_14_e2e_lifecycle(self, journal_manager, valid_strategy_match_event, valid_order_opened_event, valid_order_closed_event, mock_db_pool):
        """E2E: strategy match → TRIGGERED → ORDER_OPENED → EXECUTED → ORDER_CLOSED → CLOSED."""
        # Phase 1: Strategy Match
        mock_db_pool.set_result("fetchval", 1)
        result1 = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result1 is True

        # Phase 2: Order Opened
        mock_db_pool.set_result("execute", "UPDATE 1")
        result2 = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result2 is True

        # Phase 3: Order Closed
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)
        result3 = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result3 is True

        assert mock_db_pool.acquired
        assert len(mock_db_pool._conn.queries) >= 3


class TestTimestampConversion:
    """Test timestamp handling in all event types."""

    @pytest.mark.asyncio
    async def test_timestamp_unix_int(self, journal_manager, mock_db_pool):
        """Unix timestamp int → datetime."""
        mock_db_pool.set_result("fetchval", 1)

        event = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-ts-001",
            "data": {
                "strategy_name": "test",
                "direction": "BUY",
                "symbol": "XAUUSD",
                "origin_timestamp": 1712500800
            }
        }

        result = await journal_manager.on_strategy_match(event)
        assert result is True
        query_args = mock_db_pool._conn.queries[0][2]
        assert isinstance(query_args[8], datetime)

    @pytest.mark.asyncio
    async def test_timestamp_iso_string(self, journal_manager, valid_order_opened_event, mock_db_pool):
        """ISO format string → datetime."""
        valid_order_opened_event["time"] = "2026-04-08T10:00:00Z"
        mock_db_pool.set_result("execute", "UPDATE 1")

        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is True


# =============================================================================
# Pillar 6: Additional Branch Coverage Tests
# =============================================================================

class TestBranchCoverage:
    """Cover additional branches to reach 100% line coverage."""

    @pytest.mark.asyncio
    async def test_on_strategy_match_no_data_key(self, journal_manager, mock_db_pool):
        """Event without 'data' key → uses event directly."""
        mock_db_pool.set_result("fetchval", 1)
        event = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-no-data",
            "strategy_name": "direct_test",
            "direction": "SELL",
            "symbol": "EURUSD",
            "score": 0.7
        }

        result = await journal_manager.on_strategy_match(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_ticket_lookup_by_id_closed(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """ORDER_CLOSED with only ticket (no trace_id) → lookup by ticket."""
        valid_order_closed_event["trace_id"] = None
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-lookup-ticket",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_missing_close_time(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """Missing close_time → returns False (no fallback allowed)."""
        valid_order_closed_event["close_time"] = None
        valid_order_closed_event["time"] = None
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_origin_timestamp_datetime_object(self, journal_manager, mock_db_pool):
        """origin_timestamp is already a datetime object."""
        mock_db_pool.set_result("fetchval", 1)
        event = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-ts-dt",
            "data": {
                "strategy_name": "ts_test",
                "direction": "BUY",
                "symbol": "XAUUSD",
                "origin_timestamp": datetime(2026, 4, 8, 14, 0, 0, tzinfo=timezone.utc)
            }
        }

        result = await journal_manager.on_strategy_match(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_origin_timestamp_none(self, journal_manager, mock_db_pool):
        """origin_timestamp is None → inserted as NULL."""
        mock_db_pool.set_result("fetchval", 1)
        event = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-ts-none",
            "data": {
                "strategy_name": "ts_test",
                "direction": "BUY",
                "symbol": "XAUUSD",
                "origin_timestamp": None
            }
        }

        result = await journal_manager.on_strategy_match(event)
        assert result is True
        query_args = mock_db_pool._conn.queries[0][2]
        assert query_args[8] is None

    @pytest.mark.asyncio
    async def test_pnl_is_string_converted(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """pnl is string → converted to float."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        valid_order_closed_event["profit"] = "25.50"
        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_pnl_is_non_numeric_string(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """pnl is non-numeric string → set to None."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        valid_order_closed_event["profit"] = "not_a_number"
        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_on_strategy_match_missing_entry_price_in_closed(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """on_order_closed: no entry_price in event → pnl_pips = None."""
        valid_order_closed_event.pop("open_price", None)
        valid_order_closed_event.pop("entry_price", None)
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_update_returns_no_rows_on_close(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """Entry found but UPDATE returns 0 rows → lines 341-342."""
        call_count = {"fetchrow": 0, "fetchval": 0}

        class SelectiveMockConnection:
            async def fetchrow(self, *args):
                call_count["fetchrow"] += 1
                # First fetchrow: check entry status entry exists
                return {
                    "id": 1,
                    "trace_id": "trace-test-journal-001",
                    "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
                    "direction": "BUY",
                    "symbol": "XAUUSD"
                }

            async def fetchval(self, *args):
                call_count["fetchval"] += 1
                # fetchval on UPDATE returns None (no matching WHERE clause)
                return None

        class SelectiveContextManager:
            async def __aenter__(self):
                return SelectiveMockConnection()
            async def __aexit__(self, *args):
                pass

        original_acquire = mock_db_pool.acquire
        mock_db_pool.acquire = lambda: SelectiveContextManager()

        valid_order_closed_event["close_time"] = 1744102800

        result = await journal_manager.on_order_closed(valid_order_closed_event)

        mock_db_pool.acquire = original_acquire

        assert result is False  # UPDATE did not match any row
        assert call_count["fetchval"] >= 1
        assert call_count["fetchrow"] >= 1

    @pytest.mark.asyncio
    async def test_on_order_opened_time_is_none(self, journal_manager, valid_order_opened_event, mock_db_pool):
        """open_time is None → returns False (no fallback allowed)."""
        valid_order_opened_event["time"] = None
        valid_order_opened_event["open_time"] = None
        mock_db_pool.set_result("execute", "UPDATE 1")

        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_on_order_opened_time_is_string(self, journal_manager, valid_order_opened_event, mock_db_pool):
        """open_time is ISO string → parsed."""
        valid_order_opened_event["time"] = "2026-04-08T10:00:00Z"
        mock_db_pool.set_result("execute", "UPDATE 1")

        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_on_strategy_match_already_exists(self, journal_manager, valid_strategy_match_event, mock_db_pool):
        """Duplicate entry → ON CONFLICT DO NOTHING returns None."""
        mock_db_pool.set_result("fetchval", None)

        result = await journal_manager.on_strategy_match(valid_strategy_match_event)
        assert result is True  # Still returns True (idempotent)


    @pytest.mark.asyncio
    async def test_context_filters_is_string_coerced(self, journal_manager, mock_db_pool):
        """context_filters is not dict → coerced to empty dict (lines 89-90)."""
        mock_db_pool.set_result("fetchval", 1)
        event = {
            "type": "STRATEGY_MATCH",
            "trace_id": "trace-cf-001",
            "strategy_name": "cf_test",
            "direction": "BUY",
            "symbol": "XAUUSD",
            "context_filters": "not_a_dict"
        }
        result = await journal_manager.on_strategy_match(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_on_order_opened_missing_trace_id_returns_false(self, journal_manager):
        """Missing trace_id in on_order_opened → returns False (lines 143-144)."""
        event = {
            "type": "ORDER_OPENED",
            "ticket": 12345,
            "open_price": 3250.50
        }
        result = await journal_manager.on_order_opened(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_ticket_lookup_returns_none(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """on_order_closed: ticket lookup returns None → returns False (lines 228, 231)."""
        valid_order_closed_event["trace_id"] = None
        valid_order_closed_event["ticket"] = 99999
        mock_db_pool.set_result("fetchrow", None)  # No journal found by ticket

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_missing_both_trace_id_and_ticket(self, journal_manager):
        """Missing both trace_id and ticket → returns False (lines 233-234)."""
        event = {
            "type": "ORDER_CLOSED",
            "close_price": 3260.50,
            "profit": 10.0
        }
        result = await journal_manager.on_order_closed(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_close_time_as_iso_string(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """close_time là ISO string → parsed correctly (line 271)."""
        valid_order_closed_event["close_time"] = "2026-04-08T12:00:00Z"
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_entry_time_naive_timezone(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """entry_time has no timezone → made timezone-aware (line 284)."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": datetime(2026, 4, 8, 10, 0, 0),  # No tzinfo!
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_entry_time_is_none_no_duration(self, journal_manager, valid_order_closed_event, mock_db_pool):
        """entry_time is None → duration_seconds is None (line 287)."""
        mock_db_pool.set_result("fetchrow", {
            "id": 1,
            "trace_id": "trace-test-journal-001",
            "entry_time": None,  # No entry time!
            "direction": "BUY",
            "symbol": "XAUUSD"
        })
        mock_db_pool.set_result("fetchval", 1)

        result = await journal_manager.on_order_closed(valid_order_closed_event)
        assert result is True
        # Verify duration_seconds is None
        query_args = mock_db_pool._conn.queries[1][2]  # Second query is UPDATE
        assert query_args[3] is None  # duration_seconds

    @pytest.mark.asyncio
    async def test_db_exception_on_order_closed(self, journal_manager, mock_db_pool):
        """DB exception during on_order_closed → returns False, doesn't crash (lines 341-346)."""
        class FailingConnection:
            async def fetchrow(self, *args):
                raise ConnectionError("Connection lost during closed")

        class FailingContextManager:
            async def __aenter__(self):
                return FailingConnection()
            async def __aexit__(self, *args):
                pass

        original_acquire = mock_db_pool.acquire
        mock_db_pool.acquire = lambda: FailingContextManager()

        # Sử dụng fresh event dict để tránh mutation từ tests trước
        fresh_event = {
            "type": "ORDER_CLOSED",
            "trace_id": "trace-exception-test",
            "ticket": 55555,
            "close_price": 3260.50,
            "profit": 10.0
        }
        result = await journal_manager.on_order_closed(fresh_event)

        mock_db_pool.acquire = original_acquire
        assert result is False
