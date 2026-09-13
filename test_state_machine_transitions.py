"""Tests for state machine transitions."""
import pytest
from backend.models.schemas import ChangeState
from backend.state.machine import (
    can_transition, assert_transition, InvalidStateTransition, TRANSITIONS
)


def test_valid_transitions_smoke():
    assert can_transition(ChangeState.CREATED, ChangeState.PLANNING)
    assert can_transition(ChangeState.PLANNING, ChangeState.SEARCHING)
    assert can_transition(ChangeState.SEARCHING, ChangeState.CODING)
    assert can_transition(ChangeState.CODING, ChangeState.VALIDATING)
    assert can_transition(ChangeState.VALIDATING, ChangeState.READY_FOR_APPROVAL)
    assert can_transition(ChangeState.VALIDATING, ChangeState.DEBUGGING)
    assert can_transition(ChangeState.DEBUGGING, ChangeState.CODING)
    assert can_transition(ChangeState.READY_FOR_APPROVAL, ChangeState.APPROVED)
    assert can_transition(ChangeState.APPROVED, ChangeState.COMMITTING)
    assert can_transition(ChangeState.COMMITTING, ChangeState.COMMITTED)
    assert can_transition(ChangeState.READY_FOR_APPROVAL, ChangeState.REJECTED)


def test_invalid_transitions():
    # Terminal states cannot transition forward
    assert not can_transition(ChangeState.COMMITTED, ChangeState.CODING)
    assert not can_transition(ChangeState.ROLLED_BACK, ChangeState.PLANNING)
    assert not can_transition(ChangeState.CANCELLED, ChangeState.PLANNING)
    # Cannot go backward
    assert not can_transition(ChangeState.CODING, ChangeState.CREATED)
    assert not can_transition(ChangeState.VALIDATING, ChangeState.PLANNING)
    # Cannot skip states
    assert not can_transition(ChangeState.CREATED, ChangeState.CODING)
    # Cannot approve from CODING
    assert not can_transition(ChangeState.CODING, ChangeState.APPROVED)


def test_assert_transition_raises():
    with pytest.raises(InvalidStateTransition) as exc_info:
        assert_transition(ChangeState.COMMITTED, ChangeState.CODING)
    assert exc_info.value.from_state == ChangeState.COMMITTED
    assert exc_info.value.to_state == ChangeState.CODING


def test_assert_transition_passes():
    # Should not raise
    assert_transition(ChangeState.CREATED, ChangeState.PLANNING)
    assert_transition(ChangeState.VALIDATING, ChangeState.DEBUGGING)


def test_all_states_have_transitions_defined():
    """Every state should be in the TRANSITIONS dict."""
    for state in ChangeState:
        # Legacy states may not all be defined, that's OK
        if state in (ChangeState.FAILED_VALIDATION, ChangeState.FAILED_DEBUG):
            continue
        assert state in TRANSITIONS, f"State {state} missing from TRANSITIONS"


def test_failed_can_be_cancelled():
    assert can_transition(ChangeState.FAILED, ChangeState.CANCELLED)


def test_can_cancel_from_any_active_state():
    cancellable = [
        ChangeState.CREATED, ChangeState.PLANNING, ChangeState.SEARCHING,
        ChangeState.CODING, ChangeState.VALIDATING, ChangeState.DEBUGGING,
        ChangeState.READY_FOR_APPROVAL,
    ]
    for state in cancellable:
        assert can_transition(state, ChangeState.CANCELLED), f"Expected {state} to allow CANCELLED"
