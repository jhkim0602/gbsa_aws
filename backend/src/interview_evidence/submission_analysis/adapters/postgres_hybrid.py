from __future__ import annotations

import math
from collections.abc import Sequence
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.submission_analysis.adapters.search import (
    SearchCandidate,
    SearchDocument,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    RetrievalDocumentRow,
)


class PostgresHybridSearchIndex:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, document: SearchDocument) -> None:
        if len(document.vector) != 1024:
            raise ValueError("semantic embeddings must contain 1024 dimensions")
        self._session.merge(
            RetrievalDocumentRow(
                retrieval_document_id=_document_uuid(document.document_id),
                company_id=document.company_id,
                applicant_id=document.applicant_id,
                invitation_id=document.invitation_id,
                competency_model_version_id=(document.competency_model_version_id or UUID(int=0)),
                criterion_id=document.criterion_id,
                document_type=document.document_type,
                source_id=document.source_id,
                source_version=document.source_version,
                content_hash=document.content_hash or "0" * 64,
                locator=document.locator,
                protected_text=document.text,
                search_text=document.text,
                embedding=list(document.vector),
                embedding_model=document.embedding_model,
                embedding_version=document.embedding_version,
                source_type=document.source_type,
                path=document.path,
                symbol=document.symbol,
                ownership_confidence=document.ownership_confidence,
                metadata_json={"symbols": list(document.symbols)},
                deleted_at=None,
            )
        )
        self._session.flush()

    def delete(self, context: TenantContext, document_id: str) -> bool:
        tenant = require_tenant_context(context)
        identifier = _document_uuid(document_id)
        row = self._session.scalar(
            select(RetrievalDocumentRow).where(
                RetrievalDocumentRow.company_id == tenant.company_id,
                RetrievalDocumentRow.retrieval_document_id == identifier,
            )
        )
        if row is not None:
            self._session.delete(row)
            self._session.flush()
        return (
            self._session.scalar(
                select(RetrievalDocumentRow).where(
                    RetrievalDocumentRow.company_id == tenant.company_id,
                    RetrievalDocumentRow.retrieval_document_id == identifier,
                )
            )
            is None
        )

    def delete_and_verify(self, context: TenantContext, document_id: str) -> bool:
        return self.delete(context, document_id)

    def healthcheck(self) -> None:
        self._session.execute(select(1))

    def candidates(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        exact_symbol: str | None,
        invitation_id: UUID | None = None,
        competency_model_version_id: UUID | None = None,
        criterion_id: UUID | None = None,
    ) -> tuple[SearchCandidate, ...]:
        tenant = require_tenant_context(context)
        if tenant.actor_type.value == "applicant" and tenant.actor_id != applicant_id:
            raise PermissionError("applicant scope mismatch")
        if len(query_vector) != 1024:
            raise ValueError("query embedding must contain 1024 dimensions")

        statement = select(RetrievalDocumentRow).where(
            RetrievalDocumentRow.company_id == tenant.company_id,
            RetrievalDocumentRow.applicant_id == applicant_id,
            RetrievalDocumentRow.deleted_at.is_(None),
        )
        if invitation_id is not None:
            statement = statement.where(RetrievalDocumentRow.invitation_id == invitation_id)
        if competency_model_version_id is not None:
            statement = statement.where(
                RetrievalDocumentRow.competency_model_version_id == competency_model_version_id
            )
        if criterion_id is not None:
            statement = statement.where(RetrievalDocumentRow.criterion_id.in_((None, criterion_id)))

        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            query_vector_value = list(query_vector)
            vector_score = (
                literal(1.0) - RetrievalDocumentRow.embedding.cosine_distance(query_vector_value)
            ).label("vector_score")
            search_document = func.to_tsvector(
                "simple",
                RetrievalDocumentRow.search_text,
            )
            search_query = func.websearch_to_tsquery("simple", query)
            lexical_score_expr = func.ts_rank_cd(
                search_document,
                search_query,
            ).label("lexical_score")
            exact_score_expr = (
                case(
                    (
                        func.lower(RetrievalDocumentRow.symbol) == exact_symbol.casefold(),
                        1.0,
                    ),
                    else_=0.0,
                )
                if exact_symbol
                else literal(0.0)
            ).label("exact_symbol_score")
            ranked = self._session.execute(
                statement.add_columns(
                    vector_score,
                    lexical_score_expr,
                    exact_score_expr,
                )
                .order_by(
                    (
                        vector_score * 0.55 + lexical_score_expr * 0.30 + exact_score_expr * 0.80
                    ).desc()
                )
                .limit(200)
            ).all()
            return tuple(
                SearchCandidate(
                    document=self._document_from_row(row, applicant_id),
                    vector_score=max(0.0, float(vector)),
                    lexical_score=max(0.0, float(lexical)),
                    exact_symbol_score=max(0.0, float(exact)),
                )
                for row, vector, lexical, exact in ranked
            )

        rows = self._session.scalars(statement.limit(200)).all()
        query_terms = {term.casefold() for term in query.split() if term}
        candidates: list[SearchCandidate] = []
        for row in rows:
            row_terms = {
                term.casefold() for term in row.search_text.replace("_", " ").split() if term
            }
            lexical_value = len(query_terms & row_terms) / len(query_terms) if query_terms else 0.0
            symbols = _symbols_from_metadata(row.metadata_json)
            exact_value = (
                1.0
                if exact_symbol is not None
                and exact_symbol.casefold() in {symbol.casefold() for symbol in symbols}
                else 0.0
            )
            candidates.append(
                SearchCandidate(
                    document=self._document_from_row(row, applicant_id),
                    vector_score=_cosine(
                        query_vector,
                        tuple(
                            float(value)
                            for value in cast(
                                Sequence[float],
                                row.embedding,
                            )
                        ),
                    ),
                    lexical_score=lexical_value,
                    exact_symbol_score=exact_value,
                )
            )
        return tuple(candidates)

    @staticmethod
    def _document_from_row(
        row: RetrievalDocumentRow,
        applicant_id: UUID,
    ) -> SearchDocument:
        symbols = _symbols_from_metadata(row.metadata_json)
        return SearchDocument(
            document_id=str(row.retrieval_document_id),
            company_id=row.company_id,
            applicant_id=applicant_id,
            source_id=row.source_id,
            text=row.protected_text,
            vector=tuple(float(value) for value in cast(Sequence[float], row.embedding)),
            symbols=symbols,
            locator=dict(row.locator),
            ownership_confidence=row.ownership_confidence or 0.0,
            invitation_id=row.invitation_id,
            competency_model_version_id=row.competency_model_version_id,
            criterion_id=row.criterion_id,
            document_type=row.document_type,
            source_type=row.source_type,
            source_version=row.source_version,
            content_hash=row.content_hash,
            embedding_model=row.embedding_model,
            embedding_version=row.embedding_version,
            path=row.path,
            symbol=row.symbol,
        )


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator


def _document_uuid(document_id: str) -> UUID:
    try:
        return UUID(document_id)
    except ValueError:
        return uuid5(NAMESPACE_URL, document_id)


def _symbols_from_metadata(metadata: dict[str, object]) -> tuple[str, ...]:
    values = metadata.get("symbols", ())
    if not isinstance(values, list | tuple):
        return ()
    return tuple(str(value) for value in values)
