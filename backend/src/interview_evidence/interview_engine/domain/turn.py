from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TurnSpeaker(StrEnum):
    INTERVIEWER = "interviewer"
    APPLICANT = "applicant"


class TurnStatus(StrEnum):
    PREPARING = "preparing"
    PRESENTED = "presented"
    RECORDING = "recording"
    FINAL = "final"
    FAILED = "failed"


class InterviewTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    turn_id: UUID
    company_id: UUID
    interview_session_id: UUID
    sequence: int = Field(ge=1)
    speaker: TurnSpeaker
    status: TurnStatus
    text: str | None = None
    target_criterion_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=200)
    model_config_version: str | None = None
    finalized_at: datetime | None = None

    @model_validator(mode="after")
    def final_and_question_fields_are_consistent(self) -> InterviewTurn:
        if self.speaker is TurnSpeaker.INTERVIEWER and self.target_criterion_id is None:
            raise ValueError("interviewer turn requires a target criterion")
        if self.status is TurnStatus.FINAL and (self.text is None or self.finalized_at is None):
            raise ValueError("final turn requires text and finalized_at")
        return self


class HotViewSyncStatus(StrEnum):
    PENDING = "pending"
    SYNCED = "synced"
    DEGRADED = "degraded"


class SessionCheckpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkpoint_id: UUID
    company_id: UUID
    interview_session_id: UUID
    session_sequence: int = Field(ge=0)
    last_final_turn_id: UUID | None = None
    last_media_chunk_sequence: int = Field(default=0, ge=0)
    pending_turn_id: UUID | None = None
    hot_view_sync_status: HotViewSyncStatus
    created_at: datetime


class RecordingUploadStatus(StrEnum):
    ISSUED = "issued"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    FAILED = "failed"


class RecordingChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    recording_chunk_id: UUID
    company_id: UUID
    interview_session_id: UUID
    sequence: int = Field(ge=0)
    object_key: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(ge=1)
    session_start_ms: int = Field(ge=0)
    session_end_ms: int = Field(ge=1)
    upload_status: RecordingUploadStatus
    idempotency_key: str = Field(min_length=8, max_length=200)
    created_at: datetime

    @model_validator(mode="after")
    def recording_range_is_ordered(self) -> RecordingChunk:
        if self.session_end_ms <= self.session_start_ms:
            raise ValueError("recording chunk range must be increasing")
        return self


class QuestionSourceReference(BaseModel):
    """A reproducible explanation for a question, never applicant-answer Evidence."""

    model_config = ConfigDict(frozen=True)

    source_reference_id: UUID
    company_id: UUID
    interview_session_id: UUID
    question_turn_id: UUID
    source_id: UUID
    source_type: str = Field(min_length=1, max_length=100)
    locator: dict[str, object]
    excerpt: str = Field(default="", max_length=2000)
    relevance_score: float = Field(ge=0)
    ownership_confidence: float = Field(ge=0, le=1)
    retrieval_config_version: str = Field(min_length=1, max_length=100)
    model_config_version: str = Field(min_length=1, max_length=100)
    created_at: datetime


class VerificationProgressState(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"


class VerificationProgress(BaseModel):
    """Answer-driven state for one immutable candidate verification target."""

    model_config = ConfigDict(frozen=True)

    verification_progress_id: UUID
    company_id: UUID
    interview_session_id: UUID
    applicant_id: UUID
    verification_target_id: UUID
    criterion_id: UUID
    state: VerificationProgressState
    follow_up_count: int = Field(ge=0, le=3)
    final_answer_turn_ids: tuple[UUID, ...] = ()
    updated_at: datetime


class QuestionRationale(BaseModel):
    """Why a question was asked. This record is never competency Evidence."""

    model_config = ConfigDict(frozen=True)

    question_rationale_id: UUID
    company_id: UUID
    interview_session_id: UUID
    question_turn_id: UUID
    applicant_id: UUID
    competency_model_version_id: UUID
    criterion_id: UUID
    verification_target_id: UUID
    verification_target_type: str = Field(min_length=1, max_length=40)
    objective: str = Field(min_length=1, max_length=4000)
    question_type: str = Field(min_length=1, max_length=40)
    interview_stage: str = Field(default="technical", min_length=1, max_length=40)
    retrieval_version: str = Field(min_length=1, max_length=100)
    generation_version: str = Field(min_length=1, max_length=100)
    policy_result: str = Field(min_length=1, max_length=100)
    source_reference_ids: tuple[UUID, ...] = ()
    created_at: datetime
