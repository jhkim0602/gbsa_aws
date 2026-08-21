from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

from interview_evidence.runtime.worker import ReportRequestedEventHandler
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 21, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")
QUESTION_TURN_ID = UUID("00000000-0000-7000-8000-000000000006")
ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000007")


def test_report_request_uses_transcript_range_for_evidence() -> None:
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000008"),
        request_id=UUID("00000000-0000-7000-8000-000000000009"),
        trace_id="trace-report-request",
    )
    transcript = SimpleNamespace(
        turn_id=ANSWER_TURN_ID,
        session_start_ms=1_250,
        session_end_ms=4_750,
    )
    repository = Mock()
    repository.get_report_for_session.return_value = None
    repository.list_transcripts.return_value = (transcript,)
    repository.list_recording_assets.return_value = (
        SimpleNamespace(asset_type="final_video"),
    )
    repository.list_session_events.return_value = ()

    company = Mock()
    company.get_criterion_version.return_value = SimpleNamespace(
        criteria=(
            SimpleNamespace(
                criterion_id=CRITERION_ID,
                name="운영 문제 해결",
                description="운영 문제를 분석하고 복구할 수 있다.",
                weight=1.0,
            ),
        ),
        interview_level="entry",
        axis_weights={},
    )
    company.get_recruiting_assistant_subject.return_value = SimpleNamespace()

    interview = Mock()
    interview.get_session_snapshot.return_value = SimpleNamespace(
        competency_model_version_id=VERSION_ID,
        invitation_id=INVITATION_ID,
    )
    interview.list_final_turns.return_value = (
        SimpleNamespace(
            turn_id=QUESTION_TURN_ID,
            speaker=SimpleNamespace(value="interviewer"),
            text="운영 문제를 해결한 경험을 설명해 주세요.",
        ),
        SimpleNamespace(
            turn_id=ANSWER_TURN_ID,
            speaker=SimpleNamespace(value="applicant"),
            text="로그와 지표를 비교해 원인을 좁히고 복구했습니다.",
        ),
    )

    generated_report = object()
    generator = Mock()
    generator.generate.return_value = generated_report
    handler = ReportRequestedEventHandler(
        company=company,
        interview=interview,
        reporting=SimpleNamespace(repository=repository),
        generator=generator,
        clock=FrozenClock(NOW),
    )

    result = handler(
        context,
        OutboxEvent(
            outbox_event_id=UUID("00000000-0000-7000-8000-000000000010"),
            company_id=COMPANY_ID,
            aggregate_type="interview_session",
            aggregate_id=SESSION_ID,
            aggregate_version=1,
            event_type="report.generation_requested",
            event_version=1,
            payload={"interview_session_id": str(SESSION_ID)},
            idempotency_key="report-generation-request",
            trace_id=context.trace_id,
            occurred_at=NOW,
        ),
    )

    assert result is generated_report
    criterion_input = generator.generate.call_args.kwargs["criteria"][0]
    assert criterion_input.video_start_ms == transcript.session_start_ms
    assert criterion_input.video_end_ms == transcript.session_end_ms
