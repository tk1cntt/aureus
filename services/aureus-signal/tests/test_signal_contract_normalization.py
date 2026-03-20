import asyncio
import json
import os
import sys
import unittest

# Ensure engine module can be imported when running from repository root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.live_engine import (
    ENGINE_VERSION,
    SPEC_VERSION,
    emit_registry_rejections,
    enrich_registry_rejections_with_contract_metadata,
    enrich_strategy_decisions_with_contract_metadata,
)
from engine.signal_factory import build_normalized_signal_snapshot


class _DummyState:
    def __init__(self, transient_signals=None):
        self.transient_signals = transient_signals or {}


class TestSignalContractNormalization(unittest.TestCase):
    def test_normalized_snapshot_contains_all_required_keys_when_missing(self):
        snapshot = build_normalized_signal_snapshot(signals={}, state=_DummyState())

        self.assertEqual(
            set(snapshot.keys()),
            {"zigzag_state", "ob_state", "choch_state", "fvg_state", "trend_filter_state"},
        )
        self.assertEqual(snapshot["zigzag_state"]["status"], "MISSING")
        self.assertEqual(snapshot["ob_state"]["status"], "MISSING")
        self.assertEqual(snapshot["choch_state"]["status"], "MISSING")
        self.assertEqual(snapshot["fvg_state"]["status"], "MISSING")
        self.assertEqual(snapshot["trend_filter_state"]["status"], "MISSING")

    def test_normalized_snapshot_uses_transient_values_when_present(self):
        state = _DummyState(
            transient_signals={
                "zigzag_state": {"status": "OK", "points": 3},
                "ob_state": {"status": "OK", "blocks": 1},
                "choch_state": {"status": "OK", "direction": "UP"},
                "fvg_state": {"status": "OK", "gaps": 2},
                "trend_filter_state": {"status": "OK", "trend": "BULL"},
            }
        )

        snapshot = build_normalized_signal_snapshot(signals={}, state=state)

        self.assertEqual(snapshot["zigzag_state"]["status"], "OK")
        self.assertEqual(snapshot["ob_state"]["status"], "OK")
        self.assertEqual(snapshot["choch_state"]["status"], "OK")
        self.assertEqual(snapshot["fvg_state"]["status"], "OK")
        self.assertEqual(snapshot["trend_filter_state"]["status"], "OK")


class TestDecisionVersionMetadata(unittest.TestCase):
    def test_enrichment_adds_spec_engine_strategy_versions_and_snapshot(self):
        normalized_snapshot = {"zigzag_state": {"status": "OK"}}
        strategy_results = [
            {"strategy": "TREND_CONT", "strategy_version": "1.2.3", "t": 1710000000},
            {"strategy": "ORDER_FLOW_DOM", "t": 1710000060},
        ]

        enriched = enrich_strategy_decisions_with_contract_metadata(strategy_results, normalized_snapshot)

        self.assertEqual(len(enriched), 2)
        self.assertEqual(enriched[0]["spec_version"], SPEC_VERSION)
        self.assertEqual(enriched[0]["engine_version"], ENGINE_VERSION)
        self.assertEqual(enriched[0]["strategy_version"], "1.2.3")
        self.assertEqual(enriched[0]["normalized_signal_snapshot"], normalized_snapshot)

        self.assertEqual(enriched[1]["strategy_version"], "v0")
        self.assertEqual(enriched[1]["normalized_signal_snapshot"], normalized_snapshot)


class _FakeRedis:
    def __init__(self):
        self.calls = []

    async def xadd(self, stream, fields):
        self.calls.append((stream, fields))


class TestRegistryRejectionMetadata(unittest.TestCase):
    def test_rejection_enrichment_applies_required_defaults(self):
        normalized_snapshot = {"trend_filter_state": {"status": "OK"}}
        raw = [
            {
                "phase": "validate_entry",
                "reason_code": "VALIDATION_RULE_FAILED",
                "details": {
                    "strategy": "PHASED_REJECT",
                    "strategy_id": 404,
                    "strategy_version": "v1.5",
                    "t": 1710001000,
                },
            },
            {
                "phase": "register",
                "details": {
                    "strategy": "INCOMPATIBLE_DEMO",
                    "strategy_id": 202,
                },
            },
        ]

        enriched = enrich_registry_rejections_with_contract_metadata(
            symbol="XAUUSD",
            rejections=raw,
            normalized_snapshot=normalized_snapshot,
            default_t=1710002000,
        )

        self.assertEqual(len(enriched), 2)
        self.assertEqual(enriched[0]["symbol"], "XAUUSD")
        self.assertEqual(enriched[0]["status"], "REJECTED")
        self.assertEqual(enriched[0]["spec_version"], SPEC_VERSION)
        self.assertEqual(enriched[0]["engine_version"], ENGINE_VERSION)
        self.assertEqual(enriched[0]["strategy_version"], "v1.5")
        self.assertEqual(enriched[0]["t"], 1710001000)
        self.assertEqual(enriched[0]["origin_timestamp"], 1710001000)
        self.assertEqual(enriched[0]["normalized_signal_snapshot"], normalized_snapshot)

        self.assertEqual(enriched[1]["reason_code"], "UNKNOWN_REJECTION")
        self.assertEqual(enriched[1]["strategy_version"], "v0")
        self.assertEqual(enriched[1]["t"], 1710002000)
        self.assertEqual(enriched[1]["origin_timestamp"], 1710002000)

    def test_emit_registry_rejections_writes_order_rejected_events(self):
        redis_client = _FakeRedis()
        payloads = [
            {
                "strategy": "PHASED_REJECT",
                "reason_code": "VALIDATION_RULE_FAILED",
                "t": 1710001000,
            }
        ]

        asyncio.run(emit_registry_rejections(redis_client, "EURUSD", payloads))

        self.assertEqual(len(redis_client.calls), 1)
        stream, fields = redis_client.calls[0]
        self.assertEqual(stream, "aureus:stream:EURUSD:orders")
        self.assertEqual(fields["type"], "ORDER_REJECTED")
        decoded = json.loads(fields["data"])
        self.assertEqual(decoded["symbol"], "EURUSD")
        self.assertEqual(decoded["strategy"], "PHASED_REJECT")


if __name__ == "__main__":
    unittest.main()
