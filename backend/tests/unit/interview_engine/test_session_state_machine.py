from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.interview_engine.application.state_machine import (
    SessionStateMachine,
    StaleSessionSequence,
)
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
    InvalidSessionTransition,
)

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def session() -> InterviewSession:
    return InterviewSession(
        interview_session_id=UUID("00000000-0000-7000-8000-000000000001"),
        company_id=UUID("00000000-0000-7000-8000-000000000002"),
        invitation_id=UUID("00000000-0000-7000-8000-000000000003"),
        applicant_id=UUID("00000000-0000-7000-8000-000000000004"),
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000005"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000006"),
        created_at=NOW,
    )


def test_session_transition_increments_server_sequence() -> None:
    transitioned = SessionStateMachine().transition(
        session(),
        expected_sequence=0,
        target=InterviewSessionState.IN_PROGRESS,
    )
    assert transitioned.state is InterviewSessionState.IN_PROGRESS
    assert transitioned.session_sequence == 1


def test_session_rejects_invalid_or_stale_transitions() -> None:
    machine = SessionStateMachine()
    with pytest.raises(InvalidSessionTransition):
        machine.transition(
            session(),
            expected_sequence=0,
            target=InterviewSessionState.COMPLETED,
        )
    with pytest.raises(StaleSessionSequence):
        machine.transition(
            session(),
            expected_sequence=3,
            target=InterviewSessionState.IN_PROGRESS,
        )
