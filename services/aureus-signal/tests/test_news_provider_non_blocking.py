import asyncio
import os
import sys
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.live_engine import news_refresh_worker
from engine.signals.news_provider import NewsProvider


class TestNewsProviderNonBlocking(unittest.TestCase):
    def test_get_todays_events_returns_empty_when_cache_missing_without_fetch(self):
        current_time = datetime(2026, 3, 29, 10, 0, 0)

        with (
            patch.object(NewsProvider, "get_cached", return_value=[]),
            patch.object(NewsProvider, "fetch_this_week", side_effect=AssertionError("network fetch must not be called")),
        ):
            events = NewsProvider.get_todays_events(current_time)

        self.assertEqual(events, [])

    def test_get_todays_events_filters_today_from_cache_only(self):
        current_time = datetime(2026, 3, 29, 10, 0, 0)
        cached_events = [
            {"date_gmt7": "2026-03-29 09:30:00", "currency": "USD", "impact": "high"},
            {"date_gmt7": "2026-03-29 14:00:00", "currency": "EUR", "impact": "medium"},
            {"date_gmt7": "2026-03-30 08:00:00", "currency": "JPY", "impact": "low"},
        ]

        with (
            patch.object(NewsProvider, "get_cached", return_value=cached_events),
            patch.object(NewsProvider, "fetch_this_week", side_effect=AssertionError("network fetch must not be called")),
        ):
            events = NewsProvider.get_todays_events(current_time)

        self.assertEqual(len(events), 2)
        self.assertTrue(all(e["date_gmt7"].startswith("2026-03-29") for e in events))


class TestNewsRefreshWorker(unittest.IsolatedAsyncioTestCase):
    async def test_news_refresh_worker_runs_fetch_in_to_thread(self):
        mock_to_thread = AsyncMock(return_value=None)
        mock_fetch = Mock(return_value=[])

        async def _cancel_sleep(_seconds):
            raise asyncio.CancelledError()

        with (
            patch("engine.live_engine.NewsProvider.fetch_this_week", mock_fetch),
            patch("engine.live_engine.asyncio.to_thread", mock_to_thread),
            patch("engine.live_engine.asyncio.sleep", side_effect=_cancel_sleep),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await news_refresh_worker(1)

        mock_to_thread.assert_awaited_once_with(mock_fetch)


if __name__ == "__main__":
    unittest.main()
