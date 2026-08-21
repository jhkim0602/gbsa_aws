from __future__ import annotations

import math
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Index, String, Text, func, literal, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from interview_evidence.recruiting_assistant.domain import (
    AssistantSearchDocument,
    AssistantSearchResult,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class Base(DeclarativeBase):
    pass


class AssistantRetrievalDocumentRow(Base):
    __tablename__ = "assistant_retrieval_documents"
    __table_args__ = (
        Index(
            "ix_assistant_retrieval_scope",
            "company_id",
            "position_id",
            "document_type",
        ),
        Index("ix_assistant_retrieval_report", "company_id", "report_id"),
        Index("ix_assistant_retrieval_invitation", "company_id", "invitation_id"),
    )

    company_id: Mapped[UUID] = mapped_column(primary_key=True)
    assistant_document_id: Mapped[UUID] = mapped_column(primary_key=True)
    position_id: Mapped[UUID]
    applicant_id: Mapped[UUID]
    invitation_id: Mapped[UUID]
    report_id: Mapped[UUID]
    report_item_id: Mapped[UUID | None]
    criterion_id: Mapped[UUID | None]
    document_type: Mapped[str] = mapped_column(String(40))
    source_version: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    protected_text: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssistantDocumentRepository(Protocol):
    def replace_report_documents(
        self,
        context: TenantContext,
        *,
        report_id: UUID,
        documents: tuple[AssistantSearchDocument, ...],
    ) -> tuple[AssistantSearchDocument, ...]: ...

    def search(
        self,
        context: TenantContext,
        *,
        query: str,
        query_vector: tuple[float, ...],
        embedding_model: str,
        embedding_version: str,
        position_id: UUID | None,
        allowed_position_ids: tuple[UUID, ...] | None,
        limit: int,
    ) -> tuple[AssistantSearchResult, ...]: ...

    def list_document_ids_for_invitation(
        self,
        context: TenantContext,
        invitation_id: UUID,
    ) -> tuple[UUID, ...]: ...

    def delete_and_verify(
        self,
        context: TenantContext,
        document_id: UUID,
    ) -> bool: ...


class SQLAlchemyAssistantDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_report_documents(
        self,
        context: TenantContext,
        *,
        report_id: UUID,
        documents: tuple[AssistantSearchDocument, ...],
    ) -> tuple[AssistantSearchDocument, ...]:
        tenant = require_tenant_context(context)
        if any(
            document.company_id != tenant.company_id or document.report_id != report_id
            for document in documents
        ):
            raise PermissionError("assistant document scope mismatch")
        active_ids = {document.assistant_document_id for document in documents}
        stale_rows = self._session.scalars(
            select(AssistantRetrievalDocumentRow).where(
                AssistantRetrievalDocumentRow.company_id == tenant.company_id,
                AssistantRetrievalDocumentRow.report_id == report_id,
            )
        ).all()
        for row in stale_rows:
            if row.assistant_document_id not in active_ids:
                self._session.delete(row)
        for document in documents:
            self._session.merge(
                AssistantRetrievalDocumentRow(
                    company_id=document.company_id,
                    assistant_document_id=document.assistant_document_id,
                    position_id=document.position_id,
                    applicant_id=document.applicant_id,
                    invitation_id=document.invitation_id,
                    report_id=document.report_id,
                    report_item_id=document.report_item_id,
                    criterion_id=document.criterion_id,
                    document_type=document.document_type,
                    source_version=document.source_version,
                    content_hash=document.content_hash,
                    protected_text=document.text,
                    search_text=document.text,
                    embedding=list(document.embedding),
                    embedding_model=document.embedding_model,
                    embedding_version=document.embedding_version,
                    metadata_json=dict(document.metadata),
                    created_at=document.created_at,
                    deleted_at=None,
                )
            )
        self._session.flush()
        return documents

    def search(
        self,
        context: TenantContext,
        *,
        query: str,
        query_vector: tuple[float, ...],
        embedding_model: str,
        embedding_version: str,
        position_id: UUID | None,
        allowed_position_ids: tuple[UUID, ...] | None,
        limit: int,
    ) -> tuple[AssistantSearchResult, ...]:
        tenant = require_tenant_context(context)
        if len(query_vector) != 1024:
            raise ValueError("assistant query embedding must contain 1024 dimensions")
        if not query.strip():
            raise ValueError("assistant search query is required")
        if not 1 <= limit <= 20:
            raise ValueError("assistant search limit must be between 1 and 20")
        if position_id is not None and allowed_position_ids is not None:
            raise ValueError("assistant search accepts one position filter mode")
        if allowed_position_ids == ():
            return ()

        statement = select(AssistantRetrievalDocumentRow).where(
            AssistantRetrievalDocumentRow.company_id == tenant.company_id,
            AssistantRetrievalDocumentRow.deleted_at.is_(None),
            AssistantRetrievalDocumentRow.embedding_model == embedding_model,
            AssistantRetrievalDocumentRow.embedding_version == embedding_version,
        )
        if position_id is not None:
            statement = statement.where(AssistantRetrievalDocumentRow.position_id == position_id)
        elif allowed_position_ids is not None:
            statement = statement.where(
                AssistantRetrievalDocumentRow.position_id.in_(allowed_position_ids)
            )

        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            vector_score_expr = (
                literal(1.0)
                - AssistantRetrievalDocumentRow.embedding.cosine_distance(list(query_vector))
            ).label("vector_score")
            lexical_rank_expr = func.ts_rank_cd(
                func.to_tsvector("simple", AssistantRetrievalDocumentRow.search_text),
                func.websearch_to_tsquery("simple", query),
            )
            lexical_score_expr = func.least(
                literal(1.0),
                lexical_rank_expr,
            ).label("lexical_score")
            rows = self._session.execute(
                statement.add_columns(vector_score_expr, lexical_score_expr)
                .order_by((vector_score_expr * 0.7 + lexical_score_expr * 0.3).desc())
                .limit(limit)
            ).all()
            return tuple(
                self._result(
                    row,
                    vector_score=max(0.0, float(vector)),
                    lexical_score=max(0.0, float(lexical)),
                )
                for row, vector, lexical in rows
            )

        query_terms = {term.casefold() for term in query.split() if term}
        candidates = []
        for row in self._session.scalars(statement).all():
            vector_score = _cosine(tuple(row.embedding), query_vector)
            row_terms = {
                term.casefold() for term in row.search_text.replace("_", " ").split() if term
            }
            lexical_score = len(query_terms & row_terms) / len(query_terms) if query_terms else 0.0
            candidates.append(
                self._result(
                    row,
                    vector_score=max(0.0, vector_score),
                    lexical_score=lexical_score,
                )
            )
        return tuple(
            sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:limit]
        )

    def list_document_ids_for_invitation(
        self,
        context: TenantContext,
        invitation_id: UUID,
    ) -> tuple[UUID, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            self._session.scalars(
                select(AssistantRetrievalDocumentRow.assistant_document_id).where(
                    AssistantRetrievalDocumentRow.company_id == tenant.company_id,
                    AssistantRetrievalDocumentRow.invitation_id == invitation_id,
                )
            ).all()
        )

    def delete_and_verify(
        self,
        context: TenantContext,
        document_id: UUID,
    ) -> bool:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(AssistantRetrievalDocumentRow).where(
                AssistantRetrievalDocumentRow.company_id == tenant.company_id,
                AssistantRetrievalDocumentRow.assistant_document_id == document_id,
            )
        )
        if row is not None:
            self._session.delete(row)
            self._session.flush()
        return (
            self._session.scalar(
                select(AssistantRetrievalDocumentRow.assistant_document_id).where(
                    AssistantRetrievalDocumentRow.company_id == tenant.company_id,
                    AssistantRetrievalDocumentRow.assistant_document_id == document_id,
                )
            )
            is None
        )

    @staticmethod
    def _result(
        row: AssistantRetrievalDocumentRow,
        *,
        vector_score: float,
        lexical_score: float,
    ) -> AssistantSearchResult:
        normalized_vector = min(1.0, max(0.0, vector_score))
        normalized_lexical = min(1.0, max(0.0, lexical_score))
        return AssistantSearchResult(
            assistant_document_id=row.assistant_document_id,
            position_id=row.position_id,
            applicant_id=row.applicant_id,
            invitation_id=row.invitation_id,
            report_id=row.report_id,
            report_item_id=row.report_item_id,
            criterion_id=row.criterion_id,
            document_type=row.document_type,
            excerpt=row.protected_text[:2000],
            score=normalized_vector * 0.7 + normalized_lexical * 0.3,
            score_components={
                "vector": normalized_vector,
                "lexical": normalized_lexical,
            },
            metadata=dict(row.metadata_json),
        )


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator
