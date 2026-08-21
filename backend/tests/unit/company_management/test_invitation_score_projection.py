"""The invitation list carries a score, and the coverage that score was taken over.

A ranked column of bare numbers is a comparison the data does not support: two applicants whose
interviews reached different criteria were measured over different denominators. So the counts
travel with the score, and `_invitation_view` has to pass all three through rather than only the
one the column sorts on.

`test_invitation_review_projection.py` would be the natural home for this, but it fails at
collection -- it imports in-memory doubles that `7d977f7` deleted. This covers the view function
directly instead, with a stub in the shape of the `InvitationReviewSnapshot` protocol.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.company_management.api.company_routes import _invitation_view
from interview_evidence.company_management.domain.hiring import Invitation
from interview_evidence.shared.submission_materials import DEFAULT_SUBMISSION_REQUIREMENTS
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000002")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000003")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000004")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000005")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000006")


@dataclass(frozen=True, slots=True)
class StubReview:
    """Shaped like `InvitationReviewSnapshot`, which is a Protocol rather than a class."""

    report_status: str
    overall_score: int | None
    scored_criteria_count: int
    total_criteria_count: int


class StubReviews:
    def __init__(self, review: StubReview | None) -> None:
        self._review = review

    def get_invitation_review(
        self, context: TenantContext, *, invitation_id: UUID
    ) -> StubReview | None:
        del context, invitation_id
        return self._review


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID(int=99),
        request_id=UUID(int=98),
        trace_id="trace",
    )


def invitation() -> Invitation:
    return Invitation.create(
        invitation_id=INVITATION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        competency_model_version_id=VERSION_ID,
        applicant_id=UUID("00000000-0000-7000-8000-000000000007"),
        applicant_email="applicant@example.test",
        applicant_display_name="지원자",
        token_hash="a" * 64,
        expires_at=datetime(2026, 9, 1, tzinfo=UTC),
        submission_requirements=DEFAULT_SUBMISSION_REQUIREMENTS,
    )


def test_the_score_travels_with_the_coverage_it_was_taken_over() -> None:
    view = _invitation_view(
        invitation(),
        invitation_reviews=StubReviews(
            StubReview(
                report_status="ready",
                overall_score=82,
                scored_criteria_count=3,
                total_criteria_count=4,
            )
        ),
        context=context(),
    )

    assert view.overall_score == 82
    # Both counts, not just the score: 82 over three of four criteria is not the same
    # measurement as 82 over all four, and the column has to be able to say so.
    assert view.scored_criteria_count == 3
    assert view.total_criteria_count == 4


def test_an_invitation_without_a_report_reports_no_score_and_no_coverage() -> None:
    """None rather than 0. Zero would sort an applicant who has not interviewed yet below one

    who answered badly, and "0 of 0" would render as a coverage figure for an interview that
    never happened.
    """
    view = _invitation_view(invitation(), invitation_reviews=None, context=context())

    assert view.overall_score is None
    assert view.scored_criteria_count is None
    assert view.total_criteria_count is None


def test_a_report_that_could_not_be_scored_reports_none_not_zero() -> None:
    view = _invitation_view(
        invitation(),
        invitation_reviews=StubReviews(
            StubReview(
                report_status="partial",
                overall_score=None,
                scored_criteria_count=0,
                total_criteria_count=4,
            )
        ),
        context=context(),
    )

    assert view.overall_score is None
    # The coverage is still reported: "0 of 4" says the interview happened and produced nothing
    # scoreable, which is different from not having interviewed.
    assert view.scored_criteria_count == 0
    assert view.total_criteria_count == 4
    assert view.report_status == "partial"
