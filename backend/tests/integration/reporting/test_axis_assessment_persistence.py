"""The scores a reviewer reads have to be the scores the model produced.

A report is an immutable AI original: it is written once and read many times, by more than
one reviewer. So the round trip is what matters here -- if a score, its rationale or its
citations change shape between the write and the read, two reviewers can open the same
report and disagree about what the AI said, which is exactly the ambiguity the immutability
rule exists to prevent.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000007"),
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="trace-axis-persistence",
    )


def report_with(axes: tuple[AxisAssessment, ...], *, evidence_id: UUID) -> Report:
    report_id, item_id, criterion_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
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
        items=(
            ReportItem(
                report_item_id=item_id,
                company_id=COMPANY_ID,
                report_id=report_id,
                criterion_id=criterion_id,
                criterion_name="장애 대응 판단",
                competency_model_version_id=version_id,
                assessment_state=AssessmentState.CONFIRMED,
                observation="큐 도입 근거를 설명했습니다.",
                rationale="답변에서 지연 비교를 제시했습니다.",
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
                        video_start_ms=1000,
                        video_end_ms=4000,
                        observation="큐 선택 이유를 언급했습니다.",
                        rationale="답변 구간에서 확인했습니다.",
                        sufficiency=Sufficiency.DIRECT,
                        generation_version="report-generation-v1",
                        created_at=NOW,
                    ),
                ),
                axis_assessments=axes,
            ),
        ),
    )


def read_back(report: Report) -> Report:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        repository.save_report(context(), report)
        session.commit()
        session.expire_all()
        return repository.get_report(context(), report.report_id)


def test_scores_rationales_and_citations_survive_the_round_trip() -> None:
    evidence_id = uuid4()
    axes = (
        AxisAssessment(
            axis="correctness",
            label="정확성",
            score=78,
            rationale="재시도 폭주를 원인으로 정확히 짚었습니다.",
            quoted_evidence_ids=(evidence_id,),
        ),
        AxisAssessment(
            axis="fundamentals",
            label="CS 기본기",
            score=None,
            rationale="확인할 답변이 없었습니다.",
        ),
    )

    loaded = read_back(report_with(axes, evidence_id=evidence_id))

    assert loaded.items[0].axis_assessments == axes
    # None must come back as None rather than as a zero: a zero would tell the reviewer the
    # candidate got this wrong, when the interview never asked.
    assert loaded.items[0].axis_assessments[1].score is None
    assert loaded.items[0].average_score == 78
    assert loaded.overall_score == 78


def test_a_report_written_before_scoring_existed_still_reads() -> None:
    evidence_id = uuid4()
    report = report_with((), evidence_id=evidence_id)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        repository.save_report(context(), report)
        session.commit()
        # Stand in for a pre-migration row, which the server default filled with an empty
        # array. The console reads that as "this report has no scores".
        session.execute(text("UPDATE report_items SET axis_assessments = '[]'"))
        session.commit()
        session.expire_all()
        loaded = repository.get_report(context(), report.report_id)

    assert loaded.items[0].axis_assessments == ()
    assert loaded.items[0].average_score is None
    assert loaded.overall_score is None


def test_an_axis_row_this_build_cannot_read_is_skipped_not_raised_on() -> None:
    evidence_id = uuid4()
    report = report_with(
        (
            AxisAssessment(
                axis="correctness",
                label="정확성",
                score=78,
                rationale="정확했습니다.",
                quoted_evidence_ids=(evidence_id,),
            ),
        ),
        evidence_id=evidence_id,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        repository.save_report(context(), report)
        session.commit()
        # A row whose rationale went missing -- an axis retired since it was written, or a
        # truncated write. The report itself is what the reviewer cannot reconstruct, so it
        # has to survive one unreadable score.
        session.execute(
            text("""UPDATE report_items SET axis_assessments =
                '[{"axis": "correctness", "label": "정확성", "score": 78}]'""")
        )
        session.commit()
        session.expire_all()
        loaded = repository.get_report(context(), report.report_id)

    assert loaded.items[0].axis_assessments == ()
    assert loaded.items[0].observation == "큐 도입 근거를 설명했습니다."
