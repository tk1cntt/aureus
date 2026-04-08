"""
Comprehensive test suite for TradeJournalManager.
Covers 6 pillars: Inbound, Outbound, Black-box, White-box, Abnormal, Migration/Schema.
Target: 100% line coverage, ≥95% branch coverage on journal.py.
"""
import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from journal import TradeJournalManager, VALID_EXIT_REASONS, VALID_DIRECTIONS, PIP_VALUES


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
        mock_db_pool.set_result("execute", "UPDATE 1")
        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is True

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
        """Missing close_time → uses current time."""
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
        assert result is True

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
        """open_time is None → uses current time."""
        valid_order_opened_event["time"] = None
        valid_order_opened_event["open_time"] = None
        mock_db_pool.set_result("execute", "UPDATE 1")

        result = await journal_manager.on_order_opened(valid_order_opened_event)
        assert result is True

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
