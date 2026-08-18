"""The seeded local demo must produce one applicant whose review screen opens with data.

Driven through ``seed_local_company`` rather than the three lane helpers directly: the
helpers each have their own coverage, and what is untested without this is the sequencing
-- an interview seeded against an invitation id the caller re-derived, or report
projections pointed at a session that was never written, both leave the console with a
검토 시작 button that resolves to an empty screen.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from interview_evidence.company_management.api import ensure_local_demo_recruiting
from interview_evidence.company_management.repositories.postgres import Base as CompanyBase
from interview_evidence.company_management.repositories.postgres import (
    CompanyRow,
    CompanyUserRow,
)
from interview_evidence.interview_engine.repositories.postgres import (
    Base as InterviewBase,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InterviewSessionRow,
    InterviewTurnRow,
    QuestionRationaleRow,
    QuestionSourceReferenceRow,
    RecordingChunkRow,
)
from interview_evidence.reporting.repositories.postgres import Base as ReportingBase
from interview_evidence.reporting.repositories.postgres import (
    EvidenceRow,
    RecordingAssetRow,
    ReportItemRow,
    ReportRow,
    TranscriptSegmentRow,
)
from interview_evidence.runtime.local_seed import seed_local_company
from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def test_local_demo_seed_leaves_one_reviewable_applicant(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'seed.db'}"
    engine = create_engine(database_url)
    for metadata in (CompanyBase.metadata, InterviewBase.metadata, ReportingBase.metadata):
        metadata.create_all(engine)
    environment = {
        "DATABASE_URL": database_url,
        "LOCAL_COMPANY_ID": str(COMPANY_ID),
        "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
        "LOCAL_DEMO_DATA_ENABLED": "true",
    }

    # With a bucket, because the assertions below expect a ready asset -- and an asset is
    # only ready once the recording it names has actually been uploaded.
    media = InMemoryObjectStorage()
    # Twice, because the local stack re-runs the seed on every boot.
    seed_local_company(environment, media_storage=media)
    seed_local_company(environment, media_storage=media)

    with Session(engine) as session:
        demo = ensure_local_demo_recruiting(
            session,
            company_id=COMPANY_ID,
            company_user_id=COMPANY_USER_ID,
            now=NOW,
        )
        sessions = session.scalars(
            select(InterviewSessionRow).where(
                InterviewSessionRow.invitation_id == demo.reviewed_invitation_id
            )
        ).all()
        assert len(sessions) == 1
        # Only a reviewable session makes the console derive a review path for the row.
        assert sessions[0].state == "reviewable"
        assert sessions[0].applicant_id == demo.reviewed_applicant_id
        session_id = sessions[0].interview_session_id

        assert _count(session, InterviewTurnRow, session_id) == 6
        chunks = session.scalars(
            select(RecordingChunkRow).where(RecordingChunkRow.interview_session_id == session_id)
        ).all()
        assert [chunk.upload_status for chunk in chunks] == ["verified"]
        assert _count(session, TranscriptSegmentRow, session_id) == 6
        assets = session.scalars(
            select(RecordingAssetRow).where(RecordingAssetRow.interview_session_id == session_id)
        ).all()
        # Playback only offers a URL for a ready or partial asset.
        assert [asset.status for asset in assets] == ["ready"]
        assert assets[0].duration_ms >= chunks[0].session_end_ms
        # And a ready asset has to name bytes. Both keys, because the reviewer plays the
        # assembled recording while each citation traces back to the chunk it came from.
        assert {assets[0].object_key, chunks[0].object_key} <= set(media.objects)

        reports = session.scalars(
            select(ReportRow).where(ReportRow.interview_session_id == session_id)
        ).all()
        assert len(reports) == 1
        assert reports[0].status == "ready"
        assert reports[0].invitation_id == demo.reviewed_invitation_id

        items = session.scalars(
            select(ReportItemRow).where(ReportItemRow.report_id == reports[0].report_id)
        ).all()
        assert len(items) == 1
        assert items[0].criterion_id == demo.criterion_id
        assert items[0].criterion_name == demo.criterion_name

        evidence = session.scalars(
            select(EvidenceRow).where(EvidenceRow.report_item_id == items[0].report_item_id)
        ).all()
        assert len(evidence) == 3
        segment_ids = {
            row.transcript_segment_id
            for row in session.scalars(
                select(TranscriptSegmentRow).where(
                    TranscriptSegmentRow.interview_session_id == session_id
                )
            )
        }
        evidence_ids = {row.evidence_id for row in evidence}
        for item in evidence:
            # A citation the reviewer cannot play back teaches them to trust the score
            # instead of the answer, which is the one thing the report must not do.
            assert item.transcript_segment_id in segment_ids
            assert item.video_end_ms <= assets[0].duration_ms

        scored = [axis for axis in items[0].axis_assessments if axis["score"] is not None]
        assert scored, "the review screen shows scores, so the seed has to carry them"
        for axis in scored:
            cited = {UUID(str(value)) for value in axis["quoted_evidence_ids"]}
            assert cited and cited <= evidence_ids

        unscored = [axis for axis in items[0].axis_assessments if axis["score"] is None]
        assert unscored, "one axis stays unjudged so the seed shows that state too"
        assert all(not axis["quoted_evidence_ids"] for axis in unscored)


def test_local_demo_seed_explains_every_question_it_asked(tmp_path: Path) -> None:
    """The review screen shows what in the submission prompted each question.

    Without these rows the timeline renders the question alone, which reads as if the AI
    invented it -- and the report's 질문 근거 자료 section is empty on every local machine
    even though the console is built to show it.
    """
    database_url = f"sqlite+pysqlite:///{tmp_path / 'seed.db'}"
    engine = create_engine(database_url)
    for metadata in (CompanyBase.metadata, InterviewBase.metadata, ReportingBase.metadata):
        metadata.create_all(engine)
    environment = {
        "DATABASE_URL": database_url,
        "LOCAL_COMPANY_ID": str(COMPANY_ID),
        "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
        "LOCAL_DEMO_DATA_ENABLED": "true",
    }

    seed_local_company(environment)
    seed_local_company(environment)

    with Session(engine) as session:
        demo = ensure_local_demo_recruiting(
            session,
            company_id=COMPANY_ID,
            company_user_id=COMPANY_USER_ID,
            now=NOW,
        )
        session_id = session.scalar(
            select(InterviewSessionRow.interview_session_id).where(
                InterviewSessionRow.invitation_id == demo.reviewed_invitation_id
            )
        )
        rationales = session.scalars(
            select(QuestionRationaleRow).where(
                QuestionRationaleRow.interview_session_id == session_id
            )
        ).all()
        question_turn_ids = set(
            session.scalars(
                select(InterviewTurnRow.turn_id).where(
                    InterviewTurnRow.interview_session_id == session_id,
                    InterviewTurnRow.speaker == "interviewer",
                )
            )
        )
        # Every question, not just the first: a follow-up with no rationale is the one the
        # applicant is most likely to ask about.
        assert len(rationales) == len(question_turn_ids) == 3
        assert {row.question_turn_id for row in rationales} == question_turn_ids
        assert {row.question_type for row in rationales} == {"personalized", "follow_up"}
        assert all(row.criterion_id == demo.criterion_id for row in rationales)
        assert all(row.policy_result == "accepted" for row in rationales)

        # The timeline joins a rationale to its question through the transcript's turn id,
        # so a segment written against a different id shows the question with no rationale.
        question_segment_turn_ids = set(
            session.scalars(
                select(TranscriptSegmentRow.turn_id).where(
                    TranscriptSegmentRow.interview_session_id == session_id,
                    TranscriptSegmentRow.speaker == "interviewer",
                )
            )
        )
        assert question_segment_turn_ids == question_turn_ids

        references = session.scalars(
            select(QuestionSourceReferenceRow).where(
                QuestionSourceReferenceRow.interview_session_id == session_id
            )
        ).all()
        assert references
        by_id = {row.source_reference_id: row for row in references}
        for rationale in rationales:
            cited = [UUID(str(value)) for value in rationale.source_reference_ids]
            assert cited, "a personalized question without its material cannot be checked"
            for reference_id in cited:
                reference = by_id[reference_id]
                assert reference.question_turn_id == rationale.question_turn_id
                assert reference.excerpt
                assert reference.locator
        # One submitted excerpt motivated two questions; the console de-duplicates it, so
        # the seed has to actually contain that case.
        source_ids = [row.source_id for row in references]
        assert len(set(source_ids)) < len(source_ids)
        assert {row.source_type for row in references} == {
            "submission_chunk",
            "candidate_code_unit",
        }


def test_local_demo_seed_backfills_question_rationales_into_an_existing_database(
    tmp_path: Path,
) -> None:
    """A machine seeded before rationales existed still gets them on the next boot.

    The session guard returns early once a session exists, so anything written only on the
    first run never reaches a developer who seeded yesterday. Deleting the rows stands in
    for that older database.
    """
    database_url = f"sqlite+pysqlite:///{tmp_path / 'seed.db'}"
    engine = create_engine(database_url)
    for metadata in (CompanyBase.metadata, InterviewBase.metadata, ReportingBase.metadata):
        metadata.create_all(engine)
    environment = {
        "DATABASE_URL": database_url,
        "LOCAL_COMPANY_ID": str(COMPANY_ID),
        "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
        "LOCAL_DEMO_DATA_ENABLED": "true",
    }
    seed_local_company(environment)

    with Session(engine) as session:
        session.execute(delete(QuestionRationaleRow))
        session.execute(delete(QuestionSourceReferenceRow))
        session.commit()

    seed_local_company(environment)

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(QuestionRationaleRow)) == 3
        assert session.scalar(select(func.count()).select_from(QuestionSourceReferenceRow)) == 4


def _count(session: Session, row_type: type, session_id: UUID) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(row_type)
            .where(row_type.interview_session_id == session_id)
        )
        or 0
    )


def test_the_seeded_principal_carries_the_identity_the_token_will_present(
    tmp_path: Path,
) -> None:
    """`get_company_principal` looks the caller up by `identity_subject` and nothing else.

    Against Cognito that value is the pool's `sub` for the user, which is not knowable until
    the user exists -- so it has to be settable. A row written under the compose default
    instead authenticates a login and then answers every request with 401, which reads as a
    broken token rather than as a seed that named the wrong subject.
    """
    database_url = f"sqlite+pysqlite:///{tmp_path / 'seed.db'}"
    engine = create_engine(database_url)
    for metadata in (CompanyBase.metadata, InterviewBase.metadata, ReportingBase.metadata):
        metadata.create_all(engine)
    subject = "5d6b1f6e-0000-4000-8000-000000000abc"
    environment = {
        "DATABASE_URL": database_url,
        "LOCAL_COMPANY_ID": str(COMPANY_ID),
        "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
        "LOCAL_COMPANY_IDENTITY_SUBJECT": subject,
        "LOCAL_COMPANY_EMAIL": "operator@example.test",
        "LOCAL_COMPANY_NAME": "배포 검증 회사",
    }

    seed_local_company(environment)

    with Session(engine) as session:
        user = session.scalars(select(CompanyUserRow)).one()
        assert user.identity_subject == subject
        assert user.email_normalized == "operator@example.test"
        assert session.scalars(select(CompanyRow)).one().name == "배포 검증 회사"
