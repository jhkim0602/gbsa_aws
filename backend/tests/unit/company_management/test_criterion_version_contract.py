"""The criteria request/response models and the published contract describe the same thing.

Two defects this closes, both found by running the console against a real database rather than
by any test.

The first: the console posts ``axis_weights`` and the contract declares it on both schemas, but
``CompetencyModelVersionCreate`` never gained the field while keeping ``extra="forbid"``. Every
publish request was rejected with ``extra_forbidden``, so the five axis sliders -- the only way
a company sets axis weights -- could not reach the database at all. ``npm run typecheck`` cannot
see it because the request body is assembled with ``JSON.stringify({...})``, which type-checks
an object literal against nothing.

The second: ``CompetencyModelVersionView`` inherits from the create model, so a validator meant
for requests also ran on responses. When the "weights total 100" rule moved onto the domain in
``m_013`` a copy stayed here, and versions stored before the rule existed -- the normal case,
since nothing enforced a total before -- could no longer be serialised. Reading the criteria
list returned 500.

Both are the drift ``docs/specs/track-2-scoring-and-review.md`` §9.1 describes: with the
contract generator gone, ``packages/contracts/openapi/`` is hand-maintained and nothing compares
it to the routes. The field-parity test below is the check that was missing.
"""

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml
from interview_evidence.company_management.api.company_routes import (
    CompetencyModelVersionCreate,
    CompetencyModelVersionView,
    _criterion_view,
    _domain_error_detail,
)
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelStatus,
    CompetencyModelVersion,
    EvaluationCriterion,
)
from interview_evidence.shared.assessment_axes import ASSESSMENT_AXIS_KEYS
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[4]
CONTRACT = ROOT / "packages/contracts/openapi/root.yaml"

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000002")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000003")

EVERY_AXIS = {
    "correctness": 30.0,
    "depth": 25.0,
    "fundamentals": 15.0,
    "ownership": 20.0,
    "communication": 10.0,
}


def schemas() -> dict[str, Any]:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    return dict(document["components"]["schemas"])


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


def stored_version(
    *,
    criteria: tuple[EvaluationCriterion, ...],
    axis_weights: dict[str, float] | None = None,
) -> CompetencyModelVersion:
    """Build a version the way the repository does when it reads a row back.

    ``CompetencyModelVersion(...)`` rather than ``.create(...)`` on purpose: that is the call
    ``_criterion_versions_from_rows`` makes, and the whole point of these cases is what a
    *stored* row is allowed to look like.
    """
    return CompetencyModelVersion(
        competency_model_version_id=VERSION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        version_number=1,
        criteria=criteria,
        prohibited_topics=(),
        interview_duration_minutes=30,
        axis_weights=dict(axis_weights or {}),
    )


def test_the_request_model_declares_every_field_the_contract_does() -> None:
    """The check that was missing when ``axis_weights`` shipped in the contract only.

    ``extra="forbid"`` turns a field the contract declares and the model lacks into a rejected
    request rather than an ignored value, so this is the difference between a working publish
    and a 422.
    """
    declared = set(schemas()["CompetencyModelVersionCreate"]["properties"])

    assert declared - set(CompetencyModelVersionCreate.model_fields) == set()


def test_the_response_model_declares_every_field_the_contract_does() -> None:
    declared = set(schemas()["CompetencyModelVersion"]["properties"])

    assert declared - set(CompetencyModelVersionView.model_fields) == set()


def requirement(code: str) -> dict[str, Any]:
    return {
        "requirement_type": "required",
        "statement": "대규모 트래픽 설계 경험",
        "priority": 1,
        "criterion_code": code,
    }


def test_the_request_model_accepts_the_axis_weights_the_console_posts() -> None:
    body = CompetencyModelVersionCreate.model_validate(
        {
            "job_requirements": [requirement("SD")],
            "criteria": [
                criterion("SD", 60.0).model_dump(exclude={"criterion_id"}),
                criterion("PS", 40.0).model_dump(exclude={"criterion_id"}),
            ],
            "prohibited_topics": [],
            "interview_duration_minutes": 30,
            "axis_weights": EVERY_AXIS,
        }
    )

    assert body.axis_weights == EVERY_AXIS


def test_an_unknown_body_field_is_still_refused() -> None:
    """``extra="forbid"`` is what made the missing field fatal, and it stays.

    A silently ignored ``axis_weigths`` typo would leave a recruiter believing they configured
    the axes, which is worse than the 422.
    """
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompetencyModelVersionCreate.model_validate(
            {
                "job_requirements": [requirement("SD")],
                "criteria": [criterion("SD", 100.0).model_dump(exclude={"criterion_id"})],
                "prohibited_topics": [],
                "interview_duration_minutes": 30,
                "axis_weigths": EVERY_AXIS,
            }
        )


def test_the_view_carries_the_axis_weights_back_to_the_wizard() -> None:
    """Without this the sliders reset to an equal split every time the version is reopened,

    which reads as the company having chosen that.
    """
    view = _criterion_view(
        stored_version(criteria=(criterion("SD", 100.0),), axis_weights=EVERY_AXIS)
    )

    assert view.axis_weights == EVERY_AXIS
    assert set(view.axis_weights) == set(ASSESSMENT_AXIS_KEYS)


def test_a_stored_version_whose_weights_predate_the_rule_still_serialises() -> None:
    """Reading is not publishing. Nothing enforced a total before ``m_013``, so a stored 25 is

    the normal case; refusing to serialise it turned the criteria list into a 500.
    """
    view = _criterion_view(stored_version(criteria=(criterion("SD", 25.0),)))

    assert [item.weight for item in view.criteria] == [25.0]
    assert view.status == CompetencyModelStatus.DRAFT.value


def test_the_system_managed_persona_serialises_as_no_persona() -> None:
    """A separate defect that hid behind the one above, and predates this branch.

    ``CompetencyModelVersion`` defaults ``persona_definition`` to a ``system_managed`` mapping
    that ``InterviewerPersonaDefinition`` does not describe -- no ``name``, ``neutral`` is not
    one of the four tones, ``mode`` is an extra key. Every version published without a persona
    carries it, so serialising it verbatim made the criteria list a 500 for a second reason.

    ``None`` is the honest answer, and the one the console already infers: ``toCompanyPersona``
    rejects the same three things and returns ``undefined``.
    """
    view = _criterion_view(stored_version(criteria=(criterion("SD", 100.0),)))

    assert view.persona_definition is None


def test_a_refused_weight_mapping_reaches_the_recruiter_as_one_sentence() -> None:
    """``detail`` goes straight to the console, so it has to read like a message.

    The axis rules live on a ``model_validator``, so what the route catches is a
    ``ValidationError`` whose ``str()`` wraps the sentence in type tags, an input dump and a
    documentation URL.
    """
    with pytest.raises(ValidationError) as raised:
        stored_version(
            criteria=(criterion("SD", 100.0),),
            axis_weights=dict.fromkeys(ASSESSMENT_AXIS_KEYS, 10.0),
        )

    assert _domain_error_detail(raised.value) == "axis weights must total 100, got 50"


def test_a_plain_domain_error_passes_through_unchanged() -> None:
    assert _domain_error_detail(ValueError("criterion weights must total 100, got 75")) == (
        "criterion weights must total 100, got 75"
    )


def test_a_recruiter_defined_persona_survives_the_round_trip() -> None:
    """The counterpart: dropping a real persona would silently discard a company's choice."""
    stored = stored_version(criteria=(criterion("SD", 100.0),))
    with_persona = stored.model_copy(
        update={
            "persona_definition": {
                "name": "시니어 백엔드 면접관",
                "tone": "analytical",
                "voice_id": "Seoyeon",
            }
        }
    )

    view = _criterion_view(with_persona)

    assert view.persona_definition is not None
    assert view.persona_definition.name == "시니어 백엔드 면접관"
    assert view.persona_definition.voice_id == "Seoyeon"
