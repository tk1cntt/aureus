"""
Trade state machine for aureus_trades lifecycle management.

Valid transitions:
    PENDING → SENT, FAILED
    SENT → FILLED, FAILED, CANCELLED
    FILLED → CLOSED, FAILED
    CLOSED, FAILED, CANCELLED → (terminal, no outgoing)
"""

TRADE_TERMINAL_STATUSES = {'CLOSED', 'FAILED', 'CANCELLED'}

TRADE_ALLOWED_TRANSITIONS = {
    'PENDING': {'SENT', 'FAILED'},
    'SENT': {'FILLED', 'FAILED', 'CANCELLED'},
    'FILLED': {'CLOSED', 'FAILED'},
    'CLOSED': set(),
    'FAILED': set(),
    'CANCELLED': set(),
}


def is_trade_terminal(status: str) -> bool:
    """Return True if the given status is a terminal state."""
    return status in TRADE_TERMINAL_STATUSES


def validate_transition(current_status: str, new_status: str) -> bool:
    """
    Validate a state transition for a trade record.

    Returns False if:
        - current_status or new_status is None/empty
        - current_status equals new_status (no-op)
        - current_status is a terminal state
        - new_status is not in the allowed set for current_status

    Returns True if the transition is valid.
    """
    if not current_status or not new_status:
        return False

    if current_status == new_status:
        return False

    if current_status in TRADE_TERMINAL_STATUSES:
        return False

    allowed = TRADE_ALLOWED_TRANSITIONS.get(current_status, set())
    return new_status in allowed


def get_valid_next_states(current_status: str) -> set[str]:
    """Return the set of valid next states for a given current status."""
    if not current_status or current_status in TRADE_TERMINAL_STATUSES:
        return set()
    return TRADE_ALLOWED_TRANSITIONS.get(current_status, set()).copy()
