"""The prompt layer for scoring one criterion against the answers that were given.

Before this module a report item's assessment was decided by ``ReportGenerator`` in
Python: an Evidence interval that survived validation became ``confirmed``, one that did
not became ``insufficient_evidence``, and there was no score at all. That is a check on
whether a video range exists, not a judgement about whether the candidate demonstrated
the criterion -- an answer can be perfectly recorded and still be wrong, and a shaky
recording can hold an excellent answer.

So the judgement moves to the model and the arithmetic disappears. The prompt receives
the criterion being tested, the evaluation axes, and the applicant's actual answers with
their transcript intervals; the model returns a score per axis with the quote it relied
on. Python's remaining job is the part a model cannot be trusted with: proving that every
quote the model cited traces back to a real Evidence interval, and refusing the score if
it does not. That division is what ``AssessmentVerdict`` and its verification enforce.

The constitution permits this and constrains it. Assessments MUST trace to an actual
answer, transcript interval and criterion version, which is why a verdict names its
Evidence. Retrieval signals -- similarity, keyword rank, repository activity, document
count -- MUST NOT become competency scores, so none of them are in the payload. And no AI
output may set a final hiring decision, which is why there is no overall pass/fail here:
the axes are reported per criterion and the decision stays with a person.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)

TASK_ASSESS_CRITERION: Final = "assess_interview_criterion"

#: Bedrock requires this literal on every Anthropic Messages request.
ANTHROPIC_BEDROCK_VERSION: Final = "bedrock-2023-05-31"

#: The lowest score that still counts as demonstrating a criterion. Below this the
#: reviewer is being told to look, not that the candidate failed.
PASSING_BAND: Final = 60


class AssessmentAxis(BaseModel):
    """One dimension a technical answer is judged on.

    The axes are fixed rather than per-company because they describe how engineering
    answers are read, not what a company values -- which criterion gets asked is where
    the company's judgement lives. Each axis carries the prose the model is given, since
    what separates a 40 from an 80 on "깊이" cannot be said with a number.
    """

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=40)
    guidance: str = Field(min_length=1, max_length=1_200)


ASSESSMENT_AXES: Final[tuple[AssessmentAxis, ...]] = (
    AssessmentAxis(
        key="correctness",
        label="정확성",
        guidance=(
            "답변의 기술적 사실이 맞는지 봅니다. 용어를 정확히 쓰는지, 인과를 뒤집어 "
            "말하지 않는지, 근거 없이 단정하지 않는지 확인합니다. 틀린 내용을 자신 있게 "
            "말하는 것은 모른다고 말하는 것보다 낮게 봅니다."
        ),
    ),
    AssessmentAxis(
        key="depth",
        label="깊이",
        guidance=(
            "'무엇을 했다'에서 멈추는지, '왜 그렇게 했고 대안은 무엇이었는지'까지 "
            "내려가는지 봅니다. 한 겹 더 물었을 때 설명이 이어지면 높게, 표면 용어만 "
            "반복하면 낮게 봅니다. 암기한 정의를 그대로 읊는 것은 깊이가 아닙니다."
        ),
    ),
    AssessmentAxis(
        key="fundamentals",
        label="CS 기본기",
        guidance=(
            "자료구조·알고리즘·네트워크·운영체제·데이터베이스·동시성 같은 기반 지식이 "
            "답변에 실제로 쓰이는지 봅니다. 지원자가 먼저 꺼낸 개념만 평가하고, 면접에서 "
            "다루지 않은 주제를 몰랐다고 감점하지 않습니다."
        ),
    ),
    AssessmentAxis(
        key="ownership",
        label="본인 기여",
        guidance=(
            "본인이 한 일과 팀이 한 일을 구분해 말하는지 봅니다. 'we'로 뭉개지 않고 "
            "자기 판단과 실수를 말할 수 있으면 높게 봅니다. 기여를 부풀린 흔적이 보이면 "
            "낮게 보고 그 대목을 근거로 인용합니다."
        ),
    ),
    AssessmentAxis(
        key="communication",
        label="설명력",
        guidance=(
            "듣는 사람이 따라올 수 있게 설명하는지 봅니다. 순서가 있는지, 모르는 것을 "
            "모른다고 말하는지, 질문의 요지를 놓치지 않는지 확인합니다. 유창함이 아니라 "
            "전달이 되는지를 봅니다."
        ),
    ),
)

#: Shape the model must return. Kept beside the prompt so the two cannot drift.
OUTPUT_SCHEMA: Final[Mapping[str, Any]] = {
    "criterion_id": "uuid, must equal the requested criterion",
    "assessment_state": (
        "one of confirmed | partially_confirmed | insufficient_evidence | needs_follow_up"
    ),
    "axis_scores": [
        {
            "axis": "one of the provided axis keys",
            "score": "integer 0-100, or null when the answers do not let you judge this axis",
            "rationale": "string, Korean, why this score and not ten points either side",
            "quoted_evidence_ids": ["evidence_id of each answer this score rests on"],
        }
    ],
    "summary": "string, Korean, two or three sentences a reviewer reads first",
    "follow_up_question": "string or null, what a human interviewer should ask next",
}

_SYSTEM_PROMPT: Final = """\
당신은 기술 면접을 심사하는 시니어 엔지니어입니다. 지원자가 실제로 한 답변만 읽고, 하나의
평가 기준에 대해 축별 점수와 그 근거를 매깁니다.

당신의 점수는 최종 합격 여부가 아닙니다. 채용 담당자가 당신의 판단 근거를 읽고 스스로
평가하기 위한 자료입니다. 그래서 점수보다 근거가 중요합니다.

반드시 지켜야 할 규칙:
1. provided_answers에 실제로 있는 말만 근거로 씁니다. 지원자가 하지 않은 말을 요약하거나
   추측해서 채우지 않습니다.
2. 모든 점수에는 그 점수의 근거가 된 답변의 evidence_id를 quoted_evidence_ids에 담습니다.
   인용할 답변이 없는 축은 점수를 null로 두고 그 이유를 rationale에 적습니다.
3. 답변에서 다루지 않은 주제를 몰랐다고 감점하지 않습니다. 묻지 않은 것은 평가하지 않습니다.
4. 점수는 {passing_band}점을 기준선으로 씁니다. {passing_band}점 이상은 해당 축을 보여줬다는
   뜻이고, 그 아래는 담당자가 직접 확인해 봐야 한다는 뜻입니다. 0점은 "답변이 틀렸다"는
   뜻이며, "판단할 답변이 없다"는 뜻으로 쓰지 않습니다. 후자는 null입니다.
5. rationale은 왜 그 점수인지, 왜 10점 위나 아래가 아닌지가 드러나게 씁니다.
   "좋았습니다" 같은 문장은 쓰지 않습니다.
6. 제출 자료의 분량, 커밋 수, 검색 유사도 같은 것은 평가에 쓰지 않습니다. 면접에서 한 답변만
   봅니다.
7. assessment_state는 근거의 상태를 말합니다. 인용할 답변이 충분하면 confirmed,
   일부만 확인되면 partially_confirmed, 사람이 더 물어야 하면 needs_follow_up,
   판단할 답변 자체가 없으면 insufficient_evidence입니다.
8. 개인 신상, 가족, 종교, 정치, 출신 지역, 나이, 성별은 평가에 반영하지 않습니다.

평가 기준선:
{depth_guidance}

평가 축:
{axis_guidance}

설명이나 머리말 없이 다음 JSON 객체 하나만 출력합니다:
{output_schema}"""

_PERSONA: Final = (
    "정확하고 인용에 엄격한 시니어 엔지니어 심사자입니다. 지원자를 깎아내리지도 "
    "부풀리지도 않고, 답변에 실제로 있는 내용만 근거로 점수를 매깁니다."
)

#: What the 신입/주니어/시니어 toggle changes about a score. The same answer is not worth
#: the same at every level: a first-job candidate explaining why they picked a data
#: structure is doing well, while a senior saying only that much has not shown much.
_DEPTH_GUIDANCE: Final[Mapping[InterviewLevel, str]] = {
    InterviewLevel.ENTRY: (
        "- 실무 경력이 없는 신입입니다. 학습한 것을 자기 말로 설명하고 직접 해 본 시도를 "
        "말하면 기준선을 넘긴 것으로 봅니다.\n"
        "- 대규모 운영 경험, 조직 설계, 장기 비용 판단이 없다고 감점하지 않습니다. "
        "겪을 수 없는 일입니다.\n"
        "- 모르는 것을 모른다고 말하고 어떻게 알아볼지 말하면 정확성에서 높게 봅니다."
    ),
    InterviewLevel.JUNIOR: (
        "- 1~3년 경력입니다. 본인이 내린 판단과 그 근거를 말할 수 있으면 기준선을 넘깁니다.\n"
        "- 선택한 방법의 대안을 언급하고 왜 그것을 고르지 않았는지 말하면 깊이에서 높게 봅니다.\n"
        "- 팀 성과와 본인 기여가 섞여 있으면 본인 기여 축을 낮게 보고 그 대목을 인용합니다."
    ),
    InterviewLevel.SENIOR: (
        "- 시니어입니다. 결과를 말하는 것만으로는 기준선을 넘기지 못합니다. 트레이드오프와 "
        "실패 대비가 답변에 있어야 합니다.\n"
        "- 무엇을 포기했고 그 대가를 어떻게 감당했는지 말하면 깊이에서 높게 봅니다.\n"
        "- 용어 정의를 정확히 말하는 것은 기본으로 보고, 그것만으로 CS 기본기를 높게 주지 "
        "않습니다.\n"
        "- 측정 방법과 근거의 한계를 스스로 말하면 정확성에서 높게 봅니다."
    ),
}


class AxisScore(BaseModel):
    """One axis's score with the answers it was drawn from."""

    model_config = ConfigDict(frozen=True)

    axis: str = Field(min_length=1, max_length=40)
    #: None means the answers gave no basis to judge this axis -- never a zero, because
    #: zero says the candidate was wrong and would reject people for questions we
    #: never asked.
    score: int | None = Field(default=None, ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=2_000)
    quoted_evidence_ids: tuple[UUID, ...] = ()

    @field_validator("axis")
    @classmethod
    def _known_axis(cls, value: str) -> str:
        if value not in {axis.key for axis in ASSESSMENT_AXES}:
            raise ValueError(f"unknown assessment axis: {value}")
        return value


class AssessmentVerdict(BaseModel):
    """A model's judgement on one criterion, before it is trusted.

    Parsing this proves the response is shaped correctly. It does not prove the model
    quoted real answers, which is what ``verified_against`` is for: a score whose
    citations do not resolve is discarded rather than shown to a reviewer, because a
    reviewer cannot overrule reasoning they are unable to check.
    """

    model_config = ConfigDict(frozen=True)

    criterion_id: UUID
    assessment_state: str = Field(min_length=1, max_length=40)
    axis_scores: tuple[AxisScore, ...] = ()
    summary: str = Field(min_length=1, max_length=4_000)
    follow_up_question: str | None = Field(default=None, max_length=1_000)

    def verified_against(self, available_evidence_ids: frozenset[UUID]) -> AssessmentVerdict:
        """Drop every score whose cited answers are not real Evidence.

        A model that cites an evidence_id it was never given has either lost track of the
        payload or invented the support for its number. Either way the score cannot be
        traced to an answer, which the constitution requires of any assessment, so it is
        emptied out with the reason left in place rather than quietly kept.
        """
        return self.model_copy(
            update={
                "axis_scores": tuple(
                    score
                    if score.quoted_evidence_ids
                    and available_evidence_ids.issuperset(score.quoted_evidence_ids)
                    else score.model_copy(
                        update={
                            "score": None,
                            "quoted_evidence_ids": (),
                            "rationale": _UNVERIFIED_RATIONALE,
                        }
                    )
                    for score in self.axis_scores
                )
            }
        )

    @property
    def assessable_axes(self) -> tuple[AxisScore, ...]:
        return tuple(score for score in self.axis_scores if score.score is not None)


#: Replaces a rationale whose citations did not resolve, so the reviewer is told the
#: score was withheld rather than shown reasoning nothing supports.
_UNVERIFIED_RATIONALE: Final = "인용한 답변을 확인할 수 없어 점수를 보류했습니다."


class AssessmentPromptTemplate(BaseModel):
    """Every knob that changes a score, versioned as one unit."""

    model_config = ConfigDict(frozen=True)

    prompt_version: str = Field(min_length=1, max_length=60)
    interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL
    persona: str = Field(min_length=1, max_length=1_000)
    system_prompt: str = Field(min_length=1, max_length=12_000)
    depth_guidance: str = Field(min_length=1, max_length=2_000)
    axes: tuple[AssessmentAxis, ...] = ASSESSMENT_AXES
    max_tokens: int = Field(ge=256, le=8_192)
    temperature: float = Field(ge=0.0, le=1.0)
    passing_band: int = Field(default=PASSING_BAND, ge=1, le=99)

    def rendered_system_prompt(self) -> str:
        return "\n\n".join(
            (
                self.persona,
                self.system_prompt.format(
                    passing_band=self.passing_band,
                    depth_guidance=self.depth_guidance,
                    axis_guidance="\n".join(
                        f"- {axis.key} ({axis.label}): {axis.guidance}" for axis in self.axes
                    ),
                    output_schema=json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
                ),
            )
        )


def _template_for(level: InterviewLevel) -> AssessmentPromptTemplate:
    return AssessmentPromptTemplate(
        prompt_version=f"assessment-prompt-v1-{level.value}",
        interview_level=level,
        persona=_PERSONA,
        system_prompt=_SYSTEM_PROMPT,
        depth_guidance=_DEPTH_GUIDANCE[level],
        # Room for five axes of real reasoning. Truncated rationale is worse than none:
        # the reviewer sees a number whose justification stops mid-sentence.
        max_tokens=2_048,
        # Lower than question generation. A question may vary between runs, but two
        # reviewers reading the same interview should not see materially different
        # scores, so this stays near-deterministic.
        temperature=0.1,
    )


ASSESSMENT_PROMPTS: Final[Mapping[InterviewLevel, AssessmentPromptTemplate]] = {
    level: _template_for(level) for level in InterviewLevel
}

DEFAULT_ASSESSMENT_PROMPT: Final = ASSESSMENT_PROMPTS[DEFAULT_INTERVIEW_LEVEL]


def assessment_prompt_for(level: InterviewLevel) -> AssessmentPromptTemplate:
    """The template a given interview level is scored with."""
    return ASSESSMENT_PROMPTS[level]


class AnswerForAssessment(BaseModel):
    """One applicant answer, addressed by the Evidence the model must cite.

    The ``evidence_id`` is what makes a score checkable: the model quotes it, and Python
    resolves it back to a transcript segment and video interval a reviewer can play.
    """

    model_config = ConfigDict(frozen=True)

    evidence_id: UUID
    question: str = Field(max_length=2_000)
    answer_text: str = Field(min_length=1, max_length=20_000)
    video_start_ms: int = Field(ge=0)
    video_end_ms: int = Field(gt=0)


def build_assessment_prompt(
    template: AssessmentPromptTemplate,
    *,
    criterion_id: UUID,
    criterion_name: str,
    criterion_text: str,
    answers: Sequence[AnswerForAssessment],
    model_config_version: str,
) -> dict[str, Any]:
    """Render an Anthropic Messages body for scoring one criterion.

    Only the criterion and the answers travel. There is deliberately no place in this
    payload for a document count, a similarity figure or a repository statistic: the
    constitution admits those as retrieval metadata only, and a score that saw them would
    be rating how much a candidate submitted rather than what they demonstrated.
    """
    task_payload = {
        "task": TASK_ASSESS_CRITERION,
        "criterion": {
            "criterion_id": str(criterion_id),
            "name": criterion_name,
            "text": criterion_text,
        },
        "axes": [
            {"key": axis.key, "label": axis.label, "guidance": axis.guidance}
            for axis in template.axes
        ],
        "provided_answers": [
            {
                "evidence_id": str(answer.evidence_id),
                "question": answer.question,
                "answer_text": answer.answer_text,
                "video_start_ms": answer.video_start_ms,
                "video_end_ms": answer.video_end_ms,
            }
            for answer in answers
        ],
        "output_schema": dict(OUTPUT_SCHEMA),
        "model_config_version": model_config_version,
        "prompt_version": template.prompt_version,
        "interview_level": template.interview_level.value,
    }
    return {
        "anthropic_version": ANTHROPIC_BEDROCK_VERSION,
        "system": template.rendered_system_prompt(),
        "max_tokens": template.max_tokens,
        "temperature": template.temperature,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": json.dumps(task_payload, ensure_ascii=False)}],
            }
        ],
    }


def parse_assessment_response(response: Mapping[str, Any]) -> AssessmentVerdict:
    """Read a verdict out of a model response.

    Anthropic returns the answer as text blocks, so the JSON the prompt asked for arrives
    as a string that still has to be decoded. A response already carrying the flat fields
    is passed through, which is what the deterministic local model returns.
    """
    if "axis_scores" in response:
        return AssessmentVerdict.model_validate(response)
    content = response.get("content")
    if not isinstance(content, list):
        raise ValueError("model response has neither axis scores nor content blocks")
    joined = "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, Mapping) and block.get("type", "text") == "text"
    ).strip()
    decoded = json.loads(_unwrapped(joined))
    if not isinstance(decoded, Mapping):
        raise ValueError("model response body is not a JSON object")
    return AssessmentVerdict.model_validate(decoded)


def _unwrapped(text: str) -> str:
    """Strip a ```json fence, which models emit even when told not to."""
    if not text.startswith("```"):
        return text
    without_open = text.split("\n", 1)[1] if "\n" in text else ""
    return without_open.rsplit("```", 1)[0].strip()
