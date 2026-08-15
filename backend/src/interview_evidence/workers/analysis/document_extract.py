from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.workers.analysis.document_chunker import DocumentPage


class DocumentExtractionError(RuntimeError):
    """Sanitized document extraction failure."""


@dataclass(frozen=True, slots=True)
class TextractPage:
    page_number: int
    lines: tuple[str, ...]


class TextractPort(Protocol):
    def extract_pages(
        self,
        context: TenantContext,
        object_id: UUID,
    ) -> tuple[TextractPage, ...]: ...


class DeterministicTextract:
    def __init__(self, pages: tuple[TextractPage, ...]) -> None:
        self._pages = pages
        self.calls: list[tuple[UUID, UUID]] = []

    def extract_pages(
        self,
        context: TenantContext,
        object_id: UUID,
    ) -> tuple[TextractPage, ...]:
        tenant = require_tenant_context(context)
        self.calls.append((tenant.company_id, object_id))
        return self._pages


class DocumentExtractionAdapter:
    def __init__(self, textract: TextractPort, *, extractor_version: str) -> None:
        self._textract = textract
        self.extractor_version = extractor_version

    def extract(
        self,
        context: TenantContext,
        object_id: UUID,
    ) -> tuple[DocumentPage, ...]:
        pages = self._textract.extract_pages(context, object_id)
        if not pages:
            raise DocumentExtractionError("document_contains_no_extractable_text")
        ordered = sorted(pages, key=lambda page: page.page_number)
        if [page.page_number for page in ordered] != list(range(1, len(ordered) + 1)):
            raise DocumentExtractionError("document_page_sequence_invalid")
        return tuple(
            DocumentPage(
                page_number=page.page_number,
                text="\n".join(line for line in page.lines if line.strip()),
            )
            for page in ordered
        )
