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
from interview_evidence.reporting.domain.report import Report, ReportItem
from interview_evidence.shared.aws_clients.ports import AIModel, TextEmbedder
from interview_evidence.shared.tenant import TenantContext


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
        documents = (
            self._summary_document(
                context,
                position_id=position_id,
                position_title=position_title,
                applicant_id=applicant_id,
                applicant_display_name=applicant_display_name,
                report=report,
            ),
            *(
                self._criterion_document(
                    context,
                    position_id=position_id,
                    position_title=position_title,
                    applicant_id=applicant_id,
                    applicant_display_name=applicant_display_name,
                    report=report,
                    item=item,
                )
                for item in report.items
            ),
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
        score = str(report.overall_score) if report.overall_score is not None else "미산정"
        text = "\n".join(
            (
                "지원자 종합 평가 리포트",
                f"지원자명: {applicant_display_name}",
                f"지원 포지션: {position_title}",
                f"리포트 상태: {report.status.value}",
                f"종합 점수: {score}",
                f"평가 완료 기준: {len(report.scored_items)}/{len(report.items)}",
                f"종합 요약: {report.summary}",
                "평가 항목: "
                + ", ".join(item.criterion_name or str(item.criterion_id) for item in report.items),
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
                "overall_score": report.overall_score,
                "scored_criteria_count": len(report.scored_items),
                "total_criteria_count": len(report.items),
                "applicant_display_name": applicant_display_name,
                "position_title": position_title,
            },
        )

    def _criterion_document(
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
        axis_lines = tuple(
            (
                f"{axis.label}: "
                f"{axis.score if axis.score is not None else '미산정'}점, {axis.rationale}"
            )
            for axis in item.axis_assessments
        )
        text = "\n".join(
            (
                f"지원자명: {applicant_display_name}",
                f"지원 포지션: {position_title}",
                f"평가 기준: {item.criterion_name or item.criterion_id}",
                f"평가 상태: {item.assessment_state.value}",
                f"관찰 내용: {item.observation}",
                f"평가 근거: {item.rationale}",
                f"불확실성: {item.uncertainty}",
                *(("세부 평가:", *axis_lines) if axis_lines else ()),
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
                "score": item.average_score,
                "evidence_ids": [str(evidence.evidence_id) for evidence in item.evidence],
                "applicant_display_name": applicant_display_name,
                "position_title": position_title,
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
            source_version=str(report.version),
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            text=text,
            embedding=self._embedder.embed(context, text, dimensions=1024),
            embedding_model=self._embedder.model_id,
            embedding_version=self._embedder.embedding_version,
            created_at=report.created_at,
            metadata=metadata,
        )


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
                answer="현재 선택한 범위의 최종 리포트에서 질문을 뒷받침할 근거를 찾지 못했습니다.",
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
                    "검색된 근거는 있지만 현재 답변을 생성하지 못했습니다. "
                    "잠시 후 다시 시도해 주세요."
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
            return AssistantAnswer(
                answer=(
                    "검색 근거와 답변의 인용 관계를 검증하지 못했습니다. "
                    "근거를 다시 검색한 뒤 질문해 주세요."
                ),
                sources=(),
                degraded_mode="citation_validation_failed",
            )
        return AssistantAnswer(
            answer=verdict.answer,
            sources=cited,
        )
