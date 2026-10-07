"""T086: read-time transcript availability, ownership and immutable scoring."""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from interview_evidence.reporting.api.company_routes import _report_view, create_lane_d_app
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
    EvidenceRow,
    ReportItemRow,
    ReportRow,
    SQLAlchemyReportingRepository,
    TranscriptSegmentRow,
)
from interview_evidence.shared.security.principals import CompanyPrincipal, FakePrincipalProvider
from interview_evidence.shared.tenant import ActorType, TenantContext, TenantScopeError
from sqlalchemy import create_engine, delete, event, select, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 10, 8, tzinfo=UTC)
COMPANY = UUID(int=1)
OTHER_COMPANY = UUID(int=2)
SESSION = UUID(int=3)
REPORT = UUID(int=4)
USER = UUID(int=5)


def context(company=COMPANY):
    return TenantContext(
        company_id=company,
        actor_type=ActorType.COMPANY_USER,
        actor_id=USER,
        request_id=UUID(int=6),
        trace_id="synthetic-availability",
    )


def report():
    items = []
    for number, score in [(1, 80), (2, 60)]:
        evidence = Evidence(
            evidence_id=UUID(int=100 + number),
            company_id=COMPANY,
            report_item_id=UUID(int=200 + number),
            criterion_id=UUID(int=300 + number),
            competency_model_version_id=UUID(int=400),
            answer_turn_id=UUID(int=500 + number),
            transcript_segment_id=UUID(int=600 + number),
            video_start_ms=1000 * number,
            video_end_ms=1000 * number + 500,
            observation="synthetic observation",
            rationale="synthetic rationale",
            sufficiency=Sufficiency.DIRECT,
            generation_version="test-v1",
            created_at=NOW,
        )
        items.append(
            ReportItem(
                report_item_id=evidence.report_item_id,
                company_id=COMPANY,
                report_id=REPORT,
                criterion_id=evidence.criterion_id,
                competency_model_version_id=UUID(int=400),
                assessment_state=AssessmentState.CONFIRMED,
                observation="synthetic",
                rationale="synthetic",
                sufficiency="direct",
                uncertainty="human review required",
                evidence=(evidence,),
                criterion_weight=50.0,
                axis_weights={"depth": 100.0},
                axis_assessments=(
                    AxisAssessment(
                        axis="depth",
                        label="depth",
                        score=score,
                        rationale="synthetic",
                        quoted_evidence_ids=(evidence.evidence_id,),
                    ),
                ),
            )
        )
    return Report(
        report_id=REPORT,
        company_id=COMPANY,
        interview_session_id=SESSION,
        invitation_id=UUID(int=7),
        version=1,
        kind=ReportKind.AI_ORIGINAL,
        model_version="m",
        prompt_version="p",
        config_version="c",
        status=ReportStatus.READY,
        summary="synthetic report",
        created_at=NOW,
        items=tuple(items),
    )


def segment_values(evidence, **changes):
    values = dict(
        company_id=COMPANY,
        transcript_segment_id=evidence.transcript_segment_id,
        interview_session_id=SESSION,
        turn_id=evidence.answer_turn_id,
        speaker="applicant",
        text="synthetic answer",
        confidence=1.0,
        session_start_ms=evidence.video_start_ms,
        session_end_ms=evidence.video_end_ms,
        source_audio_key="synthetic/local",
        version=1,
        corrected_by=None,
        created_at=NOW,
    )
    return values | changes


@pytest.fixture
def store():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        original = report()
        repository.save_report(context(), original)
        for item in original.items:
            session.add(TranscriptSegmentRow(**segment_values(item.evidence[0])))
        session.commit()
        yield engine, session, repository, original
    engine.dispose()


def projection(session):
    return {
        model.__tablename__: [
            dict(row) for row in session.execute(select(model.__table__)).mappings()
        ]
        for model in (ReportRow, ReportItemRow, EvidenceRow)
    }


def test_removal_marks_only_affected_evidence_and_restore_matches_original_without_stored_mutation(
    store,
):
    _, session, repository, original = store
    before_rows = projection(session)
    loaded = repository.get_report(context(), REPORT)
    before_map = repository.transcript_availability_for_report(context(), loaded)
    assert before_map == {item.evidence[0].evidence_id: True for item in original.items}
    before_view = _report_view(loaded, (), transcript_availability=before_map)
    removed = original.items[0].evidence[0]
    session.execute(
        delete(TranscriptSegmentRow).where(
            TranscriptSegmentRow.transcript_segment_id == removed.transcript_segment_id
        )
    )
    session.commit()
    after_map = repository.transcript_availability_for_report(context(), loaded)
    assert after_map == {
        removed.evidence_id: False,
        original.items[1].evidence[0].evidence_id: True,
    }
    after_view = _report_view(loaded, (), transcript_availability=after_map)
    assert after_view["items"][0]["evidence"][0]["transcript_available"] is False
    assert after_view["items"][1] == before_view["items"][1]
    expected = before_view["items"][0]["evidence"][0] | {"transcript_available": False}
    assert after_view["items"][0]["evidence"][0] == expected
    for key in ("overall_score", "scoring_breakdown", "communication_score"):
        assert after_view[key] == before_view[key]
    assert after_view["items"][0]["axis_assessments"] == before_view["items"][0]["axis_assessments"]
    assert after_view["items"][0]["average_score"] == before_view["items"][0]["average_score"]
    assert projection(session) == before_rows
    session.add(TranscriptSegmentRow(**segment_values(removed)))
    session.commit()
    restored = repository.transcript_availability_for_report(context(), loaded)
    assert _report_view(loaded, (), transcript_availability=restored) == before_view
    assert projection(session) == before_rows


@pytest.mark.parametrize(
    "field,value",
    [
        ("company_id", OTHER_COMPANY),
        ("interview_session_id", UUID(int=999)),
        ("turn_id", UUID(int=998)),
    ],
)
def test_other_tenant_session_or_answer_cannot_make_evidence_available(store, field, value):
    _, session, repository, original = store
    evidence = original.items[0].evidence[0]
    session.execute(
        update(TranscriptSegmentRow)
        .where(TranscriptSegmentRow.transcript_segment_id == evidence.transcript_segment_id)
        .values({field: value})
    )
    session.commit()
    result = repository.transcript_availability_for_report(context(), original)
    assert result[evidence.evidence_id] is False
    assert result[original.items[1].evidence[0].evidence_id] is True


def test_foreign_report_is_rejected_before_query(store):
    engine, _, repository, original = store

    def fail_query(*args):
        raise AssertionError("tenant rejection must happen before SQL")

    event.listen(engine, "before_cursor_execute", fail_query)
    try:
        with pytest.raises(TenantScopeError):
            repository.transcript_availability_for_report(context(OTHER_COMPANY), original)
    finally:
        event.remove(engine, "before_cursor_execute", fail_query)


def test_availability_uses_one_query_for_many_items_and_no_query_without_evidence(store):
    engine, _, repository, original = store
    queries = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert all(repository.transcript_availability_for_report(context(), original).values())
        assert len(queries) == 1
        assert "text" not in queries[0].split("FROM")[0].lower()
        queries.clear()
        assert (
            repository.transcript_availability_for_report(context(), replace(original, items=()))
            == {}
        )
        assert queries == []
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_query_failure_is_not_reported_as_missing_or_available(store):
    engine, _, repository, original = store

    def unavailable(*args):
        raise RuntimeError("synthetic DB unavailable")

    event.listen(engine, "before_cursor_execute", unavailable)
    try:
        with pytest.raises(RuntimeError, match="synthetic DB unavailable"):
            repository.transcript_availability_for_report(context(), original)
    finally:
        event.remove(engine, "before_cursor_execute", unavailable)


def test_view_without_checked_availability_does_not_invent_it():
    view = _report_view(report(), ())
    assert all(
        "transcript_available" not in evidence
        for item in view["items"]
        for evidence in item["evidence"]
    )


class Audit:
    def __init__(self):
        self.actions = []

    def append(self, _context, **details):
        self.actions.append(details["action"])
        return UUID(int=9)


def test_company_report_http_path_supplies_current_availability(store):
    _, session, repository, original = store
    principal = CompanyPrincipal(
        company_id=COMPANY, company_user_id=USER, identity_subject="synthetic-company-user"
    )
    audit = Audit()
    app = create_lane_d_app(
        principal_provider=FakePrincipalProvider(company_principals={"synthetic-token": principal}),
        repository=repository,
        audit=audit,
        clock=SimpleNamespace(now=lambda: NOW),
    )
    removed = original.items[0].evidence[0]
    with TestClient(app) as client:
        route = f"/v1/interview-sessions/{SESSION}/report"
        headers = {"Authorization": "Bearer synthetic-token"}
        before = client.get(route, headers=headers)
        assert before.status_code == 200
        assert before.json()["items"][0]["evidence"][0]["transcript_available"] is True
        session.execute(
            delete(TranscriptSegmentRow).where(
                TranscriptSegmentRow.transcript_segment_id == removed.transcript_segment_id
            )
        )
        session.commit()
        after = client.get(route, headers=headers)
        assert after.status_code == 200
        assert after.json()["items"][0]["evidence"][0]["transcript_available"] is False
        assert after.json()["items"][1] == before.json()["items"][1]
        session.add(TranscriptSegmentRow(**segment_values(removed)))
        session.commit()
        assert client.get(route, headers=headers).json() == before.json()
    assert audit.actions == ["report.view"] * 3
