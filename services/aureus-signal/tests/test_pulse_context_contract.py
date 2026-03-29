import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pandas as pd

# Ensure engine module can be imported when running from repository root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.ai_validator import AIValidator, AIBrainClient, ContextBuilder


class TestPulseContextBuilder(unittest.TestCase):
    def test_build_pulse_context_uses_latest_60_records_and_stable_payload_schema(self):
        builder = ContextBuilder()

        records = []
        base_t = 1710000000
        for idx in range(70):
            records.append(
                {
                    "t": base_t + idx * 60,
                    "price": 2000.0 + idx,
                    "signals": {
                        "htf_trend": {"value": "BULLISH" if idx % 2 == 0 else "BEARISH"},
                        "market_session": {"value": "LONDON" if idx % 3 == 0 else "NEW_YORK"},
                        "zigzag": {"kind": "HH" if idx % 4 == 0 else "HL"},
                        "events": [
                            {"tag": "hh" if idx % 2 == 0 else "ll", "direction": "UP", "price": 2000.0 + idx},
                            {"tag": "choch_up" if idx % 5 == 0 else "bos_up", "direction": "UP"},
                        ],
                    },
                }
            )

        state = SimpleNamespace(log_signal_normalize=records)
        df = pd.DataFrame({"c": [2000.0 + i for i in range(70)]})

        context = builder.build_pulse_context(
            symbol="BTCUSD",
            df=df,
            state_obj=state,
            trigger_events=["periodic_pulse", "choch_up"],
        )

        self.assertIn("[MARKET_PULSE_CONTEXT_V2]", context)
        self.assertIn("PAYLOAD_JSON=", context)

        payload_text = context.split("PAYLOAD_JSON=", 1)[1].split("\nOUTPUT_CONTRACT=", 1)[0]
        payload = json.loads(payload_text)

        self.assertEqual(payload["schema"], "pulse_context_v2")
        self.assertEqual(payload["symbol"], "BTCUSD")
        self.assertEqual(payload["trigger_events"], ["PERIODIC_PULSE", "CHOCH_UP"])

        window = payload["window"]
        self.assertEqual(window["record_count"], 60)
        self.assertEqual(window["first_t"], base_t + 10 * 60)
        self.assertEqual(window["last_t"], base_t + 69 * 60)

        log_window = payload["log_signal_normalize_window"]
        self.assertEqual(len(log_window), 60)
        self.assertEqual(log_window[0]["t"], base_t + 10 * 60)
        self.assertEqual(log_window[-1]["t"], base_t + 69 * 60)

        first_record = log_window[0]
        self.assertIn("price", first_record)
        self.assertEqual(set(first_record.keys()), {"t", "price", "signals"})
        self.assertEqual(set(first_record["signals"].keys()), {"htf_trend", "market_session", "zigzag_kind", "events"})
        self.assertLessEqual(len(first_record["signals"]["events"]), 4)

        self.assertLessEqual(len(payload["recent_events"]), 12)
        self.assertIn("bias_anchors", payload)
        self.assertIn("swing_balance", payload["bias_anchors"])
        self.assertLess(len(context), 15000)


class TestPulseContractNormalization(unittest.IsolatedAsyncioTestCase):
    async def test_generate_pulse_normalizes_payload_to_flat_contract(self):
        client = AIBrainClient(base_url="http://localhost:8000/v1")

        fake_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "narrative": "  Bias remains bullish by anchors.  ",
                                "sentiment": "bullish",
                                "aci": "91.7",
                                "debate_log": {
                                    "trend": {"anchor": "htf_trend=BULLISH"},
                                    "liquidity": ["sweeps limited"],
                                    "skeptic": "Need BOS follow-through",
                                },
                            }
                        )
                    )
                )
            ]
        )

        with patch.object(client.client.chat.completions, "create", AsyncMock(return_value=fake_response)):
            result = await client.generate_pulse("CTX")

        self.assertEqual(result["sentiment"], "BULLISH")
        self.assertEqual(result["aci"], 91)
        self.assertEqual(result["narrative"], "Bias remains bullish by anchors.")
        self.assertIsInstance(result["debate_log"], dict)
        self.assertIn("htf_trend", result["debate_log"]["trend"])
        self.assertEqual(result["debate_log"]["skeptic"], "Need BOS follow-through")

    async def test_generate_pulse_returns_fallback_when_model_output_invalid(self):
        client = AIBrainClient(base_url="http://localhost:8000/v1")

        fake_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps([{"narrative": "invalid"}]))
                )
            ]
        )

        with patch.object(client.client.chat.completions, "create", AsyncMock(return_value=fake_response)):
            result = await client.generate_pulse("CTX")

        self.assertEqual(result["sentiment"], "NEUTRAL")
        self.assertEqual(result["aci"], 50)
        self.assertIn("fallback", result["debate_log"]["trend"].lower())

    async def test_generate_pulse_returns_fallback_when_client_raises(self):
        client = AIBrainClient(base_url="http://localhost:8000/v1")

        with patch.object(
            client.client.chat.completions,
            "create",
            AsyncMock(side_effect=RuntimeError("transport down")),
        ):
            result = await client.generate_pulse("CTX")

        self.assertEqual(result["sentiment"], "NEUTRAL")
        self.assertEqual(result["aci"], 50)
        self.assertIn("transport down", result["debate_log"]["trend"])  # reason should be preserved

    async def test_analyze_market_request_payload_includes_system_prompt_and_user_context(self):
        validator = AIValidator(base_url="http://localhost:8000/v1")

        fake_payload = {
            "narrative": "Anchors mixed.",
            "sentiment": "NEUTRAL",
            "aci": 50,
            "debate_log": {
                "trend": "mixed",
                "liquidity": "balanced",
                "skeptic": "await confirmation",
            },
        }

        with patch.object(validator.brain, "generate_pulse", AsyncMock(return_value=fake_payload)):
            state = SimpleNamespace(log_signal_normalize=[])
            df = pd.DataFrame({"c": [1.0, 2.0, 3.0]})
            result = await validator.analyze_market("BTCUSD", df, state)

        self.assertIn("request_payload", result)
        request_payload = result["request_payload"]
        self.assertIn("system_prompt", request_payload)
        self.assertIn("user_context", request_payload)
        self.assertEqual(request_payload["model"], validator.brain.model)
        self.assertEqual(request_payload["temperature"], 0.0)
        self.assertIn("PAYLOAD_JSON=", request_payload["user_context"])


class TestPulsePromptGuardrails(unittest.TestCase):
    def test_get_pulse_system_prompt_enforces_structured_detail_and_token_limits(self):
        client = AIBrainClient(base_url="http://localhost:8000/v1")
        prompt = client.get_pulse_system_prompt()

        self.assertIn("narrative must be 3 concise parts", prompt)
        self.assertIn("Context:", prompt)
        self.assertIn("Structure:", prompt)
        self.assertIn("Outlook:", prompt)
        self.assertIn("narrative length target: 60-110 words total", prompt)
        self.assertIn("No invention", prompt)


if __name__ == "__main__":
    unittest.main()
