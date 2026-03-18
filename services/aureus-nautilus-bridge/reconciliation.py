from typing import Dict, Optional

from mapper import build_execution_event, map_status


TERMINAL_STATUSES = {"FILLED", "CANCELED", "REJECTED", "RISK_BLOCKED"}

ALLOWED_TRANSITIONS = {
    "ORDER_ACCEPTED": {"PARTIAL_FILL", "FILLED", "CANCELED", "REJECTED", "RISK_BLOCKED"},
    "PARTIAL_FILL": {"PARTIAL_FILL", "FILLED", "CANCELED", "REJECTED", "RISK_BLOCKED"},
    "FILLED": set(),
    "CANCELED": set(),
    "REJECTED": set(),
    "RISK_BLOCKED": set(),
}


def is_terminal_status(status: Optional[str]) -> bool:
    return str(status or "").upper() in TERMINAL_STATUSES


def can_apply_status(trace_id: str, new_status: str, status_by_trace: Dict[str, str]) -> bool:
    current = status_by_trace.get(trace_id)
    new_status = map_status(new_status)

    if not current:
        return True

    current = map_status(current)
    if current == new_status:
        return False
    if is_terminal_status(current):
        return False

    return new_status in ALLOWED_TRANSITIONS.get(current, set())


def normalize_execution_report(intent: dict, adapter_report: dict, status_by_trace: Dict[str, str]) -> Optional[dict]:
    event = build_execution_event(intent, adapter_report)
    trace_id = event["trace_id"]
    if not can_apply_status(trace_id, event["status"], status_by_trace):
        return None

    status_by_trace[trace_id] = event["status"]
    return event
