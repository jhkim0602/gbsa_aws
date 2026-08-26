from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from interview_evidence.reporting.domain.report import (
    RequirementAssessment,
    RequirementAssessmentStatus,
    RequirementEvidence,
    RequirementEvidenceRelation,
)
from interview_evidence.shared.aws_clients.ports import AIModel
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext

TASK_ASSESS_REQUIREMENT: Final = "assess_job_requirement"
ANTHROPIC_BEDROCK_VERSION: Final = "bedrock-2023-05-31"


@dataclass(frozen=True, slots=True)
class RequirementDefinition:
    job_requirement_id: UUID
    requirement_type: str
    statement: str


@dataclass(frozen=True, slots=True)
class RequirementEvidenceCandidate:
    evidence_id: UUID
    source_kind: str
    source_type: str
    excerpt: str
    locator: Mapping[str, object]


class RequirementSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: UUID
    relation: RequirementEvidenceRelation
    explanation: str = Field(min_length=1, max_length=2_000)


class RequirementVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    signals: tuple[RequirementSignal, ...] = ()


class RequirementAssessmentUnavailable(ConnectionError):
    pass


class RequirementAssessor:
    def __init__(self, model: AIModel, *, require_assessment: bool = False) -> None:
        self._model = model
        self._require_assessment = require_assessment

    def assess(
        self,
        context: TenantContext,
        *,
        requirement: RequirementDefinition,
        candidates: Sequence[RequirementEvidenceCandidate],
        model_config_version: str,
    ) -> RequirementAssessment:
        if not candidates:
            return _unknown(requirement, "제출 자료와 면접 답변에서 관련 근거를 찾지 못했습니다.")
        available = {candidate.evidence_id: candidate for candidate in candidates}
        try:
            response = self._model.generate(
                context,
                _build_prompt(
                    requirement=requirement,
                    candidates=candidates,
                    model_config_version=model_config_version,
                ),
            )
            verdict = _parse_response(response)
        except (
            RuntimeError,
            ConnectionError,
            TimeoutError,
            ValidationError,
            TypeError,
            ValueError,
            KeyError,
        ) as error:
            if self._require_assessment:
                raise RequirementAssessmentUnavailable(
                    "job requirement assessment generation unavailable"
                ) from error
            return _unknown(requirement, "자격요건 판정 모델을 사용할 수 없어 판단을 보류했습니다.")

        signals = tuple(
            signal
            for signal in verdict.signals
            if signal.evidence_id in available
        )
        decisive = tuple(
            signal
            for signal in signals
            if signal.relation
            in {
                RequirementEvidenceRelation.SUPPORTS,
                RequirementEvidenceRelation.PARTIALLY_SUPPORTS,
                RequirementEvidenceRelation.CONTRADICTS,
            }
        )
        status = _status_from(decisive)
        if status is RequirementAssessmentStatus.UNKNOWN:
            return _unknown(
                requirement,
                "관련 내용은 있으나 충족 여부를 판단할 직접 근거가 없습니다.",
            )
        evidence = tuple(
            RequirementEvidence(
                evidence_id=signal.evidence_id,
                source_kind=available[signal.evidence_id].source_kind,
                source_type=available[signal.evidence_id].source_type,
                excerpt=available[signal.evidence_id].excerpt,
                locator=dict(available[signal.evidence_id].locator),
                relation=signal.relation,
                explanation=signal.explanation,
            )
            for signal in decisive
        )
        return RequirementAssessment(
            requirement_assessment_id=new_uuid7(),
            job_requirement_id=requirement.job_requirement_id,
            requirement_type=requirement.requirement_type,
            statement=requirement.statement,
            status=status,
            rationale=_rationale(status, decisive),
            confidence=_confidence(status, decisive),
            evidence=evidence,
        )


def _status_from(
    signals: Sequence[RequirementSignal],
) -> RequirementAssessmentStatus:
    complete = sum(
        signal.relation is RequirementEvidenceRelation.SUPPORTS for signal in signals
    )
    partial = sum(
        signal.relation is RequirementEvidenceRelation.PARTIALLY_SUPPORTS
        for signal in signals
    )
    contradicted = sum(
        signal.relation is RequirementEvidenceRelation.CONTRADICTS for signal in signals
    )
    if complete and not contradicted:
        return RequirementAssessmentStatus.MET
    if contradicted and not complete and not partial:
        return RequirementAssessmentStatus.NOT_MET
    if complete or partial or contradicted:
        return RequirementAssessmentStatus.PARTIALLY_MET
    return RequirementAssessmentStatus.UNKNOWN


def _confidence(
    status: RequirementAssessmentStatus,
    signals: Sequence[RequirementSignal],
) -> float:
    if status is RequirementAssessmentStatus.MET:
        complete = sum(
            signal.relation is RequirementEvidenceRelation.SUPPORTS
            for signal in signals
        )
        return min(0.95, 0.8 + max(0, complete - 1) * 0.05)
    if status is RequirementAssessmentStatus.NOT_MET:
        return min(0.95, 0.8 + max(0, len(signals) - 1) * 0.05)
    if status is RequirementAssessmentStatus.PARTIALLY_MET:
        return min(0.8, 0.6 + max(0, len(signals) - 1) * 0.05)
    return 0


def _rationale(
    status: RequirementAssessmentStatus,
    signals: Sequence[RequirementSignal],
) -> str:
    prefix = {
        RequirementAssessmentStatus.MET: "요건을 직접 뒷받침하는 근거를 확인했습니다.",
        RequirementAssessmentStatus.PARTIALLY_MET: (
            "요건과 관련된 근거는 있으나 일부 확인이 더 필요합니다."
        ),
        RequirementAssessmentStatus.NOT_MET: (
            "지원자의 자료 또는 답변에서 요건을 충족하지 못한다는 "
            "명시적 근거를 확인했습니다."
        ),
        RequirementAssessmentStatus.UNKNOWN: "충족 여부를 판단할 근거가 없습니다.",
    }[status]
    explanations = " ".join(signal.explanation.strip() for signal in signals[:2])
    return f"{prefix} {explanations}".strip()


def _unknown(requirement: RequirementDefinition, rationale: str) -> RequirementAssessment:
    return RequirementAssessment(
        requirement_assessment_id=new_uuid7(),
        job_requirement_id=requirement.job_requirement_id,
        requirement_type=requirement.requirement_type,
        statement=requirement.statement,
        status=RequirementAssessmentStatus.UNKNOWN,
        rationale=rationale,
        confidence=0,
        evidence=(),
    )


def _build_prompt(
    *,
    requirement: RequirementDefinition,
    candidates: Sequence[RequirementEvidenceCandidate],
    model_config_version: str,
) -> dict[str, Any]:
    payload = {
        "task": TASK_ASSESS_REQUIREMENT,
        "requirement": {
            "job_requirement_id": str(requirement.job_requirement_id),
            "type": requirement.requirement_type,
            "statement": requirement.statement,
        },
        "evidence_candidates": [
            {
                "evidence_id": str(candidate.evidence_id),
                "source_kind": candidate.source_kind,
                "source_type": candidate.source_type,
                "excerpt": candidate.excerpt,
                "locator": dict(candidate.locator),
            }
            for candidate in candidates
        ],
        "relations": [relation.value for relation in RequirementEvidenceRelation],
        "model_config_version": model_config_version,
    }
    system = """당신은 채용 자격요건의 근거를 분류하는 분석가입니다.
제공된 자료와 면접 답변만 사용하며, 최종 합격 여부나 점수는 만들지 않습니다.
각 근거를 다음 중 하나로만 분류합니다.
- supports: 요건 전체를 직접 뒷받침함
- partially_supports: 요건 일부 또는 간접 내용만 뒷받침함
- contradicts: 지원자가 해당 경험·지식이 없다고 명시하거나 요건과 반대되는 사실을 말함

자료에 내용이 없다는 이유만으로 contradicts를 사용하지 마십시오. 관련 없는 근거는 signals에서
제외하십시오. 모든 signal은 입력으로 받은 evidence_id만 사용해야 합니다.
설명이나 머리말 없이 다음 형식의 JSON 객체 하나만 출력하십시오.
{\"signals\":[{\"evidence_id\":\"uuid\",
\"relation\":\"supports|partially_supports|contradicts\",
\"explanation\":\"한국어 근거 설명\"}]}"""
    return {
        "anthropic_version": ANTHROPIC_BEDROCK_VERSION,
        "system": system,
        "max_tokens": 1_500,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, ensure_ascii=False),
                    }
                ],
            }
        ],
    }


def _parse_response(response: Mapping[str, Any]) -> RequirementVerdict:
    if "signals" in response:
        return RequirementVerdict.model_validate(response)
    content = response.get("content")
    if not isinstance(content, list):
        raise ValueError("model response has neither requirement signals nor content blocks")
    text = "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, Mapping) and block.get("type", "text") == "text"
    ).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    decoded = json.loads(text)
    if not isinstance(decoded, Mapping):
        raise ValueError("requirement response body is not a JSON object")
    return RequirementVerdict.model_validate(decoded)
