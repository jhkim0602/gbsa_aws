from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page_number: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=500)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    path: str | None = Field(default=None, max_length=1000)
    symbol: str | None = Field(default=None, max_length=500)
    commit_sha: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")

    @model_validator(mode="after")
    def has_a_reproducible_anchor(self) -> SourceLocation:
        if self.page_number is None and self.path is None:
            raise ValueError("source location requires a page or code path")
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.start_line > self.end_line
        ):
            raise ValueError("source line range is invalid")
        return self


class SubmissionChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    company_id: UUID
    applicant_id: UUID
    submission_id: UUID
    analysis_id: UUID
    source_location: SourceLocation
    text_object_key: str
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    chunk_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    embedding_model: str
    embedding_version: str
    index_document_id: str
    deleted_at: datetime | None = None


class SourceReferenceCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: UUID
    source_type: str
    locator: dict[str, object]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    relevance_score: float = Field(ge=0)
    ownership_confidence: float = Field(ge=0, le=1)
