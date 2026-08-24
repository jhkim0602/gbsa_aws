from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from interview_evidence.shared.submission_materials import (
    DEFAULT_SUBMISSION_REQUIREMENTS,
    SubmissionRequirement,
    normalize_submission_requirements,
)

DEFAULT_RECRUITING_STAGE_NAMES = (
    "보류",
    "검토",
    "1차 합격",
    "최종합격",
    "불합격",
)
MAX_RECRUITING_STAGES = 20


class InvitationStateError(ValueError):
    """Raised for invalid or stale invitation state transitions."""


class InvitationStatus(StrEnum):
    INVITED = "invited"
    IDENTITY_VERIFIED = "identity_verified"
    CONSENTED = "consented"
    MATERIALS_SUBMITTED = "materials_submitted"
    ANALYZING = "analyzing"
    READY = "ready"
    INTERVIEWING = "interviewing"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DELETED = "deleted"


class RecruitingStage(BaseModel):
    """A company-editable hiring stage, separate from applicant journey state."""

    model_config = ConfigDict(frozen=True)

    recruiting_stage_id: UUID
    company_id: UUID
    position_id: UUID
    name: str = Field(min_length=1, max_length=40)
    sort_order: int = Field(ge=0, lt=MAX_RECRUITING_STAGES)
    row_version: int = Field(default=1, ge=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("recruiting stage name is required")
        return normalized

    def rename(self, name: str, *, expected_version: int) -> RecruitingStage:
        if expected_version != self.row_version:
            raise InvitationStateError("stale recruiting stage version")
        return RecruitingStage(
            **self.model_dump(exclude={"name", "row_version"}),
            name=name,
            row_version=self.row_version + 1,
        )

    def reorder(self, sort_order: int) -> RecruitingStage:
        if sort_order == self.sort_order:
            return self
        return self.model_copy(
            update={"sort_order": sort_order, "row_version": self.row_version + 1}
        )


TERMINAL_INVITATION_STATES = {
    InvitationStatus.REVIEWED,
    InvitationStatus.EXPIRED,
    InvitationStatus.REVOKED,
    InvitationStatus.DELETED,
}

ALLOWED_INVITATION_TRANSITIONS: dict[InvitationStatus, set[InvitationStatus]] = {
    InvitationStatus.INVITED: {
        InvitationStatus.IDENTITY_VERIFIED,
        InvitationStatus.EXPIRED,
        InvitationStatus.REVOKED,
    },
    InvitationStatus.IDENTITY_VERIFIED: {
        InvitationStatus.CONSENTED,
        InvitationStatus.EXPIRED,
        InvitationStatus.REVOKED,
    },
    InvitationStatus.CONSENTED: {
        InvitationStatus.MATERIALS_SUBMITTED,
        InvitationStatus.REVOKED,
        InvitationStatus.DELETED,
    },
    InvitationStatus.MATERIALS_SUBMITTED: {
        InvitationStatus.ANALYZING,
        InvitationStatus.REVOKED,
        InvitationStatus.DELETED,
    },
    InvitationStatus.ANALYZING: {
        InvitationStatus.READY,
        InvitationStatus.REVOKED,
        InvitationStatus.DELETED,
    },
    InvitationStatus.READY: {
        InvitationStatus.INTERVIEWING,
        InvitationStatus.REVOKED,
        InvitationStatus.DELETED,
    },
    InvitationStatus.INTERVIEWING: {
        InvitationStatus.INTERRUPTED,
        InvitationStatus.COMPLETED,
        InvitationStatus.REVOKED,
    },
    InvitationStatus.INTERRUPTED: {
        InvitationStatus.INTERVIEWING,
        InvitationStatus.COMPLETED,
        InvitationStatus.REVOKED,
    },
    InvitationStatus.COMPLETED: {
        InvitationStatus.REVIEWED,
        InvitationStatus.DELETED,
    },
    InvitationStatus.REVIEWED: {InvitationStatus.DELETED},
    InvitationStatus.EXPIRED: {InvitationStatus.DELETED},
    InvitationStatus.REVOKED: {InvitationStatus.DELETED},
    InvitationStatus.DELETED: set(),
}


class Invitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    invitation_id: UUID
    company_id: UUID
    position_id: UUID
    competency_model_version_id: UUID
    applicant_id: UUID
    applicant_email_normalized: str = Field(min_length=3, max_length=320)
    applicant_display_name: str = Field(min_length=1, max_length=200)
    submission_requirements: tuple[SubmissionRequirement, ...] = DEFAULT_SUBMISSION_REQUIREMENTS
    token_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime
    status: InvitationStatus = InvitationStatus.INVITED
    identity_verified_at: datetime | None = None
    last_state_actor_type: str = "company_user"
    row_version: int = Field(default=1, ge=1)
    recruiting_stage_id: UUID | None = None
    pipeline_row_version: int = Field(default=1, ge=1)

    @field_validator("applicant_email_normalized")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("submission_requirements")
    @classmethod
    def validate_submission_requirements(
        cls,
        value: tuple[SubmissionRequirement, ...],
    ) -> tuple[SubmissionRequirement, ...]:
        return normalize_submission_requirements(value)

    @property
    def applicant_email(self) -> str:
        return self.applicant_email_normalized

    @classmethod
    def create(
        cls,
        *,
        invitation_id: UUID,
        company_id: UUID,
        position_id: UUID,
        competency_model_version_id: UUID,
        applicant_id: UUID,
        applicant_email: str,
        applicant_display_name: str,
        submission_requirements: tuple[SubmissionRequirement, ...],
        token_hash: str,
        expires_at: datetime,
        recruiting_stage_id: UUID | None = None,
    ) -> Invitation:
        return cls(
            invitation_id=invitation_id,
            company_id=company_id,
            position_id=position_id,
            competency_model_version_id=competency_model_version_id,
            applicant_id=applicant_id,
            applicant_email_normalized=applicant_email,
            applicant_display_name=applicant_display_name,
            submission_requirements=submission_requirements,
            token_hash=token_hash,
            expires_at=expires_at,
            recruiting_stage_id=recruiting_stage_id,
        )

    def move_to_recruiting_stage(
        self,
        stage_id: UUID,
        *,
        expected_version: int,
    ) -> Invitation:
        if expected_version != self.pipeline_row_version:
            raise InvitationStateError("stale applicant pipeline version")
        if self.recruiting_stage_id == stage_id:
            return self
        return self.model_copy(
            update={
                "recruiting_stage_id": stage_id,
                "pipeline_row_version": self.pipeline_row_version + 1,
            }
        )

    def transition(
        self,
        target: InvitationStatus | str,
        *,
        actor_type: str,
        occurred_at: datetime,
        expected_version: int,
    ) -> Invitation:
        target_status = InvitationStatus(target)
        if expected_version != self.row_version:
            raise InvitationStateError("stale invitation version")
        if target_status not in ALLOWED_INVITATION_TRANSITIONS[self.status]:
            raise InvitationStateError(
                f"cannot transition invitation from {self.status} to {target_status}"
            )
        update: dict[str, object] = {
            "status": target_status,
            "last_state_actor_type": actor_type,
            "row_version": self.row_version + 1,
        }
        if target_status is InvitationStatus.IDENTITY_VERIFIED:
            update["identity_verified_at"] = occurred_at
        return self.model_copy(update=update)


class InvitationStateChange(BaseModel):
    model_config = ConfigDict(frozen=True)

    invitation_state_change_id: UUID
    company_id: UUID
    invitation_id: UUID
    from_status: InvitationStatus
    to_status: InvitationStatus
    actor_type: str
    occurred_at: datetime
    aggregate_version: int = Field(ge=2)
