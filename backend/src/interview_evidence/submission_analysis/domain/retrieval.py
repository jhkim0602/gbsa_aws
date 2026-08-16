from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VerificationTargetType(StrEnum):
    NOT_MENTIONED = "not_mentioned"
    CLAIM_FOUND = "claim_found"
    DETAIL_MISSING = "detail_missing"
    SOURCE_CONFLICT = "source_conflict"
    OWNERSHIP_UNCERTAIN = "ownership_uncertain"


class CandidateClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_claim_id: UUID
    company_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    competency_model_version_id: UUID
    criterion_id: UUID
    claim_type: str = Field(min_length=1, max_length=40)
    neutral_text: str = Field(min_length=1, max_length=4000)
    source_id: UUID
    locator: dict[str, object]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    extraction_version: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)


class ClaimConflict(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_conflict_id: UUID
    company_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    criterion_id: UUID
    left_claim_id: UUID
    right_claim_id: UUID
    conflict_type: str = Field(min_length=1, max_length=50)
    verification_objective: str = Field(min_length=1, max_length=4000)


class VerificationTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_target_id: UUID
    company_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    competency_model_version_id: UUID
    criterion_id: UUID
    target_type: VerificationTargetType
    objective: str = Field(min_length=1, max_length=4000)
    missing_dimensions: tuple[str, ...] = ()
    priority: int = Field(ge=1)
    max_follow_ups: int = Field(ge=0, le=3)
    source_reference_candidates: tuple[UUID, ...] = ()


class CandidateVerificationMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_verification_map_id: UUID
    company_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    competency_model_version_id: UUID
    criterion_version: int = Field(ge=1)
    material_version: str
    retrieval_version: str
    embedding_model: str
    embedding_version: str
    generation_version: str
    ordered_target_ids: tuple[UUID, ...]
    time_budget_seconds: int = Field(ge=60)
    readiness_state: str
    created_at: datetime
