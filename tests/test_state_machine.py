from wyvern.state_machine import (
    MissionState,
    TERMINAL_STATES,
    allowed_transitions,
    can_transition,
    is_terminal,
)


def test_happy_path_transitions():
    path = [
        MissionState.DRAFT,
        MissionState.VALIDATED,
        MissionState.AWAITING_APPROVAL,
        MissionState.APPROVED,
        MissionState.STAGING,
        MissionState.EXECUTING,
        MissionState.COMPLETED,
    ]
    for i in range(len(path) - 1):
        assert can_transition(path[i], path[i + 1]), f"{path[i]} -> {path[i+1]}"


def test_pause_resume_cycle():
    assert can_transition(MissionState.EXECUTING, MissionState.PAUSED)
    assert can_transition(MissionState.PAUSED, MissionState.RESUMING)
    assert can_transition(MissionState.RESUMING, MissionState.EXECUTING)


def test_rtl_from_executing():
    assert can_transition(MissionState.EXECUTING, MissionState.RTL)
    assert can_transition(MissionState.RTL, MissionState.COMPLETED)
    assert can_transition(MissionState.RTL, MissionState.FAILED)


def test_rtl_from_paused():
    assert can_transition(MissionState.PAUSED, MissionState.RTL)


def test_abort_from_executing():
    assert can_transition(MissionState.EXECUTING, MissionState.ABORTED)


def test_abort_from_paused():
    assert can_transition(MissionState.PAUSED, MissionState.ABORTED)


def test_rejection():
    assert can_transition(MissionState.VALIDATED, MissionState.REJECTED)
    assert can_transition(MissionState.AWAITING_APPROVAL, MissionState.REJECTED)


def test_invalid_transitions():
    assert not can_transition(MissionState.DRAFT, MissionState.EXECUTING)
    assert not can_transition(MissionState.COMPLETED, MissionState.EXECUTING)
    assert not can_transition(MissionState.ABORTED, MissionState.DRAFT)
    assert not can_transition(MissionState.PAUSED, MissionState.COMPLETED)
    assert not can_transition(MissionState.STAGING, MissionState.PAUSED)


def test_terminal_states():
    for state in TERMINAL_STATES:
        assert is_terminal(state)
        assert allowed_transitions(state) == []

    assert MissionState.COMPLETED in TERMINAL_STATES
    assert MissionState.FAILED in TERMINAL_STATES
    assert MissionState.ABORTED in TERMINAL_STATES
    assert MissionState.REJECTED in TERMINAL_STATES
    assert MissionState.EXPIRED in TERMINAL_STATES


def test_non_terminal_states():
    assert not is_terminal(MissionState.DRAFT)
    assert not is_terminal(MissionState.EXECUTING)
    assert not is_terminal(MissionState.PAUSED)


def test_manual_handover_from_executing():
    assert can_transition(MissionState.EXECUTING, MissionState.MANUAL_HANDOVER)
    assert can_transition(MissionState.MANUAL_HANDOVER, MissionState.PAUSED)


def test_manual_handover_from_paused():
    assert can_transition(MissionState.PAUSED, MissionState.MANUAL_HANDOVER)


def test_allowed_transitions_from_executing():
    allowed = allowed_transitions(MissionState.EXECUTING)
    assert MissionState.PAUSED in allowed
    assert MissionState.RTL in allowed
    assert MissionState.ABORTED in allowed
    assert MissionState.COMPLETED in allowed
    assert MissionState.FAILED in allowed
    assert MissionState.MANUAL_HANDOVER in allowed
    assert len(allowed) == 6
