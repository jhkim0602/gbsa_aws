from datetime import UTC, datetime
from uuid import UUID, uuid4

from interview_evidence.reporting.domain.report import (
    AssessmentState,
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
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")

# One statement each for the report, its items, and every item's evidence.
EXPECTED_SELECTS = 3


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000007"),
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="trace-report-query-count",
    )


def report_with(item_count: int, evidence_per_item: int) -> Report:
    report_id = uuid4()
    items = []
    for _ in range(item_count):
        item_id, criterion_id, version_id = uuid4(), uuid4(), uuid4()
        items.append(
            ReportItem(
                report_item_id=item_id,
                company_id=COMPANY_ID,
                report_id=report_id,
                criterion_id=criterion_id,
                competency_model_version_id=version_id,
                assessment_state=AssessmentState.CONFIRMED,
                observation="후보자가 큐 도입 근거를 설명했습니다.",
                rationale="답변에서 지연 시간 비교를 제시했습니다.",
                sufficiency="direct",
                uncertainty="",
                evidence=tuple(
                    Evidence(
                        evidence_id=uuid4(),
                        company_id=COMPANY_ID,
                        report_item_id=item_id,
                        criterion_id=criterion_id,
                        competency_model_version_id=version_id,
                        answer_turn_id=uuid4(),
                        transcript_segment_id=uuid4(),
                        video_start_ms=0,
                        video_end_ms=1000,
                        observation="큐 선택 이유를 언급했습니다.",
                        rationale="답변 구간에서 확인했습니다.",
                        sufficiency=Sufficiency.DIRECT,
                        generation_version="report-generation-v1",
                        created_at=NOW,
                    )
                    for _ in range(evidence_per_item)
                ),
                follow_up_question=None,
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


def read_back(report: Report) -> tuple[Report, int]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        repository.save_report(context(), report)
        session.commit()
        session.expire_all()

        selects: list[str] = []

        def record(conn, cursor, statement, parameters, ctx, executemany) -> None:  # noqa: ANN001
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            loaded = repository.get_report(context(), report.report_id)
        finally:
            event.remove(engine, "before_cursor_execute", record)
    return loaded, len(selects)


def test_report_read_does_not_scale_queries_with_item_count() -> None:
    _, few = read_back(report_with(item_count=2, evidence_per_item=2))
    _, many = read_back(report_with(item_count=25, evidence_per_item=3))

    assert few == EXPECTED_SELECTS
    assert many == EXPECTED_SELECTS


def test_batched_evidence_read_preserves_item_order_and_grouping() -> None:
    report = report_with(item_count=25, evidence_per_item=3)

    loaded, _ = read_back(report)

    assert [item.report_item_id for item in loaded.items] == [
        item.report_item_id for item in report.items
    ]
    for item in loaded.items:
        assert len(item.evidence) == 3
        assert {evidence.report_item_id for evidence in item.evidence} == {item.report_item_id}
