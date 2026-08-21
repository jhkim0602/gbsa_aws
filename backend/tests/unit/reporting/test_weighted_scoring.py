"""Weighted aggregation, and the divisor it has to hand back.

The arithmetic is the easy part. What these tests pin is the three ways it can be wrong without
raising: an unscored entry counted as zero, a divisor that is assumed to be 1.0, and a report
whose number changes after the company edits a weight.
"""

from uuid import UUID

from interview_evidence.reporting.domain.report import (
    COMMUNICATION_SEPARATED_CONFIG_VERSION,
    AssessmentState,
    AxisAssessment,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
)
from interview_evidence.reporting.domain.scoring import Entry, aggregate, weights_for
from interview_evidence.shared.assessment_axes import ASSESSMENT_AXIS_KEYS

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000002")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000003")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000004")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000005")
EVIDENCE_ID = UUID("00000000-0000-7000-8000-000000000006")


def axis(key: str, score: int | None) -> AxisAssessment:
    return AxisAssessment(
        axis=key,
        label=key,
        score=score,
        rationale="근거",
        # A scored axis must cite Evidence; ReportItem enforces it, so the fixture obeys it.
        quoted_evidence_ids=(EVIDENCE_ID,) if score is not None else (),
    )


def item(
    criterion_index: int,
    *,
    axes: tuple[AxisAssessment, ...],
    criterion_weight: float = 1.0,
    axis_weights: dict[str, float] | None = None,
) -> ReportItem:
    return ReportItem(
        report_item_id=UUID(int=0x7000_0000 + criterion_index),
        company_id=COMPANY_ID,
        report_id=REPORT_ID,
        criterion_id=UUID(int=0x8000_0000 + criterion_index),
        competency_model_version_id=VERSION_ID,
        # INSUFFICIENT_EVIDENCE so the fixture needs no Evidence rows; the arithmetic under test
        # does not read the state.
        assessment_state=AssessmentState.INSUFFICIENT_EVIDENCE,
        observation="관찰",
        rationale="근거",
        sufficiency="insufficient",
        uncertainty="사람 검토 필요",
        evidence=(),
        axis_assessments=axes,
        criterion_weight=criterion_weight,
        axis_weights=axis_weights or {},
    )


def report(
    items: tuple[ReportItem, ...],
    *,
    config_version: str = "c",
) -> Report:
    return Report(
        report_id=REPORT_ID,
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        invitation_id=INVITATION_ID,
        version=1,
        kind=ReportKind.AI_ORIGINAL,
        model_version="m",
        prompt_version="p",
        config_version=config_version,
        status=ReportStatus.READY,
        summary="요약",
        created_at=__import__("datetime").datetime(2026, 8, 20, tzinfo=__import__("datetime").UTC),
        items=items,
    )


def test_the_spec_example_reproduces_exactly() -> None:
    """30/25/20/25 with the fourth criterion unscored is 55.7 ÷ 0.75 = 74.

    Pinned as a literal because it is the example the reviewer's calculator renders, and a
    rounding or normalisation change would move a number a recruiter compares candidates on.
    """
    result = aggregate(
        [
            Entry("A", 85, 30.0),
            Entry("B", 72, 25.0),
            Entry("C", 61, 20.0),
            Entry("D", None, 25.0),
        ]
    )

    assert round(result.numerator, 10) == 55.7
    assert round(result.denominator, 10) == 0.75
    assert result.score == 74


def test_an_unscored_entry_leaves_both_the_numerator_and_the_divisor() -> None:
    """Dropping it from the numerator alone would silently score it zero.

    With one of two equal criteria unscored, the answer is the other one's score -- not half
    of it.
    """
    result = aggregate([Entry("A", 80, 50.0), Entry("B", None, 50.0)])

    assert result.score == 80
    assert round(result.denominator, 10) == 0.5
    assert [exclusion.key for exclusion in result.exclusions] == ["B"]


def test_nothing_scored_is_none_and_never_zero() -> None:
    result = aggregate([Entry("A", None, 60.0), Entry("B", None, 40.0)])

    assert result.score is None
    assert result.numerator == 0.0
    assert result.denominator == 0.0


def test_a_zero_weight_entry_is_excluded_from_the_score_not_counted() -> None:
    """A recruiter setting an axis to 0 means "do not look at this one here".

    It must not pull the score toward its own value, and it must not divide by anything.
    """
    result = aggregate([Entry("A", 90, 100.0), Entry("B", 10, 0.0)])

    assert result.score == 90


def test_absent_weights_reproduce_the_plain_mean() -> None:
    """Reports written before weights existed carry none, and were scored as a plain mean.

    Reading them as equal weight reproduces their numbers instead of restating their history.
    """
    weighted = aggregate([Entry("A", 90, 0.0), Entry("B", 80, 0.0), Entry("C", None, 0.0)])

    assert weighted.score == 85


def test_weights_for_defaults_an_unnamed_key_to_one_not_zero() -> None:
    assert weights_for(["depth", "correctness"], {"depth": 40.0}) == (40.0, 1.0)
    assert weights_for(list(ASSESSMENT_AXIS_KEYS), {}) == (1.0,) * 5


def test_a_criterion_score_applies_its_axis_weights() -> None:
    scored = item(
        1,
        axes=(axis("correctness", 90), axis("depth", 60)),
        axis_weights={"correctness": 75.0, "depth": 25.0},
    )

    # 0.75*90 + 0.25*60 = 82.5 -> 82 (round-half-to-even, matching the previous behaviour)
    assert scored.average_score == 82
    assert scored.axis_aggregate.denominator == 1.0


def test_new_reports_separate_communication_from_competency_scoring() -> None:
    scored = item(
        1,
        axes=(axis("correctness", 90), axis("communication", 30)),
        axis_weights={"correctness": 50.0, "communication": 50.0},
    )
    separated = report(
        (scored,),
        config_version=COMMUNICATION_SEPARATED_CONFIG_VERSION,
    )

    assert scored.average_score == 60
    assert scored.competency_score == 90
    assert separated.overall_score == 90
    assert separated.communication_score == 30


def test_legacy_reports_keep_communication_in_their_original_score() -> None:
    scored = item(
        1,
        axes=(axis("correctness", 90), axis("communication", 30)),
        axis_weights={"correctness": 50.0, "communication": 50.0},
    )

    assert report((scored,)).overall_score == 60


def test_a_report_score_applies_its_criterion_weights() -> None:
    heavy = item(1, axes=(axis("depth", 90),), criterion_weight=80.0)
    light = item(2, axes=(axis("depth", 40),), criterion_weight=20.0)

    # 0.8*90 + 0.2*40 = 80 -- a plain mean would have said 65.
    assert report((heavy, light)).overall_score == 80


def test_an_unreached_criterion_shrinks_the_divisor_and_is_reported() -> None:
    """The criterion is in the report with its weight, not missing from it.

    A criterion dropped from the report entirely would shrink the divisor with nothing on the
    screen to say that a quarter of the interview never happened.
    """
    answered = item(1, axes=(axis("depth", 80),), criterion_weight=75.0)
    unreached = item(2, axes=(), criterion_weight=25.0)

    result = report((answered, unreached)).criterion_aggregate

    assert result.score == 80
    assert round(result.denominator, 10) == 0.75
    assert [exclusion.normalized_weight for exclusion in result.exclusions] == [0.25]


def test_changing_a_weight_cannot_change_a_stored_report() -> None:
    """The weights live on the item, so a report is scored by what it froze.

    This is the invariant the whole freeze exists for: a reviewer who advanced a candidate at 80
    must not reopen the report and find 65 because the company re-weighted its criteria.
    """
    frozen = report(
        (
            item(1, axes=(axis("depth", 90),), criterion_weight=80.0),
            item(2, axes=(axis("depth", 40),), criterion_weight=20.0),
        )
    )
    assert frozen.overall_score == 80

    # What a re-weighted version would produce, built as a *new* report -- the stored one is
    # untouched because nothing reads the version at display time.
    reweighted = report(
        (
            item(1, axes=(axis("depth", 90),), criterion_weight=20.0),
            item(2, axes=(axis("depth", 40),), criterion_weight=80.0),
        )
    )

    assert reweighted.overall_score == 50
    assert frozen.overall_score == 80
