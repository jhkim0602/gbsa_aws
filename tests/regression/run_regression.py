from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from interview_evidence.interview_engine.adapters.polly import SpeechSynthesisAdapter
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.application.question_generator import (
    QuestionGenerationUnavailable,
    QuestionGenerator,
)
from interview_evidence.interview_engine.application.question_policy import (
    QuestionDraft,
    QuestionPolicy,
)
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    Evidence,
    ReportItem,
    Sufficiency,
)
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    InMemorySearchIndex,
    SearchDocument,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)

ROOT = Path(__file__).resolve().parent
RETRIEVAL_THRESHOLD = 0.95
QUESTION_THRESHOLD = 1.0
EVIDENCE_THRESHOLD = 1.0


def _cases(name: str) -> list[dict[str, Any]]:
    path = ROOT / name / "cases.jsonl"
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _context(company_id: UUID, applicant_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.APPLICANT,
        actor_id=applicant_id,
        request_id=new_uuid7(),
        trace_id="fixed-regression",
    )


def _run_retrieval() -> tuple[dict[str, object], list[str]]:
    cases = _cases("retrieval")
    recalls: list[float] = []
    failed: list[str] = []
    versions = {str(case["config_version"]) for case in cases}
    for case in cases:
        company_id = UUID(case["company_id"])
        applicant_id = UUID(case["applicant_id"])
        index = InMemorySearchIndex()
        for raw in case["documents"]:
            index.add(
                SearchDocument(
                    document_id=raw["document_id"],
                    company_id=UUID(raw["company_id"]),
                    applicant_id=UUID(raw["applicant_id"]),
                    source_id=UUID(raw["source_id"]),
                    text=raw["text"],
                    vector=tuple(float(value) for value in raw["vector"]),
                    symbols=tuple(raw["symbols"]),
                    locator=dict(raw["locator"]),
                    ownership_confidence=float(raw["ownership_confidence"]),
                )
            )
        results = HybridRetriever(index, HybridRetrievalConfig()).retrieve(
            _context(company_id, applicant_id),
            applicant_id=applicant_id,
            query=case["query"],
            query_vector=tuple(float(value) for value in case["query_vector"]),
            exact_symbol=case["exact_symbol"],
            limit=int(case["limit"]),
        )
        actual = [str(result.source_id) for result in results]
        expected = set(case["expected_top_source_ids"])
        recall = len(expected & set(actual[: len(expected)])) / len(expected)
        recalls.append(recall)
        forbidden = set(case.get("forbidden_source_ids", ()))
        ownership_limit = case.get("expected_max_ownership_confidence")
        ownership_ok = ownership_limit is None or (
            bool(results) and results[0].ownership_confidence <= float(ownership_limit)
        )
        if (
            recall < float(case["min_recall_at_k"])
            or forbidden.intersection(actual)
            or not ownership_ok
        ):
            failed.append(str(case["case_id"]))
    recall_at_k = sum(recalls) / len(recalls)
    return (
        {
            "cases": len(cases),
            "config_versions": sorted(versions),
            "recall_at_k": recall_at_k,
            "threshold": RETRIEVAL_THRESHOLD,
            "passed": recall_at_k >= RETRIEVAL_THRESHOLD,
        },
        failed,
    )


class _FailingRetrieval:
    def retrieve_context(self, *_args: object, **_kwargs: object) -> tuple[object, ...]:
        raise RuntimeError("search unavailable")


class _FailingModel:
    def generate(
        self,
        _context: TenantContext,
        _model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        raise RuntimeError("model unavailable")


class _FailingSpeech:
    def synthesize(
        self,
        _context: TenantContext,
        _text: str,
        *,
        voice_id: str,
    ) -> Mapping[str, Any]:
        del voice_id
        raise RuntimeError("speech unavailable")


def _degraded_result(case: dict[str, Any]) -> tuple[str, bool]:
    context = _context(
        UUID("00000000-0000-7000-8000-000000000001"),
        UUID("00000000-0000-7000-8000-000000000002"),
    )
    failure = case["failure"]
    if failure == "retrieval":
        outcome = RetrievalClient(_FailingRetrieval()).retrieve(
            context,
            applicant_id=context.actor_id,
            session_id=UUID("00000000-0000-7000-8000-000000000203"),
            query="장애 대응",
            query_vector=(1.0, 0.0),
            criterion_id=UUID("00000000-0000-7000-8000-000000000201"),
            config_version=str(case["config_version"]),
        )
        return outcome.degraded_mode or "", True
    if failure == "model":
        try:
            QuestionGenerator(_FailingModel()).generate(
                context,
                target_criterion_id=UUID("00000000-0000-7000-8000-000000000201"),
                context_payload={"remaining_time_seconds": 300},
                model_config_version=str(case["config_version"]),
                retrieval_config_version="hybrid-v1",
            )
        except QuestionGenerationUnavailable as error:
            return "question_generation", error.retryable
        return "", False
    if failure == "speech":
        output = SpeechSynthesisAdapter(_FailingSpeech()).synthesize(
            context,
            text="문제를 해결한 과정을 설명해 주세요?",
            voice_id="Seoyeon",
        )
        return output.degraded_mode or "", False
    raise ValueError("unsupported degraded regression case")


def _run_questions() -> tuple[dict[str, object], list[str]]:
    cases = _cases("questions")
    passed = 0
    failed: list[str] = []
    versions = {str(case["config_version"]) for case in cases}
    for case in cases:
        if case["case_type"] == "policy":
            criterion_id = UUID(case["criterion_id"])
            result = QuestionPolicy().evaluate(
                QuestionDraft(
                    text=case["text"],
                    target_criterion_id=criterion_id,
                    source_reference_ids=(),
                    model_config_version=str(case["config_version"]),
                    retrieval_config_version="hybrid-v1",
                ),
                allowed_criterion_ids=frozenset(
                    UUID(value) for value in case["allowed_criterion_ids"]
                ),
                prohibited_topics=tuple(case["prohibited_topics"]),
                previous_questions=tuple(case["previous_questions"]),
                fallback_question=case["fallback_question"],
                fallback_criterion_id=next(UUID(value) for value in case["allowed_criterion_ids"]),
            )
            case_passed = result.accepted is bool(case["expected_accepted"]) and set(
                result.reason_codes
            ) == set(case["expected_reason_codes"])
        else:
            mode, retryable = _degraded_result(case)
            case_passed = mode == case["expected_mode"] and retryable is bool(
                case["expected_retryable"]
            )
        if case_passed:
            passed += 1
        else:
            failed.append(str(case["case_id"]))
    pass_rate = passed / len(cases)
    return (
        {
            "cases": len(cases),
            "config_versions": sorted(versions),
            "pass_rate": pass_rate,
            "threshold": QUESTION_THRESHOLD,
            "passed": pass_rate >= QUESTION_THRESHOLD,
        },
        failed,
    )


def _run_evidence_case(case: dict[str, Any]) -> bool:
    company_id = UUID("00000000-0000-7000-8000-000000000001")
    report_item_id = UUID("00000000-0000-7000-8000-000000000302")
    criterion_id = UUID("00000000-0000-7000-8000-000000000303")
    version_id = UUID("00000000-0000-7000-8000-000000000304")
    answer_turn_id = UUID("00000000-0000-7000-8000-000000000305")
    referenced_turn_id = (
        answer_turn_id
        if case["answer_turn_matches"]
        else UUID("00000000-0000-7000-8000-000000000399")
    )
    if case["source_kind"] == "source_reference":
        Evidence.from_source_reference(source_id=referenced_turn_id)

    evidence_items: tuple[Evidence, ...] = ()
    if case["has_evidence"]:
        candidate = Evidence(
            evidence_id=UUID("00000000-0000-7000-8000-000000000307"),
            company_id=company_id,
            report_item_id=report_item_id,
            criterion_id=criterion_id,
            competency_model_version_id=version_id,
            answer_turn_id=referenced_turn_id,
            transcript_segment_id=UUID("00000000-0000-7000-8000-000000000306"),
            video_start_ms=int(case["video_start_ms"]),
            video_end_ms=int(case["video_end_ms"]),
            observation="지원자의 최종 답변에서 확인된 사실",
            rationale="평가 기준과 직접 연결되는 최종 답변",
            sufficiency=Sufficiency.DIRECT,
            generation_version=str(case["config_version"]),
            created_at=datetime.now(UTC),
        )
        candidate.validate_timeline(
            answer_turn_id=answer_turn_id,
            transcript_start_ms=int(case["transcript_start_ms"]),
            transcript_end_ms=int(case["transcript_end_ms"]),
            missing_ranges=tuple(
                (int(value[0]), int(value[1])) for value in case["missing_ranges"]
            ),
            technical_failure_ranges=tuple(
                (int(value[0]), int(value[1])) for value in case["technical_failure_ranges"]
            ),
        )
        evidence_items = (candidate,)
    ReportItem(
        report_item_id=report_item_id,
        company_id=company_id,
        report_id=UUID("00000000-0000-7000-8000-000000000308"),
        criterion_id=criterion_id,
        competency_model_version_id=version_id,
        assessment_state=AssessmentState(case["assessment_state"]),
        observation="관찰",
        rationale="판단",
        sufficiency="direct" if evidence_items else "none",
        uncertainty="낮음" if evidence_items else "높음",
        evidence=evidence_items,
    )
    return True


def _run_evidence() -> tuple[dict[str, object], list[str]]:
    cases = _cases("evidence")
    passed = 0
    failed: list[str] = []
    versions = {str(case["config_version"]) for case in cases}
    for case in cases:
        try:
            actual_valid = _run_evidence_case(case)
        except (TypeError, ValueError):
            actual_valid = False
        if actual_valid is bool(case["expected_valid"]):
            passed += 1
        else:
            failed.append(str(case["case_id"]))
    pass_rate = passed / len(cases)
    return (
        {
            "cases": len(cases),
            "config_versions": sorted(versions),
            "pass_rate": pass_rate,
            "threshold": EVIDENCE_THRESHOLD,
            "passed": pass_rate >= EVIDENCE_THRESHOLD,
        },
        failed,
    )


def run_all() -> dict[str, Any]:
    retrieval, retrieval_failed = _run_retrieval()
    questions, question_failed = _run_questions()
    evidence, evidence_failed = _run_evidence()
    failed = [*retrieval_failed, *question_failed, *evidence_failed]
    return {
        "passed": (
            bool(retrieval["passed"])
            and bool(questions["passed"])
            and bool(evidence["passed"])
            and not failed
        ),
        "retrieval": retrieval,
        "questions": questions,
        "evidence": evidence,
        "failed_cases": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixed AI regression corpora.")
    parser.add_argument("--json", action="store_true", help="Emit a JSON report.")
    arguments = parser.parse_args()
    report = run_all()
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("AI regression passed." if report["passed"] else "AI regression failed.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
