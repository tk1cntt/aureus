"""Tests for trade state machine transition validation."""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from state_machine import (
    TRADE_TERMINAL_STATUSES,
    TRADE_ALLOWED_TRANSITIONS,
    is_trade_terminal,
    validate_transition,
    get_valid_next_states,
)


# --- Valid transition tests ---

class TestValidTransitions:
    @pytest.mark.parametrize("current,new", [
        ('PENDING', 'SENT'),
        ('PENDING', 'FAILED'),
        ('SENT', 'FILLED'),
        ('SENT', 'FAILED'),
        ('SENT', 'CANCELLED'),
        ('FILLED', 'CLOSED'),
        ('FILLED', 'FAILED'),
    ])
    def test_valid_transitions(self, current, new):
        assert validate_transition(current, new) is True

    def test_pending_to_sent(self):
        assert validate_transition('PENDING', 'SENT') is True

    def test_sent_to_filled(self):
        assert validate_transition('SENT', 'FILLED') is True

    def test_filled_to_closed(self):
        assert validate_transition('FILLED', 'CLOSED') is True


# --- Invalid transition tests ---

class TestInvalidTransitions:
    @pytest.mark.parametrize("current,new", [
        ('PENDING', 'FILLED'),      # skip SENT
        ('PENDING', 'CLOSED'),      # skip multiple
        ('SENT', 'PENDING'),        # backward
        ('SENT', 'CLOSED'),         # skip FILLED
        ('FILLED', 'SENT'),         # backward
        ('FILLED', 'PENDING'),      # backward
        ('CLOSED', 'SENT'),         # from terminal
        ('FAILED', 'PENDING'),      # from terminal
        ('CANCELLED', 'SENT'),      # from terminal
    ])
    def test_invalid_transitions(self, current, new):
        assert validate_transition(current, new) is False


# --- Terminal state tests ---

class TestTerminalStates:
    def test_terminal_statuses_set(self):
        assert TRADE_TERMINAL_STATUSES == {'CLOSED', 'FAILED', 'CANCELLED'}

    @pytest.mark.parametrize("status", ['CLOSED', 'FAILED', 'CANCELLED'])
    def test_is_trade_terminal_true(self, status):
        assert is_trade_terminal(status) is True

    @pytest.mark.parametrize("status", ['PENDING', 'SENT', 'FILLED'])
    def test_is_trade_terminal_false(self, status):
        assert is_trade_terminal(status) is False

    @pytest.mark.parametrize("status", ['CLOSED', 'FAILED', 'CANCELLED'])
    def test_terminal_reject_all_outgoing(self, status):
        for next_status in ['PENDING', 'SENT', 'FILLED', 'CLOSED', 'FAILED', 'CANCELLED']:
            assert validate_transition(status, next_status) is False


# --- Same status test ---

class TestSameStatus:
    @pytest.mark.parametrize("status", ['PENDING', 'SENT', 'FILLED', 'CLOSED', 'FAILED', 'CANCELLED'])
    def test_same_status_returns_false(self, status):
        assert validate_transition(status, status) is False


# --- Edge cases ---

class TestEdgeCases:
    def test_none_current_status(self):
        assert validate_transition(None, 'SENT') is False

    def test_none_new_status(self):
        assert validate_transition('PENDING', None) is False

    def test_empty_current_status(self):
        assert validate_transition('', 'SENT') is False

    def test_empty_new_status(self):
        assert validate_transition('PENDING', '') is False

    def test_unknown_current_status(self):
        assert validate_transition('UNKNOWN', 'SENT') is False

    def test_get_valid_next_states_pending(self):
        assert get_valid_next_states('PENDING') == {'SENT', 'FAILED'}

    def test_get_valid_next_states_sent(self):
        assert get_valid_next_states('SENT') == {'FILLED', 'FAILED', 'CANCELLED'}

    def test_get_valid_next_states_filled(self):
        assert get_valid_next_states('FILLED') == {'CLOSED', 'FAILED'}

    def test_get_valid_next_states_terminal(self):
        assert get_valid_next_states('CLOSED') == set()
        assert get_valid_next_states('FAILED') == set()
        assert get_valid_next_states('CANCELLED') == set()

    def test_get_valid_next_states_none(self):
        assert get_valid_next_states(None) == set()

    def test_allowed_transitions_all_states_defined(self):
        expected_states = {'PENDING', 'SENT', 'FILLED', 'CLOSED', 'FAILED', 'CANCELLED'}
        assert set(TRADE_ALLOWED_TRANSITIONS.keys()) == expected_states
