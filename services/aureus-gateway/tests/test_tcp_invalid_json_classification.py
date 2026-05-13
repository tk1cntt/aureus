import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from main import handle_tcp_client


class MockReader:
    def __init__(self, lines):
        self._lines = list(lines)

    async def readline(self):
        if self._lines:
            return self._lines.pop(0)
        return b""


class MockWriter:
    def __init__(self):
        self.closed = False

    def get_extra_info(self, name):
        if name == "peername":
            return ("127.0.0.1", 55555)
        return None

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


@pytest.mark.asyncio
async def test_tcp_handler_ignores_empty_and_non_json_probe_without_invalid_json_warning(caplog):
    reader = MockReader([b"\n", b"healthcheck\n", b""])
    writer = MockWriter()

    with patch("main.process_message", new=AsyncMock(return_value=True)) as process_message:
        with caplog.at_level(logging.DEBUG, logger="aureus-gateway.main"):
            await handle_tcp_client(reader, writer, AsyncMock())

    process_message.assert_not_awaited()
    assert "Invalid JSON" not in caplog.text
    assert "Non-JSON TCP probe/ignored" in caplog.text
    assert writer.closed is True


@pytest.mark.asyncio
async def test_tcp_handler_keeps_invalid_json_warning_for_json_like_payload(caplog):
    reader = MockReader([b"{bad json}\n", b""])
    writer = MockWriter()

    with patch("main.process_message", new=AsyncMock(return_value=True)) as process_message:
        with caplog.at_level(logging.WARNING, logger="aureus-gateway.main"):
            await handle_tcp_client(reader, writer, AsyncMock())

    process_message.assert_not_awaited()
    assert "Invalid JSON" in caplog.text


@pytest.mark.asyncio
async def test_tcp_handler_processes_valid_json_and_counts_success(caplog):
    payload = {"type": "TICK", "symbol": "XAUUSD", "t": 1778689200000, "bid": 1.0, "ask": 1.1, "vol": 2.0}
    reader = MockReader([json.dumps(payload).encode("utf-8") + b"\n", b""])
    writer = MockWriter()

    with patch("main.process_message", new=AsyncMock(return_value=True)) as process_message:
        with caplog.at_level(logging.INFO, logger="aureus-gateway.main"):
            await handle_tcp_client(reader, writer, AsyncMock())

    process_message.assert_awaited_once()
    sent = process_message.await_args.args[1]
    assert sent["symbol"] == "XAUUSD"
    assert sent["writer"] is writer
    assert "Total cumulative messages: 1" in caplog.text
