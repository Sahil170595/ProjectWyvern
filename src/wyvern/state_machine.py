from __future__ import annotations

from enum import Enum


class MissionState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    STAGING = "staging"
    EXECUTING = "executing"
    PAUSED = "paused"
    RESUMING = "resuming"
    RTL = "rtl"
    ABORTED = "aborted"
    COMPLETED = "completed"
    FAILED = "failed"
    MANUAL_HANDOVER = "manual_handover"


_TRANSITIONS: dict[MissionState, list[MissionState]] = {
    MissionState.DRAFT: [MissionState.VALIDATED],
    MissionState.VALIDATED: [MissionState.AWAITING_APPROVAL, MissionState.REJECTED],
    MissionState.AWAITING_APPROVAL: [MissionState.APPROVED, MissionState.REJECTED],
    MissionState.APPROVED: [MissionState.STAGING, MissionState.EXPIRED],
    MissionState.STAGING: [MissionState.EXECUTING, MissionState.FAILED],
    MissionState.EXECUTING: [
        MissionState.PAUSED,
        MissionState.RTL,
        MissionState.ABORTED,
        MissionState.COMPLETED,
        MissionState.FAILED,
        MissionState.MANUAL_HANDOVER,
    ],
    MissionState.PAUSED: [
        MissionState.RESUMING,
        MissionState.RTL,
        MissionState.ABORTED,
        MissionState.MANUAL_HANDOVER,
    ],
    MissionState.RESUMING: [MissionState.EXECUTING],
    MissionState.RTL: [MissionState.COMPLETED, MissionState.FAILED],
    MissionState.MANUAL_HANDOVER: [MissionState.PAUSED],
    # Terminal states
    MissionState.ABORTED: [],
    MissionState.COMPLETED: [],
    MissionState.FAILED: [],
    MissionState.REJECTED: [],
    MissionState.EXPIRED: [],
}

TERMINAL_STATES = frozenset(
    s for s, targets in _TRANSITIONS.items() if not targets
)


def can_transition(from_state: MissionState, to_state: MissionState) -> bool:
    return to_state in _TRANSITIONS.get(from_state, [])


def is_terminal(state: MissionState) -> bool:
    return state in TERMINAL_STATES


def allowed_transitions(state: MissionState) -> list[MissionState]:
    return list(_TRANSITIONS.get(state, []))
