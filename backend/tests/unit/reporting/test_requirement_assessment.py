from typing import Any
from uuid import UUID

import pytest
from interview_evidence.reporting.application.requirement_assessment import (
    RequirementAssessmentUnavailable,
    RequirementAssessor,
    RequirementDefinition,
    RequirementEvidenceCandidate,
)
from interview_evidence.reporting.domain.report import RequirementAssessmentStatus
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
REQUIREMENT_ID = UUID("00000000-0000-7000-8000-000000000002")
EVIDENCE_ID = UUID("00000000-0000-7000-8000-000000000003")


class StubModel:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def generate(
        self,
        _context: TenantContext,
        _model_input: dict[str, Any],
    ) -> dict[str, Any]:
        return self._response


class FailingModel:
    def generate(
        self,
        _context: TenantContext,
        _model_input: dict[str, Any],
    ) -> dict[str, Any]:
        raise TimeoutError("model unavailable")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=REQUIREMENT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="requirement-assessment",
    )


def _requirement() -> RequirementDefinition:
    return RequirementDefinition(
        job_requirement_id=REQUIREMENT_ID,
        requirement_type="required",
        statement="Java 기반 서비스 개발 경험",
    )


def _candidate() -> RequirementEvidenceCandidate:
    return RequirementEvidenceCandidate(
        evidence_id=EVIDENCE_ID,
        source_kind="submission",
        source_type="resume",
        excerpt="Java와 Spring Boot로 주문 서비스를 개발했습니다.",
        locator={"page": 2},
    )


def _assess(relation: str) -> RequirementAssessmentStatus:
    assessment = RequirementAssessor(
        StubModel(
            {
                "signals": [
                    {
                        "evidence_id": str(EVIDENCE_ID),
                        "relation": relation,
                        "explanation": "지원자가 직접 수행한 경험을 명시했습니다.",
                    }
                ]
            }
        )
    ).assess(
        _context(),
        requirement=_requirement(),
        candidates=(_candidate(),),
        model_config_version="test-v1",
    )
    assert assessment.evidence[0].evidence_id == EVIDENCE_ID
    return assessment.status


def test_no_evidence_is_unknown_instead_of_not_met() -> None:
    assessment = RequirementAssessor(StubModel({})).assess(
        _context(),
        requirement=_requirement(),
        candidates=(),
        model_config_version="test-v1",
    )

    assert assessment.status is RequirementAssessmentStatus.UNKNOWN
    assert assessment.evidence == ()


@pytest.mark.parametrize(
    ("relation", "expected"),
    (
        ("supports", RequirementAssessmentStatus.MET),
        ("partially_supports", RequirementAssessmentStatus.PARTIALLY_MET),
        ("contradicts", RequirementAssessmentStatus.NOT_MET),
    ),
)
def test_model_signals_are_converted_by_deterministic_rules(
    relation: str,
    expected: RequirementAssessmentStatus,
) -> None:
    assert _assess(relation) is expected


def test_invented_evidence_id_is_ignored() -> None:
    assessment = RequirementAssessor(
        StubModel(
            {
                "signals": [
                    {
                        "evidence_id": "00000000-0000-7000-8000-000000000099",
                        "relation": "supports",
                        "explanation": "입력에 없는 근거입니다.",
                    }
                ]
            }
        )
    ).assess(
        _context(),
        requirement=_requirement(),
        candidates=(_candidate(),),
        model_config_version="test-v1",
    )

    assert assessment.status is RequirementAssessmentStatus.UNKNOWN
    assert assessment.evidence == ()


def test_required_assessment_failure_is_retried_by_worker() -> None:
    with pytest.raises(RequirementAssessmentUnavailable):
        RequirementAssessor(FailingModel(), require_assessment=True).assess(
            _context(),
            requirement=_requirement(),
            candidates=(_candidate(),),
            model_config_version="test-v1",
        )
