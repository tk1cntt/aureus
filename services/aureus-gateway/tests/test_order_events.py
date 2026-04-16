import pytest
import json
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import process_message


def _published_payloads(mock_redis):
    return [json.loads(call.args[1]) for call in mock_redis.publish.call_args_list]


def _published_types(mock_redis):
    return [payload["type"] for payload in _published_payloads(mock_redis)]


def _validate_terminal_sequence(event_types):
    """ACK có thể đến trước, terminal event phải là ORDER_OPENED hoặc ORDER_FAILED duy nhất."""
    terminal = [e for e in event_types if e in ("ORDER_OPENED", "ORDER_FAILED")]
    assert len(terminal) == 1
    assert event_types[-1] in ("ORDER_OPENED", "ORDER_FAILED")
    return terminal[0]


def _apply_finalize_outcome(events, modify_success):
    """Mô phỏng sequencing phase 42.1: ACK sớm, terminal sau finalize hậu fill."""
    if modify_success:
        events.append("ORDER_OPENED")
    else:
        events.append("ORDER_FAILED")
    return events


def _extract_post_fill_trace(event):
    """Bóc tách thông tin trace fill/tp_before/tp_after/modify_result từ reason."""
    reason = event.get("reason", "")
    trace = {}
    for marker in ("filled_entry=", "tp_before=", "tp_after=", "modify_result="):
        idx = reason.find(marker)
        if idx < 0:
            trace[marker[:-1]] = ""
            continue
        start = idx + len(marker)
        end = reason.find("|", start)
        if end < 0:
            end = len(reason)
        trace[marker[:-1]] = reason[start:end].strip()
    return trace


def _assert_failed_event_contract(payload):
    assert payload["type"] == "ORDER_FAILED"
    assert payload["retcode"] > 0
    assert payload["reason"]


def _assert_no_false_success(event_types):
    assert "ORDER_OPENED" not in event_types


def _assert_post_fill_trace_fields(trace):
    assert trace["filled_entry"]
    assert trace["tp_before"]
    assert trace["tp_after"]
    assert trace["modify_result"]


def _build_modify_fail_payload(cmd_id="ord-modify-fail"):
    return {
        "type": "ORDER_FAILED",
        "cmd_id": cmd_id,
        "symbol": "XAUUSD",
        "reason": "POST_FILL_MODIFY_FAILED|filled_entry=1962.15|tp_before=1971.00|tp_after=1974.63|modify_result=retcode:10016",
        "retcode": 10016,
        "t": 1712376000000,
    }


def _build_ack_payload(cmd_id="ord-modify-fail"):
    return {"type": "ACK", "cmd_id": cmd_id, "t": 1712375999000}


def _build_opened_payload(cmd_id="ord-modify-ok"):
    return {
        "type": "ORDER_OPENED",
        "cmd_id": cmd_id,
        "symbol": "XAUUSD",
        "ticket": 44556677,
        "direction": "BUY",
        "order_type": "MARKET",
        "volume": 0.1,
        "open_price": 1962.15,
        "sl": 1954.00,
        "tp": 1974.63,
        "magic": 10001,
        "t": 1712376000001,
    }


def _assert_terminal_only_after_ack(event_types):
    ack_idx = event_types.index("ACK")
    terminal_idx = max(i for i, e in enumerate(event_types) if e in ("ORDER_OPENED", "ORDER_FAILED"))
    assert terminal_idx > ack_idx


def _assert_modify_fail_reason_has_marker(reason):
    assert reason.startswith("POST_FILL_MODIFY_FAILED")


def _assert_opened_shape(payload):
    assert payload["type"] == "ORDER_OPENED"
    assert payload["ticket"] > 0


def _assert_event_channel(mock_redis):
    for call in mock_redis.publish.call_args_list:
        assert call.args[0] == "aureus:mt5:events"


def _assert_terminal_is_failed(terminal):
    assert terminal == "ORDER_FAILED"


def _assert_terminal_is_opened(terminal):
    assert terminal == "ORDER_OPENED"


def _assert_ack_present(event_types):
    assert "ACK" in event_types


def _assert_sequence_shape(event_types):
    assert len(event_types) == 2


def _assert_failed_payload_published(mock_redis):
    failed = [p for p in _published_payloads(mock_redis) if p["type"] == "ORDER_FAILED"]
    assert len(failed) == 1
    return failed[0]


def _assert_opened_payload_published(mock_redis):
    opened = [p for p in _published_payloads(mock_redis) if p["type"] == "ORDER_OPENED"]
    assert len(opened) == 1
    return opened[0]


def _assert_no_failed_when_success(event_types):
    assert "ORDER_FAILED" not in event_types


def _assert_no_opened_when_failed(event_types):
    assert "ORDER_OPENED" not in event_types


def _assert_post_fill_trace_has_recalc(trace):
    assert trace["tp_before"] != trace["tp_after"]


def _assert_reason_has_retcode(reason):
    assert "retcode:" in reason


def _assert_terminal_count(event_types):
    terminal = [e for e in event_types if e in ("ORDER_OPENED", "ORDER_FAILED")]
    assert len(terminal) == 1


@pytest.mark.asyncio
async def test_phase_42_1_terminal_opened_after_finalize_success(mock_redis):
    cmd_id = "ord-modify-ok"
    await process_message(mock_redis, _build_ack_payload(cmd_id), source="TCP")
    await process_message(mock_redis, _build_opened_payload(cmd_id), source="TCP")

    event_types = _published_types(mock_redis)
    _assert_ack_present(event_types)
    _assert_sequence_shape(event_types)
    _assert_terminal_count(event_types)
    _assert_terminal_only_after_ack(event_types)

    terminal = _validate_terminal_sequence(event_types)
    _assert_terminal_is_opened(terminal)
    _assert_no_failed_when_success(event_types)
    _assert_event_channel(mock_redis)

    opened_payload = _assert_opened_payload_published(mock_redis)
    _assert_opened_shape(opened_payload)


@pytest.mark.asyncio
async def test_phase_42_1_modify_fail_emits_failed_only(mock_redis):
    cmd_id = "ord-modify-fail"
    await process_message(mock_redis, _build_ack_payload(cmd_id), source="TCP")
    await process_message(mock_redis, _build_modify_fail_payload(cmd_id), source="TCP")

    event_types = _published_types(mock_redis)
    _assert_ack_present(event_types)
    _assert_sequence_shape(event_types)
    _assert_terminal_count(event_types)
    _assert_terminal_only_after_ack(event_types)

    terminal = _validate_terminal_sequence(event_types)
    _assert_terminal_is_failed(terminal)
    _assert_no_opened_when_failed(event_types)

    failed_payload = _assert_failed_payload_published(mock_redis)
    _assert_failed_event_contract(failed_payload)
    _assert_modify_fail_reason_has_marker(failed_payload["reason"])
    _assert_reason_has_retcode(failed_payload["reason"])


@pytest.mark.asyncio
async def test_phase_42_1_modify_fail_trace_fields_present(mock_redis):
    payload = _build_modify_fail_payload("ord-trace")
    await process_message(mock_redis, payload, source="TCP")

    failed_payload = _assert_failed_payload_published(mock_redis)
    _assert_failed_event_contract(failed_payload)

    trace = _extract_post_fill_trace(failed_payload)
    _assert_post_fill_trace_fields(trace)
    _assert_post_fill_trace_has_recalc(trace)
    assert trace["modify_result"].startswith("retcode:")


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.hget = AsyncMock(return_value=None)
    r.hset = AsyncMock()
    r.xadd = AsyncMock()
    r.publish = AsyncMock()
    return r

@pytest.mark.asyncio
async def test_order_opened_event(mock_redis):
    data = {
        "type": "ORDER_OPENED", "cmd_id": "ord-001", "symbol": "XAUUSD",
        "ticket": 12345678, "direction": "BUY", "order_type": "MARKET",
        "volume": 0.1, "open_price": 1960.25, "sl": 1950.50, "tp": 1970.00,
        "magic": 10001, "t": 1712376000000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "aureus:mt5:events"

@pytest.mark.asyncio
async def test_order_closed_event(mock_redis):
    data = {
        "type": "ORDER_CLOSED", "symbol": "XAUUSD", "ticket": 12345678,
        "direction": "BUY", "volume": 0.1, "open_price": 1960.25,
        "close_price": 1968.50, "profit": 82.50, "commission": -0.70,
        "swap": 0.00, "magic": 10001, "t": 1712379600000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_order_failed_event(mock_redis):
    data = {
        "type": "ORDER_FAILED", "cmd_id": "ord-001", "symbol": "XAUUSD",
        "reason": "INSUFFICIENT_MARGIN", "retcode": 10019, "t": 1712376000000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_ack_event(mock_redis):
    data = {"type": "ACK", "cmd_id": "ord-001", "t": 1712376000000}
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_nack_event(mock_redis):
    data = {"type": "NACK", "cmd_id": "ord-001", "reason": "DUPLICATE", "t": 1712376000000}
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_order_event_invalid_fields(mock_redis):
    """ORDER_OPENED missing required 'ticket' field should fail validation."""
    data = {
        "type": "ORDER_OPENED", "cmd_id": "ord-001", "symbol": "XAUUSD",
        "direction": "BUY", "t": 1712376000000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is False
    mock_redis.publish.assert_not_called()

@pytest.mark.asyncio
async def test_order_event_publishes_correct_channel(mock_redis):
    """Verify events go to aureus:mt5:events channel."""
    data = {
        "type": "ORDER_OPENED", "cmd_id": "ord-002", "symbol": "BTCUSD",
        "ticket": 99999, "direction": "SELL", "order_type": "LIMIT",
        "volume": 0.5, "open_price": 60000.0, "sl": 61000.0, "tp": 58000.0,
        "magic": 20001, "t": 1712376000000
    }
    await process_message(mock_redis, data, source="TCP")
    channel = mock_redis.publish.call_args[0][0]
    assert channel == "aureus:mt5:events"

@pytest.mark.asyncio
async def test_order_event_json_payload(mock_redis):
    """Verify published JSON contains expected fields."""
    data = {
        "type": "ORDER_CLOSED", "symbol": "XAUUSD", "ticket": 12345678,
        "direction": "BUY", "volume": 0.1, "open_price": 1960.25,
        "close_price": 1968.50, "profit": 82.50, "commission": -0.70,
        "swap": 0.00, "magic": 10001, "t": 1712379600000
    }
    await process_message(mock_redis, data, source="TCP")
    published_json = mock_redis.publish.call_args[0][1]
    parsed = json.loads(published_json)
    assert parsed["type"] == "ORDER_CLOSED"
    assert parsed["ticket"] == 12345678
    assert parsed["profit"] == 82.50

@pytest.mark.asyncio
async def test_trade_history_event_with_error_missing_fields(mock_redis):
    """Test Backward compatibility for old EA sending error without count/from_time."""
    data = {
        "type": "TRADE_HISTORY",
        "trades": [],
        "error": "invalid_time_range"
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()
    
    # Verify the published data has the error field
    published_json = mock_redis.publish.call_args[0][1]
    parsed = json.loads(published_json)
    assert parsed["type"] == "TRADE_HISTORY"
    assert parsed["error"] == "invalid_time_range"
