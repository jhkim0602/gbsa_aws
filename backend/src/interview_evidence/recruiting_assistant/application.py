from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError

from interview_evidence.recruiting_assistant.domain import (
    AssistantSearchDocument,
    AssistantSearchResult,
)
from interview_evidence.recruiting_assistant.prompt import (
    build_answer_prompt,
    parse_answer_response,
)
from interview_evidence.recruiting_assistant.repository import (
    AssistantDocumentRepository,
)
from interview_evidence.reporting.domain.report import (
    Report,
    ReportItem,
    RequirementAssessment,
    RequirementAssessmentStatus,
)
from interview_evidence.shared.aws_clients.ports import AIModel, TextEmbedder
from interview_evidence.shared.tenant import TenantContext

ASSISTANT_PROJECTION_VERSION = "requirements-v2"


class ReportSearchProjector:
    """Build the recruiter-safe search projection from an immutable final report."""

    def __init__(
        self,
        repository: AssistantDocumentRepository,
        embedder: TextEmbedder,
    ) -> None:
        self._repository = repository
        self._embedder = embedder

    def project(
        self,
        context: TenantContext,
        *,
        position_id: UUID,
        position_title: str,
        applicant_id: UUID,
        applicant_display_name: str,
        report: Report,
    ) -> tuple[AssistantSearchDocument, ...]:
        context.assert_company(report.company_id)
        evidence_documents = (
            tuple(
                self._requirement_document(
                    context,
                    position_id=position_id,
                    position_title=position_title,
                    applicant_id=applicant_id,
                    applicant_display_name=applicant_display_name,
                    report=report,
                    assessment=assessment,
                )
                for assessment in report.requirement_assessments
            )
            if report.requirement_assessments
            else tuple(
                self._legacy_evidence_document(
                    context,
                    position_id=position_id,
                    position_title=position_title,
                    applicant_id=applicant_id,
                    applicant_display_name=applicant_display_name,
                    report=report,
                    item=item,
                )
                for item in report.items
            )
        )
        documents = (
            self._summary_document(
                context,
                position_id=position_id,
                position_title=position_title,
                applicant_id=applicant_id,
                applicant_display_name=applicant_display_name,
                report=report,
            ),
            *evidence_documents,
        )
        return self._repository.replace_report_documents(
            context,
            report_id=report.report_id,
            documents=documents,
        )

    def _summary_document(
        self,
        context: TenantContext,
        *,
        position_id: UUID,
        position_title: str,
        applicant_id: UUID,
        applicant_display_name: str,
        report: Report,
    ) -> AssistantSearchDocument:
        status_counts = {
            status: sum(
                assessment.status is status for assessment in report.requirement_assessments
            )
            for status in RequirementAssessmentStatus
        }
        total = len(report.requirement_assessments)
        requirement_lines = tuple(
            (
                f"{_requirement_type_label(assessment.requirement_type)} 자격요건 · "
                f"{_requirement_status_label(assessment.status)} · {assessment.statement}"
            )
            for assessment in report.requirement_assessments
        )
        text = "\n".join(
            (
                "지원자 자격요건 종합 판정",
                f"지원자명: {applicant_display_name}",
                f"지원 포지션: {position_title}",
                f"리포트 상태: {report.status.value}",
                (
                    "자격요건 판정: "
                    f"충족 {status_counts[RequirementAssessmentStatus.MET]} / 전체 {total}, "
                    f"부분 충족 {status_counts[RequirementAssessmentStatus.PARTIALLY_MET]}, "
                    f"미충족 {status_counts[RequirementAssessmentStatus.NOT_MET]}, "
                    f"판단 보류 {status_counts[RequirementAssessmentStatus.UNKNOWN]}"
                ),
                f"근거 요약: {report.summary}",
                *(requirement_lines or ("자격요건 판정: 아직 생성되지 않음",)),
            )
        )
        return self._document(
            context,
            document_id=uuid5(NAMESPACE_URL, f"assistant:{report.report_id}:summary"),
            position_id=position_id,
            applicant_id=applicant_id,
            report=report,
            report_item_id=None,
            criterion_id=None,
            document_type="report_summary",
            text=text,
            metadata={
                "report_status": report.status.value,
                "requirements_total": total,
                "requirements_met": status_counts[RequirementAssessmentStatus.MET],
                "requirements_partially_met": status_counts[
                    RequirementAssessmentStatus.PARTIALLY_MET
                ],
                "requirements_not_met": status_counts[RequirementAssessmentStatus.NOT_MET],
                "requirements_unknown": status_counts[RequirementAssessmentStatus.UNKNOWN],
                "applicant_display_name": applicant_display_name,
                "position_title": position_title,
            },
        )

    def _requirement_document(
        self,
        context: TenantContext,
        *,
        position_id: UUID,
        position_title: str,
        applicant_id: UUID,
        applicant_display_name: str,
        report: Report,
        assessment: RequirementAssessment,
    ) -> AssistantSearchDocument:
        evidence_lines = tuple(
            line
            for index, evidence in enumerate(assessment.evidence, start=1)
            for line in (
                (
                    f"근거 {index} ({_evidence_source_label(evidence.source_kind)} · "
                    f"{evidence.source_type}): {evidence.excerpt}"
                ),
                f"근거 설명 {index}: {evidence.explanation}",
            )
        )
        text = "\n".join(
            (
                "지원자 자격요건 판정 근거",
                f"지원자명: {applicant_display_name}",
                f"지원 포지션: {position_title}",
                f"자격요건 구분: {_requirement_type_label(assessment.requirement_type)}",
                f"자격요건: {assessment.statement}",
                f"판정 상태: {_requirement_status_label(assessment.status)}",
                f"판정 근거: {assessment.rationale}",
                *(evidence_lines or ("직접 연결된 근거: 없음",)),
            )
        )
        return self._document(
            context,
            document_id=uuid5(
                NAMESPACE_URL,
                (
                    f"assistant:{report.report_id}:requirement:"
                    f"{assessment.requirement_assessment_id}"
                ),
            ),
            position_id=position_id,
            applicant_id=applicant_id,
            report=report,
            report_item_id=None,
            criterion_id=None,
            document_type="report_criterion",
            text=text,
            metadata={
                "requirement_assessment_id": str(assessment.requirement_assessment_id),
                "job_requirement_id": str(assessment.job_requirement_id),
                "requirement_statement": assessment.statement,
                "requirement_type": assessment.requirement_type,
                "requirement_status": assessment.status.value,
                "evidence_ids": [str(evidence.evidence_id) for evidence in assessment.evidence],
                "applicant_display_name": applicant_display_name,
                "position_title": position_title,
            },
        )

    def _legacy_evidence_document(
        self,
        context: TenantContext,
        *,
        position_id: UUID,
        position_title: str,
        applicant_id: UUID,
        applicant_display_name: str,
        report: Report,
        item: ReportItem,
    ) -> AssistantSearchDocument:
        text = "\n".join(
            (
                "지원자 답변 근거 (이전 리포트)",
                f"지원자명: {applicant_display_name}",
                f"지원 포지션: {position_title}",
                f"확인 주제: {item.criterion_name or item.criterion_id}",
                f"근거 상태: {item.assessment_state.value}",
                f"관찰 내용: {item.observation}",
                f"답변 근거: {item.rationale}",
                f"불확실성: {item.uncertainty}",
            )
        )
        return self._document(
            context,
            document_id=uuid5(
                NAMESPACE_URL,
                f"assistant:{report.report_id}:criterion:{item.report_item_id}",
            ),
            position_id=position_id,
            applicant_id=applicant_id,
            report=report,
            report_item_id=item.report_item_id,
            criterion_id=item.criterion_id,
            document_type="report_criterion",
            text=text,
            metadata={
                "criterion_name": item.criterion_name,
                "assessment_state": item.assessment_state.value,
                "evidence_ids": [str(evidence.evidence_id) for evidence in item.evidence],
                "applicant_display_name": applicant_display_name,
                "position_title": position_title,
                "legacy_evidence": True,
            },
        )

    def _document(
        self,
        context: TenantContext,
        *,
        document_id: UUID,
        position_id: UUID,
        applicant_id: UUID,
        report: Report,
        report_item_id: UUID | None,
        criterion_id: UUID | None,
        document_type: str,
        text: str,
        metadata: dict[str, object],
    ) -> AssistantSearchDocument:
        return AssistantSearchDocument(
            assistant_document_id=document_id,
            company_id=report.company_id,
            position_id=position_id,
            applicant_id=applicant_id,
            invitation_id=report.invitation_id,
            report_id=report.report_id,
            report_item_id=report_item_id,
            criterion_id=criterion_id,
            document_type=document_type,
            source_version=f"{report.version}:{ASSISTANT_PROJECTION_VERSION}",
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            text=text,
            embedding=self._embedder.embed(context, text, dimensions=1024),
            embedding_model=self._embedder.model_id,
            embedding_version=self._embedder.embedding_version,
            created_at=report.created_at,
            metadata=metadata,
        )


def _requirement_type_label(requirement_type: str) -> str:
    return "필수" if requirement_type == "required" else "우대"


def _requirement_status_label(status: RequirementAssessmentStatus) -> str:
    return {
        RequirementAssessmentStatus.MET: "충족",
        RequirementAssessmentStatus.PARTIALLY_MET: "부분 충족",
        RequirementAssessmentStatus.NOT_MET: "미충족",
        RequirementAssessmentStatus.UNKNOWN: "판단 보류",
    }[status]


def _evidence_source_label(source_kind: str) -> str:
    return "면접 답변" if source_kind == "interview" else "제출 자료"


@dataclass(frozen=True, slots=True)
class AssistantSearchQuery:
    query: str
    position_id: UUID | None
    allowed_position_ids: tuple[UUID, ...] | None = None
    limit: int = 8


class AssistantSearchService:
    def __init__(
        self,
        repository: AssistantDocumentRepository,
        embedder: TextEmbedder,
        *,
        minimum_score: float = 0.0,
    ) -> None:
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("assistant minimum score must be between 0 and 1")
        self._repository = repository
        self._embedder = embedder
        self._minimum_score = minimum_score

    def search(
        self,
        context: TenantContext,
        query: AssistantSearchQuery,
    ) -> tuple[AssistantSearchResult, ...]:
        normalized = query.query.strip()
        if not normalized:
            raise ValueError("assistant search query is required")
        if query.allowed_position_ids == ():
            return ()
        results = self._repository.search(
            context,
            query=normalized,
            query_vector=self._embedder.embed(context, normalized, dimensions=1024),
            embedding_model=self._embedder.model_id,
            embedding_version=self._embedder.embedding_version,
            position_id=query.position_id,
            allowed_position_ids=query.allowed_position_ids,
            limit=query.limit,
        )
        return tuple(result for result in results if result.score >= self._minimum_score)


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    answer: str
    sources: tuple[AssistantSearchResult, ...]
    degraded_mode: str | None = None


class AssistantAnswerService:
    def __init__(
        self,
        search: AssistantSearchService,
        model: AIModel,
    ) -> None:
        self._search = search
        self._model = model

    def answer(
        self,
        context: TenantContext,
        *,
        scope: str,
        query: AssistantSearchQuery,
        archived_scope: bool = False,
    ) -> AssistantAnswer:
        sources = self._search.search(context, query)
        if not sources:
            return AssistantAnswer(
                answer=(
                    "선택한 범위의 최종 리포트를 검색해봤지만, 지금 질문과 "
                    "직접 연결되는 근거는 확인할 수 없었어요. 다른 표현으로 "
                    "묻거나 새 채팅에서 검색 범위를 넓혀보세요."
                ),
                sources=(),
                degraded_mode="no_sources",
            )
        try:
            verdict = parse_answer_response(
                self._model.generate(
                    context,
                    build_answer_prompt(
                        query=query.query,
                        scope=scope,
                        position_id=query.position_id,
                        archived_scope=archived_scope,
                        sources=sources,
                    ),
                )
            )
        except (RuntimeError, ValidationError, TypeError, ValueError, KeyError):
            return AssistantAnswer(
                answer=(
                    "질문과 관련된 최종 리포트를 검색해봤지만, 답변으로 "
                    "확정할 수 있는 내용은 확인하지 못했어요. 대신 아래에 "
                    "관련성이 높은 근거를 함께 표시했습니다."
                ),
                sources=sources,
                degraded_mode="generation_unavailable",
            )
        sources_by_id = {source.assistant_document_id: source for source in sources}
        cited = tuple(
            sources_by_id[source_id]
            for source_id in dict.fromkeys(verdict.source_ids)
            if source_id in sources_by_id
        )
        if not cited:
            cited = sources
        return AssistantAnswer(
            answer=verdict.answer,
            sources=cited,
        )
