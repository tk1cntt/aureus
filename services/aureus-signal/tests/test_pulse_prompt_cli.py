import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

# Ensure script module can be imported when running from repository root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import pulse_prompt_cli as cli


class TestPulsePromptCLI(unittest.TestCase):
    def _fixture_path(self) -> str:
        return os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "pulse_log_signal_normalize.json",
        )

    def test_extract_log_signal_records_filters_invalid_and_sorts(self):
        with open(self._fixture_path(), "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        records = cli.extract_log_signal_records(payload)

        self.assertEqual(len(records), 4)
        self.assertEqual([row["t"] for row in records], [1710000000, 1710000060, 1710000120, 1710000240])
        self.assertEqual(records[0].get("price"), 2010.5)
        self.assertNotIn("price", records[1])

    def test_load_records_from_file_applies_limit(self):
        records = cli.load_records_from_file(self._fixture_path(), limit=2)
        self.assertEqual([row["t"] for row in records], [1710000120, 1710000240])

    def test_build_price_frame_resolves_price_from_signals_and_events(self):
        with open(self._fixture_path(), "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        records = cli.extract_log_signal_records(payload)
        frame = cli.build_price_frame(records)

        closes = frame["c"].tolist()
        self.assertEqual(closes, [2010.5, 2012.0, 2014.25, 2016.75])


class TestPulsePromptCLIRun(unittest.IsolatedAsyncioTestCase):
    async def test_run_prompt_test_without_llm(self):
        records = [
            {"t": 1710000000, "price": 2010.5, "signals": {"events": [{"tag": "hl", "price": 2010.5}]}}
        ]

        with patch.object(cli, "ContextBuilder") as mock_builder_cls:
            mock_builder = mock_builder_cls.return_value
            mock_builder.build_pulse_context.return_value = "PULSE_CONTEXT"

            output = await cli.run_prompt_test(
                symbol="BTCUSD",
                records=records,
                trigger_events=["PERIODIC_PULSE"],
                request_llm=False,
                llm_base_url="http://localhost:8000/v1",
                model="",
            )

        self.assertEqual(output["symbol"], "BTCUSD")
        self.assertEqual(output["record_count"], 1)
        self.assertEqual(output["context"], "PULSE_CONTEXT")
        self.assertNotIn("pulse", output)

    async def test_run_prompt_test_with_llm(self):
        records = [
            {"t": 1710000000, "price": 2010.5, "signals": {"events": [{"tag": "hl", "price": 2010.5}]}}
        ]

        with patch.object(cli, "ContextBuilder") as mock_builder_cls, patch.object(cli, "AIBrainClient") as mock_brain_cls:
            mock_builder = mock_builder_cls.return_value
            mock_builder.build_pulse_context.return_value = "PULSE_CONTEXT"

            mock_brain = mock_brain_cls.return_value
            mock_brain.generate_pulse = AsyncMock(
                return_value={
                    "narrative": "Anchor-backed pulse",
                    "sentiment": "NEUTRAL",
                    "aci": 51,
                    "debate_log": "anchor-only",
                }
            )

            output = await cli.run_prompt_test(
                symbol="BTCUSD",
                records=records,
                trigger_events=["PERIODIC_PULSE"],
                request_llm=True,
                llm_base_url="http://localhost:8000/v1",
                model="meta-llama/Llama-3.2-3B-Instruct",
            )

        mock_brain_cls.assert_called_once_with(base_url="http://localhost:8000/v1")
        mock_brain.set_model.assert_called_once_with("meta-llama/Llama-3.2-3B-Instruct")
        mock_brain.generate_pulse.assert_awaited_once_with("PULSE_CONTEXT")
        self.assertEqual(output["pulse"]["sentiment"], "NEUTRAL")


if __name__ == "__main__":
    unittest.main()
