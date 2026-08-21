from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from interview_evidence.reporting.application.timeline_service import (
    TimelineService,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
TURN_ID = UUID("00000000-0000-7000-8000-000000000003")
NOW = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)


class TimelineRepository:
    def list_transcripts(
        self,
        _context: TenantContext,
        _session_id: UUID,
    ) -> tuple[SimpleNamespace, ...]:
        return (
            SimpleNamespace(
                transcript_segment_id=UUID("00000000-0000-7000-8000-000000000004"),
                turn_id=TURN_ID,
                speaker="interviewer",
                text="ECS 장애의 원인을 어떻게 좁혔나요?",
                session_start_ms=1000,
                session_end_ms=4000,
            ),
        )

    def list_session_events(
        self,
        _context: TenantContext,
        _session_id: UUID,
    ) -> tuple[()]:
        return ()


class RationaleProvider:
    def list_question_rationales(
        self,
        _context: TenantContext,
        *,
        session_id: UUID,
    ) -> tuple[SimpleNamespace, ...]:
        assert session_id == SESSION_ID
        return (
            SimpleNamespace(
                question_turn_id=TURN_ID,
                criterion_id=UUID("00000000-0000-7000-8000-000000000005"),
                interview_stage="project_deep_dive",
                verification_target_type="detail_missing",
                objective="자료에서 확인되지 않은 원인 분석과 복구 역할 확인",
                question_type="follow_up",
                retrieval_version="aurora-hybrid-v1",
                generation_version="question-v2",
                policy_result="accepted",
                source_references=(
                    SimpleNamespace(
                        source_id=UUID("00000000-0000-7000-8000-000000000006"),
                        source_type="submission_chunk",
                        locator={"page_number": 2},
                        excerpt="ECS 배포 경험은 있으나 장애 대응 설명은 없습니다.",
                    ),
                ),
            ),
        )


def test_question_rationale_is_projected_separately_from_evidence() -> None:
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000007"),
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="question-rationale-timeline",
    )

    entries = TimelineService(
        TimelineRepository(),
        rationale_provider=RationaleProvider(),
    ).project(context, session_id=SESSION_ID)

    assert len(entries) == 1
    rationale = entries[0].question_rationale
    assert rationale is not None
    assert rationale.interview_stage == "project_deep_dive"
    assert rationale.objective.startswith("자료에서 확인되지 않은")
    assert rationale.source_references[0].excerpt.startswith("ECS 배포")
    assert entries[0].entry_type == "question"
