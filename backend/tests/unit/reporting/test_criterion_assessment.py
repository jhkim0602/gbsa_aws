"""What a reviewer is allowed to be shown as a score.

These tests pin the division of labour the scoring design rests on: the model judges, and
Python refuses to display a judgement it cannot trace to an answer. The cases that matter
are the dishonest ones -- a citation that does not resolve, a zero standing in for "we
never asked", an average dragged down by axes the interview never reached -- because those
are the ways a score misleads someone making a hiring decision.
"""

from typing import Any
from uuid import UUID

import pytest
from interview_evidence.reporting.application.assessment_prompt import (
    ASSESSMENT_AXES,
    AnswerForAssessment,
    build_assessment_prompt,
    parse_assessment_response,
)
from interview_evidence.reporting.application.assessment_service import (
    AssessmentGenerationUnavailable,
    CriterionAssessor,
)
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    AxisAssessment,
    ReportItem,
)
from interview_evidence.shared.interview_level import InterviewLevel
from interview_evidence.shared.operations import InMemoryMetricRecorder
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000002")
EVIDENCE_ID = UUID("00000000-0000-7000-8000-000000000003")
OTHER_EVIDENCE_ID = UUID("00000000-0000-7000-8000-000000000004")
REPORT_ITEM_ID = UUID("00000000-0000-7000-8000-000000000005")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000006")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000007")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000008"),
        request_id=UUID("00000000-0000-7000-8000-000000000009"),
        trace_id="trace-criterion-assessment",
    )


def answer() -> AnswerForAssessment:
    return AnswerForAssessment(
        evidence_id=EVIDENCE_ID,
        question="큐를 고른 이유가 무엇인가요?",
        answer_text="재시도 폭주를 막으려고 큐를 골랐고, 캐시는 정합성 때문에 버렸습니다.",
        video_start_ms=1000,
        video_end_ms=4000,
    )


class StubModel:
    """A model that answers with whatever verdict a test hands it."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.prompts: list[dict[str, Any]] = []

    def generate(
        self,
        _context: TenantContext,
        model_input: dict[str, Any],
    ) -> dict[str, Any]:
        self.prompts.append(dict(model_input))
        return self.response


class FailingModel:
    def generate(self, _context: TenantContext, _model_input: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("bedrock is unavailable")


class QuotaExhaustedModel:
    def generate(self, _context: TenantContext, _model_input: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("vertex quota is exhausted")


def verdict(**overrides: Any) -> dict[str, Any]:
    body = {
        "criterion_id": str(CRITERION_ID),
        "assessment_state": "confirmed",
        "axis_scores": [
            {
                "axis": "correctness",
                "score": 78,
                "rationale": "재시도 폭주와 정합성을 원인으로 정확히 짚었습니다.",
                "quoted_evidence_ids": [str(EVIDENCE_ID)],
            },
            {
                "axis": "depth",
                "score": 64,
                "rationale": "대안을 버린 이유까지 말했지만 측정 근거는 없었습니다.",
                "quoted_evidence_ids": [str(EVIDENCE_ID)],
            },
        ],
        "summary": "큐 선택의 이유와 버린 대안을 답변에서 확인했습니다.",
        "follow_up_question": "큐 지연을 어떻게 측정했는지 확인해 주세요.",
    }
    body.update(overrides)
    return body


def assess(response: dict[str, Any]) -> Any:
    return CriterionAssessor(StubModel(response)).assess(
        context(),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교하고 선택 근거를 설명할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v1",
    )


def test_the_model_supplies_the_score_and_the_rationale_travels_with_it() -> None:
    assessment = assess(verdict())
    assert assessment is not None
    scores = {axis.axis: axis for axis in assessment.axis_assessments}
    assert scores["correctness"].score == 78
    assert scores["depth"].score == 64
    # The label is snapshotted so an old report keeps its wording, and the rationale is
    # what lets a reviewer overrule the number.
    assert scores["correctness"].label == "정확성"
    assert "재시도 폭주" in scores["correctness"].rationale
    assert scores["correctness"].quoted_evidence_ids == (EVIDENCE_ID,)


def test_a_score_citing_evidence_that_does_not_exist_is_withheld() -> None:
    body = verdict()
    body["axis_scores"][0]["quoted_evidence_ids"] = [str(OTHER_EVIDENCE_ID)]

    assessment = assess(body)

    assert assessment is not None
    scores = {axis.axis: axis for axis in assessment.axis_assessments}
    # The number is gone, and the reviewer is told why rather than being shown reasoning
    # that nothing supports.
    assert scores["correctness"].score is None
    assert scores["correctness"].quoted_evidence_ids == ()
    assert "확인할 수 없어" in scores["correctness"].rationale
    # The axis that cited a real answer is untouched: one bad citation does not void the
    # whole assessment.
    assert scores["depth"].score == 64


def test_citation_verification_records_accepted_and_withheld_axis_counts() -> None:
    body = verdict()
    body["axis_scores"][0]["quoted_evidence_ids"] = [str(OTHER_EVIDENCE_ID)]
    metrics = InMemoryMetricRecorder()

    CriterionAssessor(StubModel(body), metrics=metrics).assess(
        context(),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v1",
    )

    axis_counts = {
        record.dimensions["outcome"]: record.value
        for record in metrics.records
        if record.name == "ai_assessment_axis_count"
    }
    assert axis_counts == {"evidence_verified": 1, "citation_withheld": 1}


def test_an_axis_with_nothing_to_cite_scores_null_not_zero() -> None:
    body = verdict()
    body["axis_scores"].append(
        {
            "axis": "fundamentals",
            "score": None,
            "rationale": "CS 기본기를 확인할 질문이 없었습니다.",
            "quoted_evidence_ids": [],
        }
    )

    assessment = assess(body)

    assert assessment is not None
    scores = {axis.axis: axis for axis in assessment.axis_assessments}
    assert scores["fundamentals"].score is None
    assert scores["fundamentals"].rationale == "CS 기본기를 확인할 질문이 없었습니다."
    assert scores["fundamentals"].quoted_evidence_ids == ()


def test_the_average_ignores_unjudged_axes_instead_of_counting_them_as_zero() -> None:
    item = ReportItem(
        report_item_id=REPORT_ITEM_ID,
        company_id=COMPANY_ID,
        report_id=REPORT_ID,
        criterion_id=CRITERION_ID,
        competency_model_version_id=VERSION_ID,
        assessment_state=AssessmentState.NEEDS_FOLLOW_UP,
        observation="관찰",
        rationale="판단",
        sufficiency="partial",
        uncertainty="중간",
        evidence=(),
        axis_assessments=(
            AxisAssessment(
                axis="correctness",
                label="정확성",
                score=80,
                rationale="정확했습니다.",
                quoted_evidence_ids=(EVIDENCE_ID,),
            ),
            AxisAssessment(
                axis="fundamentals",
                label="CS 기본기",
                score=None,
                rationale="확인할 답변이 없었습니다.",
            ),
        ),
    )

    # Counting the unjudged axis as zero would report 40 -- a failure for a question we
    # never asked.
    assert item.average_score == 80


def test_a_model_outage_costs_the_scores_but_not_the_report() -> None:
    assessment = CriterionAssessor(FailingModel()).assess(
        context(),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v1",
    )

    # None means "no judgement", which the caller renders as an item without scores. A
    # raise here would lose the reviewer the Evidence trail they cannot reconstruct.
    assert assessment is None


def test_a_gcp_quota_error_costs_the_scores_but_not_the_report() -> None:
    assessment = CriterionAssessor(QuotaExhaustedModel()).assess(
        context(),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v1",
    )

    assert assessment is None


def test_the_production_report_worker_retries_when_required_scores_are_unavailable() -> None:
    with pytest.raises(AssessmentGenerationUnavailable):
        CriterionAssessor(QuotaExhaustedModel(), require_scores=True).assess(
            context(),
            criterion_id=CRITERION_ID,
            criterion_name="장애 대응 판단",
            criterion_text="장애 상황에서 대안을 비교할 수 있다.",
            answers=(answer(),),
            model_config_version="report-config-v1",
        )


def test_an_unrecognized_assessment_state_asks_for_a_human_rather_than_confirming() -> None:
    assessment = assess(verdict(assessment_state="looks_great"))

    assert assessment is not None
    assert assessment.assessment_state.value == "needs_follow_up"


def test_no_retrieval_signal_reaches_the_scoring_prompt() -> None:
    model = StubModel(verdict())
    CriterionAssessor(model).assess(
        context(),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v1",
    )

    rendered = str(model.prompts[0])
    # The constitution admits these as retrieval metadata only. A score that saw them
    # would be rating how much the candidate submitted, not what they demonstrated.
    for banned in ("similarity", "relevance_score", "commit_count", "source_count"):
        assert banned not in rendered


def test_the_interview_level_changes_the_bar_the_same_answer_is_held_to() -> None:
    entry = build_assessment_prompt(
        CriterionAssessor(StubModel(verdict())).prompt_for(InterviewLevel.ENTRY),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v1",
    )
    senior = build_assessment_prompt(
        CriterionAssessor(StubModel(verdict())).prompt_for(InterviewLevel.SENIOR),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v1",
    )

    assert entry["system"] != senior["system"]
    assert "신입" in entry["system"]
    assert "트레이드오프" in senior["system"]


def test_every_axis_the_prompt_offers_is_one_the_parser_will_accept() -> None:
    body = verdict()
    body["axis_scores"] = [
        {
            "axis": axis.key,
            "score": 70,
            "rationale": f"{axis.label} 근거",
            "quoted_evidence_ids": [str(EVIDENCE_ID)],
        }
        for axis in ASSESSMENT_AXES
    ]

    parsed = parse_assessment_response(body)

    # A prompt that advertises an axis the parser rejects would drop that score silently.
    assert len(parsed.axis_scores) == len(ASSESSMENT_AXES)


def test_communication_is_scored_as_delivery_not_answer_length() -> None:
    prompt = build_assessment_prompt(
        CriterionAssessor(StubModel(verdict())).prompt_for(InterviewLevel.JUNIOR),
        criterion_id=CRITERION_ID,
        criterion_name="장애 대응 판단",
        criterion_text="장애 상황에서 대안을 비교할 수 있다.",
        answers=(answer(),),
        model_config_version="report-config-v2",
    )

    system = str(prompt["system"])
    assert "짧아도 질문에 직접 답하고 근거가 명확하면" in system
    assert "긴장·말더듬·일시적인 침묵 자체는 감점하지 않습니다" in system
    assert "communication 점수를 기술 정확성" in system
