from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AssistantSearchDocument:
    assistant_document_id: UUID
    company_id: UUID
    position_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    report_id: UUID
    report_item_id: UUID | None
    criterion_id: UUID | None
    document_type: str
    source_version: str
    content_hash: str
    text: str
    embedding: tuple[float, ...]
    embedding_model: str
    embedding_version: str
    created_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.document_type not in {"report_summary", "report_criterion"}:
            raise ValueError("unsupported assistant document type")
        if len(self.embedding) != 1024:
            raise ValueError("assistant embeddings must contain 1024 dimensions")
        if not self.text.strip():
            raise ValueError("assistant document text is required")
        if len(self.content_hash) != 64:
            raise ValueError("assistant document content hash is invalid")


@dataclass(frozen=True, slots=True)
class AssistantSearchResult:
    assistant_document_id: UUID
    position_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    report_id: UUID
    report_item_id: UUID | None
    criterion_id: UUID | None
    document_type: str
    excerpt: str
    score: float
    score_components: dict[str, float]
    metadata: dict[str, object]
