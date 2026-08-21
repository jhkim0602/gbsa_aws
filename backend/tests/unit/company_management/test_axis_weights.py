"""Weights are percentages, and they are refused at publish time rather than at scoring time.

``CompetencyModelVersion`` is frozen and locks on publish, and the report freezes the weights
it scored with. So a set of weights that cannot be read as the recruiter meant it has to fail
while they are still looking at the form. Caught later -- during report generation -- the
interview has already happened and there is nothing left to correct.

Both totals must be 100. That is a decision about what the recruiter reads, not about
arithmetic: accepting any positive total and dividing by it yields the same scores, but leaves
30 on screen meaning 40%. Requiring 100 makes the number on the slider the share it carries,
and the console keeps it there by redistributing the others as one is dragged.

Every case here is one that would otherwise produce a wrong number rather than an error.
"""

from uuid import UUID

import pytest
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    EvaluationCriterion,
)
from interview_evidence.shared.assessment_axes import ASSESSMENT_AXIS_KEYS

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000002")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000003")

#: A complete mapping totalling 100. ``fundamentals`` is zero on purpose: "do not look at CS
#: fundamentals for this position" is a legitimate choice, and it must not be confused with
#: omitting the key, which is not.
EVERY_AXIS = {
    "correctness": 25.0,
    "depth": 30.0,
    "fundamentals": 0.0,
    "ownership": 25.0,
    "communication": 20.0,
}


def criterion(code: str, weight: float) -> EvaluationCriterion:
    return EvaluationCriterion(
        criterion_id=UUID(int=int(code.encode().hex(), 16) % 10**12),
        code=code,
        name="시스템 설계",
        description="설계 판단과 트레이드오프를 확인한다.",
        weight=weight,
        abstain_guidance="관련 답변이 없으면 판단을 유보한다.",
        required=True,
    )


def version(
    *,
    axis_weights: dict[str, float] | None = None,
    criteria: tuple[EvaluationCriterion, ...] | None = None,
) -> CompetencyModelVersion:
    return CompetencyModelVersion.create(
        competency_model_version_id=VERSION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        version_number=1,
        criteria=criteria or (criterion("SD", 60.0), criterion("PS", 40.0)),
        prohibited_topics=(),
        interview_duration_minutes=30,
        axis_weights=axis_weights,
    )


def test_criterion_weights_must_total_100() -> None:
    with pytest.raises(ValueError, match="criterion weights must total 100"):
        version(criteria=(criterion("SD", 30.0), criterion("PS", 25.0)))


def test_criterion_weights_that_are_all_zero_are_refused() -> None:
    """Not a special case -- zero simply is not 100. Kept because it is the total that

    scoring would have divided by, and dividing by it is the failure this prevents.
    """
    with pytest.raises(ValueError, match="criterion weights must total 100"):
        version(criteria=(criterion("SD", 0.0), criterion("PS", 0.0)))


def test_a_float_total_within_tolerance_is_accepted() -> None:
    """The console redistributes weights, so three shares of 100 do not land exactly.

    An exact ``== 100`` would reject a set the UI itself produced.
    """
    thirds = (
        criterion("AA", 33.33333333333333),
        criterion("BB", 33.33333333333333),
        criterion("CC", 33.33333333333334),
    )

    assert len(version(criteria=thirds).criteria) == 3


def test_an_omitted_axis_mapping_means_equal_weight() -> None:
    """Every version published before axis weights existed reads back this way.

    That is also how those interviews were actually scored, so it is the honest default. A
    migration filling in explicit weights would restate history.
    """
    assert version().axis_weights == {}
    assert version(axis_weights={}).axis_weights == {}


def test_a_complete_axis_mapping_is_kept_verbatim_including_zero() -> None:
    assert version(axis_weights=EVERY_AXIS).axis_weights == EVERY_AXIS


def test_an_unknown_axis_key_is_refused() -> None:
    """A typo matches no axis and would be silently dropped.

    The recruiter would leave the form believing 정확성 was weighted, and the score would come
    out as though they had never touched it.
    """
    with pytest.raises(ValueError, match="unknown assessment axis weights"):
        version(axis_weights={**EVERY_AXIS, "correctnes": 10.0})


def test_a_partial_axis_mapping_is_refused() -> None:
    """There is no reading of the absent keys that is not a wrong score.

    Zero drops three axes out of the criterion score; one adds 40 and 1 on the same scale.
    Neither shows on screen, so the mapping is all or nothing.
    """
    with pytest.raises(ValueError, match="must name every scoring axis"):
        version(axis_weights={"depth": 60.0, "correctness": 40.0})


def test_every_axis_key_must_be_present_not_merely_the_right_count() -> None:
    swapped = {key: 20.0 for key in ASSESSMENT_AXIS_KEYS[:-1]}
    swapped["not_an_axis"] = 20.0

    with pytest.raises(ValueError, match="unknown assessment axis weights"):
        version(axis_weights=swapped)


def test_a_negative_axis_weight_is_refused() -> None:
    """Negative weight would mean doing well on an axis lowers the score.

    That inverts the ranking table rather than expressing a preference, and `Field(ge=0)` does
    not reach inside a dict's values.
    """
    with pytest.raises(ValueError, match="cannot be negative"):
        version(axis_weights={**EVERY_AXIS, "depth": -1.0})


def test_axis_weights_must_also_total_100() -> None:
    """The same rule as the criteria, so one slider means one share on both screens."""
    with pytest.raises(ValueError, match="axis weights must total 100"):
        version(axis_weights=dict.fromkeys(ASSESSMENT_AXIS_KEYS, 10.0))


def test_axis_weights_that_are_all_zero_are_refused() -> None:
    with pytest.raises(ValueError, match="axis weights must total 100"):
        version(axis_weights=dict.fromkeys(ASSESSMENT_AXIS_KEYS, 0.0))


def test_a_stored_version_can_be_read_back_with_a_total_that_predates_the_rule() -> None:
    """Reading a row is not publishing a form, and only one of the two can be held to this.

    ``weight`` has existed since ``a_001`` with nothing enforcing a total -- the wizard showed
    ``합계 {totalWeight}`` and never checked it -- so stored versions really do total something
    other than 100. As a pydantic validator this rule also ran on the construction the
    repository performs to read a row, which turned every read of those versions into a 500:
    the criteria list, applicant access, the hiring workspace, question generation, the
    interview and report generation. It even blocked creating a *new* version, because
    ``create_version`` lists the existing ones first.

    Nothing is lost by reading them: ``scoring.aggregate`` divides by whatever the weights
    total, so 30/25/20 already scores as 40%/33%/27% -- the proportions the recruiter set.
    """
    stored = CompetencyModelVersion(
        competency_model_version_id=VERSION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        version_number=1,
        criteria=(criterion("SD", 30.0), criterion("PS", 25.0), criterion("CM", 20.0)),
        prohibited_topics=(),
        interview_duration_minutes=30,
    )

    assert [item.weight for item in stored.criteria] == [30.0, 25.0, 20.0]


def test_the_rule_still_refuses_what_a_recruiter_submits() -> None:
    """The counterpart to the case above: tolerant on read, strict on the way in.

    ``create`` is the only path a version reaches the database by, and ``criteria`` cannot be
    replaced afterwards, so checking there holds for the version's whole life.
    """
    with pytest.raises(ValueError, match="criterion weights must total 100"):
        version(criteria=(criterion("SD", 30.0), criterion("PS", 25.0), criterion("CM", 20.0)))
