import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.strategy_executor import prepare_and_publish_strategy_match


class _TradeManagerReturningNone:
    def __init__(self):
        self.sl_tp_called = False

    def _calculate_entry_price(self, side, state_obj, entry_method, entry_value):
        return None

    def _calculate_sl_tp(self, *args, **kwargs):
        self.sl_tp_called = True
        return 1.0, 2.0

    def _get_tp_rr_ratio(self, result):
        return None


@pytest.mark.asyncio
async def test_rejected_none_entry_price_skips_publish_and_float(caplog):
    trade_manager = _TradeManagerReturningNone()
    publish_strategy_match = AsyncMock()
    result = {'strategy': 'OB_EDGE_TEST', 'side': 'BUY', 'order_plan': {'entry_method': 'OB_EDGE'}}

    published = await prepare_and_publish_strategy_match(
        redis_client=AsyncMock(),
        symbol='USTEC',
        res=result,
        payload={'indicator_snapshot': {}},
        signals_snapshot={},
        executor_state={},
        trade_manager=trade_manager,
        recent_candles=[],
        publish_strategy_match=publish_strategy_match,
    )

    assert published is False
    assert trade_manager.sl_tp_called is False
    publish_strategy_match.assert_not_awaited()
    assert '[EXECUTOR][USTEC]' in caplog.text
    assert 'ENTRY_PRICE_UNAVAILABLE' in caplog.text
    assert 'OB_EDGE_TEST' in caplog.text
    assert 'OB_EDGE' in caplog.text


class _TradeManagerReturningPrice:
    def __init__(self):
        self.sl_tp_called = False

    def _calculate_entry_price(self, side, state_obj, entry_method, entry_value):
        return '123.45'

    def _calculate_sl_tp(self, *args, **kwargs):
        self.sl_tp_called = True
        return 120.0, 130.0

    def _get_tp_rr_ratio(self, result):
        return 2.0


@pytest.mark.asyncio
async def test_valid_entry_price_still_publishes_strategy_match():
    trade_manager = _TradeManagerReturningPrice()
    publish_strategy_match = AsyncMock(return_value=True)
    result = {'strategy': 'VALID_STRATEGY', 'side': 'BUY', 'order_plan': {'entry_method': 'CURRENT'}}

    published = await prepare_and_publish_strategy_match(
        redis_client=AsyncMock(),
        symbol='USTEC',
        res=result,
        payload={'indicator_snapshot': {'atr_14': 2.5}},
        signals_snapshot={'trend': 'UP'},
        executor_state={},
        trade_manager=trade_manager,
        recent_candles=[],
        publish_strategy_match=publish_strategy_match,
    )

    assert published is True
    assert trade_manager.sl_tp_called is True
    assert result['entry_price'] == pytest.approx(123.45)
    assert result['sl_absolute'] == pytest.approx(120.0)
    assert result['tp_absolute'] == pytest.approx(130.0)
    assert result['tp_rr_ratio'] == pytest.approx(2.0)
    assert result['indicator_snapshot'] == {'atr_14': 2.5}
    publish_strategy_match.assert_awaited_once()
