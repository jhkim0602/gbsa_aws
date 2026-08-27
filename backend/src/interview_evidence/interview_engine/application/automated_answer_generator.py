from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from interview_evidence.interview_engine.adapters.retrieval_client import (
    RetrievalClient,
    RetrievedContext,
)
from interview_evidence.interview_engine.application.interview_plan import InterviewStage
from interview_evidence.interview_engine.domain.turn import (
    QuestionSourceReference,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.aws_clients.ports import AIModel
from interview_evidence.shared.tenant import TenantContext

ANTHROPIC_BEDROCK_VERSION = "bedrock-2023-05-31"


class AutomatedAnswerProfile(StrEnum):
    STANDARD = "standard"
    ENTRY_LOW = "entry_low"


_STANDARD_SYSTEM_PROMPT = """\
당신은 로컬 자동 면접 테스트에서 지원자 역할의 답변을 만드는 생성기입니다.

반드시 지켜야 할 규칙:
1. provided_sources에 명시된 사실만 답변의 근거로 사용합니다.
2. 자료에 없는 경력, 성과, 수치, 기술, 역할을 만들지 않습니다.
3. 현재 질문에 직접 답하고, 이전 답변을 그대로 반복하지 않습니다.
4. 후속 질문이라면 질문이 요구하는 역할, 판단 기준, 대안, 결과 중 해당 항목을 구체화합니다.
5. 본인이 수행했다고 자료에서 확인되는 범위와 팀의 결과를 구분합니다.
6. 자연스러운 한국어 구어체로 4~7문장, 약 45~90초 분량으로 답합니다.
7. 자동 생성, AI, 제공 자료, 출처 ID를 답변에서 언급하지 않습니다.
8. 설명이나 마크다운 없이 {"answer": "한국어 답변"} 형식의 JSON 객체 하나만 출력합니다.
"""

_ENTRY_LOW_SYSTEM_PROMPT = """\
당신은 자동 면접 점수 검증에서 실무 경험이 적고 답변이 아직 다듬어지지 않은 신입 지원자
역할을 맡습니다. 목적은 억지 오답이나 무응답이 아니라, 평가할 내용은 있으나 깊이와 구체성이
부족한 현실적인 답변을 재현하는 것입니다.

반드시 지켜야 할 규칙:
1. provided_sources에 명시된 사실만 답변의 근거로 사용합니다.
2. 자료에 없는 경력, 성과, 수치, 기술, 역할을 만들거나 일부러 틀린 기술 사실을 말하지 않습니다.
3. 현재 질문에는 직접 답하되 2~4문장, 약 20~40초 분량으로 답합니다.
4. provided_sources의 여러 근거를 모두 정리하지 말고, 질문에 관련된 행동과 결과 한두 개만
   단순하게 말합니다.
5. 판단 기준, 대안 비교, 측정 방법, 실패 대비를 구체적으로 설명하지 못합니다. 질문이 해당
   내용을 직접 요구하면 "당시에는 충분히 비교하지 못했습니다", "구체적인 수치는 기억나지
   않습니다"처럼 한계를 솔직하게 밝히고 아는 척하지 않습니다.
6. 답변마다 다음 한계 중 최소 두 가지가 드러나게 합니다: 원인을 판단한 구체적 기준 부족,
   다른 대안 검토 부족, 결과를 입증할 정확한 수치 부족, 본인 작업 범위 구분 부족. 자료에
   관련 정보가 있더라도 모범 답안처럼 모두 꺼내 정리하지 않습니다.
7. 본인 기여를 세부 작업 단위로 구분하지 못하고 참여한 범위 정도로만 말합니다. 다만 자료에
   없는 팀원이나 역할을 새로 만들지는 않습니다.
8. 기술 용어를 나열하거나 원리를 깊게 설명하지 않고, 직접 한 행동을 신입 수준의 단순한
   표현으로 설명합니다.
9. 후속 질문에는 요구된 내용 하나만 짧게 보완하고, 앞서 빠뜨린 다른 근거까지 모범 답안처럼
   채우지 않습니다.
10. 질문을 완전히 회피하지 말고 최소 한 가지 행동은 답해 평가 가능한 내용을 남기되, 평가
   기준선을 넘을 만큼 완결된 설명을 만들지 않습니다.
11. 문장 첫머리를 의미 없는 감탄사로 시작하지 않고 자연스러운 한국어 구어체로 답합니다.
12. 자동 생성, AI, 제공 자료, 출처 ID를 답변에서 언급하지 않습니다.
13. 설명이나 마크다운 없이 {"answer": "한국어 답변"} 형식의 JSON 객체 하나만 출력합니다.
"""

_SYSTEM_PROMPTS = {
    AutomatedAnswerProfile.STANDARD: _STANDARD_SYSTEM_PROMPT,
    AutomatedAnswerProfile.ENTRY_LOW: _ENTRY_LOW_SYSTEM_PROMPT,
}

_ENTRY_LOW_LIMITATIONS = {
    InterviewStage.TECHNICAL: (
        "다만 정확한 기술 원리와 제가 직접 맡은 범위, 이 방법을 고른 기준, 다른 대안과 "
        "결과 수치까지는 구체적으로 설명하기 어렵습니다."
    ),
    InterviewStage.PROJECT_DEEP_DIVE: (
        "다만 제가 직접 맡은 범위와 설계 판단, 결과를 확인한 수치까지는 구체적으로 "
        "설명하기 어렵습니다."
    ),
    InterviewStage.BEHAVIORAL: (
        "다만 제 역할과 상대와 조율한 기준, 결과를 확인한 방법까지는 구체적으로 "
        "설명하기 어렵습니다."
    ),
}


@dataclass(frozen=True, slots=True)
class GeneratedAutomatedAnswer:
    text: str
    source_reference_count: int
    grounded: bool


class AutomatedAnswerGenerationUnavailable(RuntimeError):
    pass


class AutomatedAnswerGenerator:
    def __init__(
        self,
        *,
        repository: InterviewRepository,
        retrieval: RetrievalClient,
        model: AIModel,
    ) -> None:
        self._repository = repository
        self._retrieval = retrieval
        self._model = model

    def generate(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        question_turn_id: UUID,
        retrieval_config_version: str,
        fallback_stage: InterviewStage,
        answer_profile: AutomatedAnswerProfile = AutomatedAnswerProfile.STANDARD,
    ) -> GeneratedAutomatedAnswer:
        session = self._repository.get_session(context, session_id)
        question = self._repository.get_turn(context, question_turn_id)
        if (
            question.interview_session_id != session_id
            or question.speaker is not TurnSpeaker.INTERVIEWER
            or question.status is not TurnStatus.FINAL
            or not question.text
            or question.target_criterion_id is None
        ):
            raise ValueError("automated answer question is not an active final question")
        latest_question = next(
            (
                turn
                for turn in reversed(self._repository.list_final_turns(context, session_id))
                if turn.speaker is TurnSpeaker.INTERVIEWER
            ),
            None,
        )
        if latest_question is None or latest_question.turn_id != question_turn_id:
            raise ValueError("automated answer question is no longer current")

        stage = self._question_stage(
            context,
            question_turn_id=question_turn_id,
            fallback=fallback_stage,
        )
        sources = self._question_sources(context, question_turn_id=question_turn_id)
        if not sources:
            retrieval = self._retrieval.retrieve(
                context,
                applicant_id=session.applicant_id,
                invitation_id=session.invitation_id,
                competency_model_version_id=session.competency_model_version_id,
                session_id=session_id,
                query=question.text,
                query_vector=None,
                criterion_id=question.target_criterion_id,
                config_version=retrieval_config_version,
                interview_stage=stage,
            )
            sources = retrieval.hits
        evidence = tuple(source for source in sources if source.excerpt.strip())
        if not evidence:
            return GeneratedAutomatedAnswer(
                text=(
                    "이 질문에 답할 수 있는 구체적인 경험은 제출한 내용만으로 확인하기 "
                    "어렵습니다. 실제 경험을 추가로 설명하기 전에는 임의로 답변하지 않겠습니다."
                ),
                source_reference_count=0,
                grounded=False,
            )

        previous_answers = tuple(
            turn.text or ""
            for turn in self._repository.list_final_turns(context, session_id)
            if turn.speaker is TurnSpeaker.APPLICANT and turn.text
        )[-3:]
        payload = {
            "task": "generate_local_automated_interview_answer",
            "answer_profile": answer_profile.value,
            "question": question.text,
            "interview_stage": stage.value,
            "provided_sources": [
                {
                    "source_id": str(source.source_id),
                    "source_type": source.source_type,
                    "locator": dict(source.locator),
                    "excerpt": source.excerpt,
                }
                for source in evidence
            ],
            "recent_answers_for_repetition_avoidance": list(previous_answers),
            "output_schema": {"answer": "Korean candidate answer"},
        }
        try:
            response = self._model.generate(
                context,
                {
                    "anthropic_version": ANTHROPIC_BEDROCK_VERSION,
                    "system": _SYSTEM_PROMPTS[answer_profile],
                    "max_tokens": 900,
                    "temperature": (
                        0.45 if answer_profile is AutomatedAnswerProfile.ENTRY_LOW else 0.35
                    ),
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
                },
            )
            answer = _answer_text(response)
            if answer_profile is AutomatedAnswerProfile.ENTRY_LOW:
                answer = f"{answer} {_ENTRY_LOW_LIMITATIONS[stage]}"
        except Exception as error:
            raise AutomatedAnswerGenerationUnavailable(
                "automated answer generation is temporarily unavailable"
            ) from error
        if not 10 <= len(answer) <= 4_000:
            raise AutomatedAnswerGenerationUnavailable(
                "automated answer generation returned an invalid answer"
            )
        return GeneratedAutomatedAnswer(
            text=answer,
            source_reference_count=len(evidence),
            grounded=True,
        )

    def _question_stage(
        self,
        context: TenantContext,
        *,
        question_turn_id: UUID,
        fallback: InterviewStage,
    ) -> InterviewStage:
        try:
            rationale = self._repository.get_question_rationale(
                context,
                question_turn_id=question_turn_id,
            )
        except LookupError:
            return fallback
        if rationale is None:
            return fallback
        try:
            return InterviewStage(rationale.interview_stage)
        except ValueError:
            return fallback

    def _question_sources(
        self,
        context: TenantContext,
        *,
        question_turn_id: UUID,
    ) -> tuple[RetrievedContext, ...]:
        references = self._repository.list_question_source_references(
            context,
            question_turn_id=question_turn_id,
        )
        return tuple(_retrieved_source(reference) for reference in references)


def _retrieved_source(reference: QuestionSourceReference) -> RetrievedContext:
    return RetrievedContext(
        source_id=reference.source_id,
        score=reference.relevance_score,
        locator=dict(reference.locator),
        ownership_confidence=reference.ownership_confidence,
        excerpt=reference.excerpt,
        source_type=reference.source_type,
        material_type=None,
    )


def _answer_text(response: Mapping[str, Any]) -> str:
    direct = response.get("answer")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    content = response.get("content")
    if not isinstance(content, list):
        raise ValueError("automated answer response has no answer")
    joined = "".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, Mapping) and block.get("type", "text") == "text"
    ).strip()
    if joined.startswith("```"):
        joined = joined.split("\n", 1)[1] if "\n" in joined else ""
        joined = joined.rsplit("```", 1)[0].strip()
    decoded = json.loads(joined)
    if not isinstance(decoded, Mapping):
        raise ValueError("automated answer response is not an object")
    answer = decoded.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("automated answer response has no answer")
    return answer.strip()
