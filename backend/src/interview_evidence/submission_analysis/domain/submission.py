from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubmissionStateError(ValueError):
    """Raised when submission or analysis state transitions are invalid."""


class SourceType(StrEnum):
    COVER_LETTER = "cover_letter"
    RESUME = "resume"
    PDF = "pdf"
    PUBLIC_GIT = "public_git"
    PUBLIC_URL = "public_url"


class SubmissionStatus(StrEnum):
    RECEIVED = "received"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"
    DELETED = "deleted"


class AnalysisStatus(StrEnum):
    RUNNING = "running"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


SUBMISSION_TRANSITIONS: dict[SubmissionStatus, set[SubmissionStatus]] = {
    SubmissionStatus.RECEIVED: {
        SubmissionStatus.VALIDATING,
        SubmissionStatus.FAILED,
        SubmissionStatus.DELETED,
    },
    SubmissionStatus.VALIDATING: {
        SubmissionStatus.ANALYZING,
        SubmissionStatus.FAILED,
        SubmissionStatus.DELETED,
    },
    SubmissionStatus.ANALYZING: {
        SubmissionStatus.READY,
        SubmissionStatus.PARTIAL,
        SubmissionStatus.FAILED,
        SubmissionStatus.DELETED,
    },
    SubmissionStatus.READY: {SubmissionStatus.DELETED},
    SubmissionStatus.PARTIAL: {
        SubmissionStatus.ANALYZING,
        SubmissionStatus.READY,
        SubmissionStatus.DELETED,
    },
    SubmissionStatus.FAILED: {
        SubmissionStatus.VALIDATING,
        SubmissionStatus.DELETED,
    },
    SubmissionStatus.DELETED: set(),
}


class Submission(BaseModel):
    model_config = ConfigDict(frozen=True)

    submission_id: UUID
    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    source_type: SourceType
    source_uri: str = Field(min_length=1, max_length=4096)
    original_filename: str | None = Field(default=None, max_length=255)
    content_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    byte_size: int | None = Field(default=None, ge=1)
    media_type: str | None = Field(default=None, max_length=200)
    candidate_identity_inputs: dict[str, tuple[str, ...]] | None = None
    status: SubmissionStatus = SubmissionStatus.RECEIVED
    failure_code: str | None = Field(default=None, max_length=100)
    impact_summary: str | None = Field(default=None, max_length=2000)
    created_at: datetime
    row_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def file_and_url_metadata_are_consistent(self) -> Submission:
        is_file = self.source_type in {
            SourceType.COVER_LETTER,
            SourceType.RESUME,
            SourceType.PDF,
        }
        if is_file and (
            self.original_filename is None
            or self.content_hash is None
            or self.byte_size is None
            or self.media_type is None
        ):
            raise ValueError("file submissions require integrity metadata")
        if self.candidate_identity_inputs is not None:
            if self.source_type is not SourceType.PUBLIC_GIT:
                raise ValueError("candidate identity inputs are only valid for public Git")
            allowed_keys = {
                "claimed_names",
                "claimed_emails",
                "claimed_handles",
            }
            if not set(self.candidate_identity_inputs).issubset(allowed_keys):
                raise ValueError("candidate identity input contains an unsupported field")
            for values in self.candidate_identity_inputs.values():
                if len(values) > 20 or any(
                    not value.strip() or len(value) > 320 for value in values
                ):
                    raise ValueError("candidate identity input is invalid")
        return self

    def transition(
        self,
        status: SubmissionStatus,
        *,
        failure_code: str | None = None,
        impact_summary: str | None = None,
    ) -> Submission:
        if status not in SUBMISSION_TRANSITIONS[self.status]:
            raise SubmissionStateError(
                f"cannot transition submission from {self.status} to {status}"
            )
        if status in {
            SubmissionStatus.PARTIAL,
            SubmissionStatus.FAILED,
        } and (failure_code is None or impact_summary is None):
            raise SubmissionStateError("partial and failed submissions require sanitized impact")
        return self.model_copy(
            update={
                "status": status,
                "failure_code": failure_code,
                "impact_summary": impact_summary,
                "row_version": self.row_version + 1,
            }
        )


class SubmissionAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_id: UUID
    company_id: UUID
    submission_id: UUID
    analysis_version: int = Field(ge=1)
    extractor_version: str = Field(min_length=1, max_length=100)
    chunk_config_version: str = Field(min_length=1, max_length=100)
    claims: tuple[dict[str, object], ...] = ()
    conflicts: tuple[dict[str, object], ...] = ()
    verification_points: tuple[dict[str, object], ...] = ()
    status: AnalysisStatus
    created_at: datetime
    failure_code: str | None = None
    impact_summary: str | None = None

    @model_validator(mode="after")
    def failed_results_explain_impact(self) -> SubmissionAnalysis:
        if self.status in {AnalysisStatus.PARTIAL, AnalysisStatus.FAILED} and (
            self.failure_code is None or self.impact_summary is None
        ):
            raise ValueError("partial and failed analyses require sanitized impact")
        return self
