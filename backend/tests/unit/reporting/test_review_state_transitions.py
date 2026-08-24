# Created: 2026-08-23 23:45
"""An interview that finished, and a decision that was made, have to reach the invitation.

Neither did. Finishing an interview left the invitation wherever the analysis pipeline had put it,
and recording a final decision wrote a `HumanReview` row and stopped. The console counts
"검토 대기" as `status == "completed"` and "검토 완료" as `reviewed`, so both counters stayed at
zero no matter how many interviews were run or decisions recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.reporting.application.review_service import close_invitation_review
from interview_evidence.runtime.worker import InterviewCompletedEventHandler
from interview_evidence.shared.ids import CommandMeta, FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox, OutboxEvent
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")


@dataclass(frozen=True)
class Snapshot:
    state: str
    row_version: int


class RecordingInvitations:
    """Stands in for the hiring lane, rejecting transitions the domain would reject."""

    def __init__(self, state: str, row_version: int = 1) -> None:
        self.state = state
        self.row_version = row_version
        self.transitions: list[tuple[str, str, str]] = []

    def authorize_invitation(
        self,
        _context: TenantContext,
        _invitation_id: UUID,
        *,
        required_state: str | frozenset[str],
    ) -> Snapshot:
        del required_state
        return Snapshot(state=self.state, row_version=self.row_version)

    def advance_invitation_state(
        self,
        _context: TenantContext,
        _invitation_id: UUID,
        *,
        from_state: str,
        to_state: str,
        meta: CommandMeta,
    ) -> Snapshot:
        if self.state != from_state:
            raise ValueError("invitation state does not match the requested transition")
        if meta.expected_version != self.row_version:
            raise ValueError("stale invitation version")
        self.transitions.append((from_state, to_state, meta.idempotency_key))
        self.state = to_state
        self.row_version += 1
        return Snapshot(state=self.state, row_version=self.row_version)


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=SESSION_ID,
        request_id=SESSION_ID,
        trace_id="review-transition",
    )


def _completed_event() -> OutboxEvent:
    return OutboxEvent(
        outbox_event_id=UUID("00000000-0000-7000-8000-000000000004"),
        company_id=COMPANY_ID,
        aggregate_type="interview_session",
        aggregate_id=SESSION_ID,
        aggregate_version=7,
        event_type="interview.completed",
        event_version=1,
        payload={
            "interview_session_id": str(SESSION_ID),
            "invitation_id": str(INVITATION_ID),
            "last_turn_id": str(UUID("00000000-0000-7000-8000-000000000005")),
            "completed_at": NOW.isoformat(),
            "media_status": "pending",
        },
        idempotency_key=f"interview-completed-{SESSION_ID}",
        trace_id="review-transition",
        occurred_at=NOW,
    )


def _handle(invitations: RecordingInvitations | None) -> InMemoryOutbox:
    outbox = InMemoryOutbox()
    InterviewCompletedEventHandler(outbox, FrozenClock(NOW), invitations)(
        _context(),
        _completed_event(),
    )
    return outbox


class TestInterviewCompletion:
    def test_a_finished_interview_puts_its_invitation_up_for_review(self) -> None:
        invitations = RecordingInvitations("ready")

        _handle(invitations)

        # `interviewing` is passed through because the domain allows only
        # `ready -> interviewing -> completed`; a live interview never announced itself.
        assert invitations.transitions == [
            ("ready", "interviewing", f"interview-started-{INVITATION_ID}"),
            ("interviewing", "completed", f"interview-completed-{INVITATION_ID}"),
        ]
        assert invitations.state == "completed"

    def test_an_interview_already_underway_only_needs_closing(self) -> None:
        invitations = RecordingInvitations("interviewing")

        _handle(invitations)

        assert invitations.transitions == [
            ("interviewing", "completed", f"interview-completed-{INVITATION_ID}")
        ]

    def test_a_reconnected_interview_closes_from_interrupted(self) -> None:
        invitations = RecordingInvitations("interrupted")

        _handle(invitations)

        assert invitations.transitions == [
            ("interrupted", "completed", f"interview-completed-{INVITATION_ID}")
        ]

    @pytest.mark.parametrize("state", ["completed", "reviewed"])
    def test_redelivery_changes_nothing(self, state: str) -> None:
        """The queue delivers at least once, so the handler runs more than once per interview."""
        invitations = RecordingInvitations(state)

        _handle(invitations)

        assert invitations.transitions == []
        assert invitations.state == state

    def test_an_unexpected_state_is_left_alone_rather_than_requeued(self) -> None:
        """Raising here would requeue the event forever and block the media request below it."""
        invitations = RecordingInvitations("materials_submitted")

        outbox = _handle(invitations)

        assert invitations.transitions == []
        assert [event.event_type for event in outbox.pending()] == ["media.postprocess_requested"]

    def test_media_post_processing_is_still_requested(self) -> None:
        outbox = _handle(RecordingInvitations("ready"))

        pending = outbox.pending()
        assert [event.event_type for event in pending] == ["media.postprocess_requested"]
        assert pending[0].payload["interview_session_id"] == str(SESSION_ID)

    def test_the_handler_works_without_the_hiring_lane(self) -> None:
        """The in-memory worker runtime wires no company port; it must still post-process."""
        outbox = _handle(None)

        assert [event.event_type for event in outbox.pending()] == ["media.postprocess_requested"]


class TestFinalDecision:
    def test_recording_a_decision_marks_the_invitation_reviewed(self) -> None:
        invitations = RecordingInvitations("completed")

        state = close_invitation_review(
            invitations,
            _context(),
            invitation_id=INVITATION_ID,
            occurred_at=NOW,
        )

        assert state == "reviewed"
        assert invitations.transitions == [
            ("completed", "reviewed", f"invitation-reviewed-{INVITATION_ID}")
        ]

    def test_a_second_decision_does_not_transition_again(self) -> None:
        """Reviewers change their minds; the decision is re-recorded, the state is already there."""
        invitations = RecordingInvitations("reviewed")

        state = close_invitation_review(
            invitations,
            _context(),
            invitation_id=INVITATION_ID,
            occurred_at=NOW,
        )

        assert state == "reviewed"
        assert invitations.transitions == []

    def test_an_interview_that_never_finished_is_not_forced_to_reviewed(self) -> None:
        invitations = RecordingInvitations("interviewing")

        state = close_invitation_review(
            invitations,
            _context(),
            invitation_id=INVITATION_ID,
            occurred_at=NOW,
        )

        assert state == "interviewing"
        assert invitations.transitions == []
