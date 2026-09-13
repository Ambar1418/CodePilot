"""Explicit state machine with legal transition enforcement."""
from __future__ import annotations
from typing import Set, Dict
from backend.models.schemas import ChangeState

# Legal transitions: from_state -> set of allowed to_states
TRANSITIONS: Dict[ChangeState, Set[ChangeState]] = {
    ChangeState.CREATED: {ChangeState.PLANNING, ChangeState.FAILED, ChangeState.CANCELLED},
    ChangeState.PLANNING: {ChangeState.SEARCHING, ChangeState.FAILED, ChangeState.CANCELLED},
    ChangeState.SEARCHING: {ChangeState.CODING, ChangeState.FAILED, ChangeState.CANCELLED},
    ChangeState.CODING: {ChangeState.VALIDATING, ChangeState.FAILED, ChangeState.CANCELLED},
    ChangeState.VALIDATING: {
        ChangeState.DEBUGGING,
        ChangeState.READY_FOR_APPROVAL,
        ChangeState.FAILED,
        ChangeState.CANCELLED,
    },
    ChangeState.DEBUGGING: {ChangeState.CODING, ChangeState.FAILED, ChangeState.CANCELLED},
    ChangeState.READY_FOR_APPROVAL: {
        ChangeState.APPROVED,
        ChangeState.REJECTED,
        ChangeState.CANCELLED,
    },
    ChangeState.APPROVED: {ChangeState.COMMITTING},
    ChangeState.COMMITTING: {ChangeState.COMMITTED, ChangeState.FAILED},
    ChangeState.COMMITTED: set(),   # terminal
    ChangeState.REJECTED: {ChangeState.ROLLED_BACK},
    ChangeState.ROLLED_BACK: set(), # terminal
    ChangeState.FAILED: {ChangeState.CANCELLED},  # can only be cancelled after failure
    ChangeState.CANCELLED: set(),   # terminal

    # Legacy compat states (map to FAILED/READY_FOR_APPROVAL for transitions)
    ChangeState.FAILED_VALIDATION: {ChangeState.FAILED, ChangeState.CANCELLED},
    ChangeState.FAILED_DEBUG: {ChangeState.FAILED, ChangeState.CANCELLED},
}


class InvalidStateTransition(Exception):
    """Raised when an illegal state transition is attempted."""
    def __init__(self, from_state: ChangeState, to_state: ChangeState):
        super().__init__(f"Invalid transition: {from_state} → {to_state}")
        self.from_state = from_state
        self.to_state = to_state


def can_transition(from_state: ChangeState, to_state: ChangeState) -> bool:
    """Returns True if the transition is legal."""
    allowed = TRANSITIONS.get(from_state, set())
    return to_state in allowed


def assert_transition(from_state: ChangeState, to_state: ChangeState) -> None:
    """Raises InvalidStateTransition if the move is not allowed."""
    if not can_transition(from_state, to_state):
        raise InvalidStateTransition(from_state, to_state)
