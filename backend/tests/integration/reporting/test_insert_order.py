"""Parent rows have to be inserted before the rows that reference them.

None of the row classes are linked by ``relationship()``, so SQLAlchemy's unit of work has
no foreign key dependency to sort a flush by and falls back to mapper sort order, which is
alphabetical. In this lane that order is exactly backwards: ``evidence`` sorts before
``report_items``, which sorts before ``reports``. Writing all three in one flush therefore
inserts the children first, and Postgres rejects it.

Every other test in this directory runs on sqlite with its default of foreign keys OFF, so
that failure is invisible to them -- the whole suite passed on a ``save_report`` that could
not write a report to the real database. These tests turn the constraint on so the ordering
is checked where it is cheap to check, rather than by a reviewer opening a report.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from interview_evidence.reporting.domain.deletion import (
    DeletionManifest,
    DeletionRequest,
    DeletionTarget,
)
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    AxisAssessment,
    Evidence,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
    Sufficiency,
)
from interview_evidence.reporting.repositories.postgres import (
    Base,
    SQLAlchemyReportingRepository,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000007"),
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="trace-insert-order",
    )


@pytest.fixture(name="engine")
def engine_fixture() -> Engine:
    """A sqlite engine that enforces foreign keys, which is not the default."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection: DBAPIConnection, _record: object) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def report_with_evidence() -> Report:
    """A report spanning all three tables, which is what makes the ordering observable."""
    report_id, version_id = uuid4(), uuid4()
    items = []
    for name in ("장애 대응 판단", "데이터 모델링"):
        item_id, criterion_id, evidence_id = uuid4(), uuid4(), uuid4()
        items.append(
            ReportItem(
                report_item_id=item_id,
                company_id=COMPANY_ID,
                report_id=report_id,
                criterion_id=criterion_id,
                criterion_name=name,
                competency_model_version_id=version_id,
                assessment_state=AssessmentState.CONFIRMED,
                observation="답변에서 선택 근거를 확인했습니다.",
                rationale="최종 답변 구간에서 확인했습니다.",
                sufficiency="direct",
                uncertainty="",
                evidence=(
                    Evidence(
                        evidence_id=evidence_id,
                        company_id=COMPANY_ID,
                        report_item_id=item_id,
                        criterion_id=criterion_id,
                        competency_model_version_id=version_id,
                        answer_turn_id=uuid4(),
                        transcript_segment_id=uuid4(),
                        video_start_ms=1_000,
                        video_end_ms=4_000,
                        observation="대안을 비교한 대목입니다.",
                        rationale="답변 구간에서 확인했습니다.",
                        sufficiency=Sufficiency.DIRECT,
                        generation_version="report-generation-v1",
                        created_at=NOW,
                    ),
                ),
                axis_assessments=(
                    AxisAssessment(
                        axis="correctness",
                        label="정확성",
                        score=78,
                        rationale="원인을 정확히 짚었습니다.",
                        quoted_evidence_ids=(evidence_id,),
                    ),
                ),
            )
        )
    return Report(
        report_id=report_id,
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        invitation_id=INVITATION_ID,
        version=1,
        kind=ReportKind.AI_ORIGINAL,
        model_version="model-v1",
        prompt_version="prompt-v1",
        config_version="config-v1",
        status=ReportStatus.READY,
        summary="면접 근거 요약",
        created_at=NOW,
        items=tuple(items),
    )


def test_a_report_writes_against_enforced_foreign_keys(engine: Engine) -> None:
    report = report_with_evidence()

    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        repository.save_report(context(), report)
        session.commit()
        session.expire_all()
        loaded = repository.get_report(context(), report.report_id)

    # Read back rather than only asserting the write did not raise: a flush reordered to
    # satisfy the constraints must still store every row.
    assert len(loaded.items) == 2
    assert all(len(item.evidence) == 1 for item in loaded.items)
    assert loaded.overall_score == 78


def test_a_deletion_manifest_writes_against_enforced_foreign_keys(engine: Engine) -> None:
    request = DeletionRequest(
        deletion_request_id=uuid4(),
        company_id=COMPANY_ID,
        scope_type="invitation",
        scope_id=INVITATION_ID,
        reason="지원자 삭제 요청",
        requester_type="company_user",
        requester_id=UUID("00000000-0000-7000-8000-000000000004"),
        policy_snapshot={"retention_days": 180},
        requested_at=NOW,
    )
    manifest = DeletionManifest(
        manifest_id=uuid4(),
        deletion_request_id=request.deletion_request_id,
        manifest_version=1,
        targets=(
            DeletionTarget.pending(
                target_id=uuid4(),
                owner_lane="C",
                store="s3",
                target_type="recording_chunk",
                resource_id="chunk-1",
            ),
        ),
    )

    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        repository.save_deletion(context(), request, manifest)
        session.commit()
        session.expire_all()
        loaded_request, loaded_manifest = repository.get_deletion(
            context(), request.deletion_request_id
        )

    assert loaded_request.deletion_request_id == request.deletion_request_id
    assert len(loaded_manifest.targets) == 1
