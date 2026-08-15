from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsentRequiredError(PermissionError):
    """Raised when an applicant has not granted active purpose-specific consent."""


class ProcessingPurpose(StrEnum):
    DOCUMENT_ANALYSIS = "document_analysis"
    RECORDING = "recording"
    AI_ASSESSMENT = "ai_assessment"


class VerificationMethod(StrEnum):
    INVITATION_VALUE = "invitation_value"


class ApplicantProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    applicant_id: UUID
    company_id: UUID
    invitation_id: UUID
    display_name: str = Field(min_length=1, max_length=200)
    verification_method: VerificationMethod = VerificationMethod.INVITATION_VALUE
    technology_tags: tuple[str, ...] = ()


class ConsentRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    consent_record_id: UUID
    company_id: UUID
    invitation_id: UUID
    policy_version: str = Field(min_length=1, max_length=100)
    purposes: frozenset[ProcessingPurpose] = Field(min_length=1)
    retention_days: int = Field(ge=1, le=3650)
    accepted_at: datetime
    withdrawn_at: datetime | None = None
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @classmethod
    def accept(
        cls,
        *,
        consent_record_id: UUID,
        company_id: UUID,
        invitation_id: UUID,
        policy_version: str,
        purposes: tuple[ProcessingPurpose, ...],
        retention_days: int,
        accepted_at: datetime,
        evidence_digest: str,
    ) -> ConsentRecord:
        return cls(
            consent_record_id=consent_record_id,
            company_id=company_id,
            invitation_id=invitation_id,
            policy_version=policy_version,
            purposes=frozenset(purposes),
            retention_days=retention_days,
            accepted_at=accepted_at,
            evidence_digest=evidence_digest,
        )

    def withdraw(self, *, at: datetime) -> ConsentRecord:
        if at < self.accepted_at:
            raise ValueError("consent cannot be withdrawn before it is accepted")
        return self.model_copy(update={"withdrawn_at": at})


class ProcessingAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    invitation_id: UUID
    consent_record_id: UUID
    purpose: ProcessingPurpose
    expires_at: datetime


def require_processing_authorization(
    consent: ConsentRecord | None,
    purpose: ProcessingPurpose,
    *,
    at: datetime,
) -> ProcessingAuthorization:
    if consent is None or consent.withdrawn_at is not None or purpose not in consent.purposes:
        raise ConsentRequiredError("active purpose-specific consent is required")
    expires_at = consent.accepted_at + timedelta(days=consent.retention_days)
    if at >= expires_at:
        raise ConsentRequiredError("consent retention period has expired")
    return ProcessingAuthorization(
        company_id=consent.company_id,
        invitation_id=consent.invitation_id,
        consent_record_id=consent.consent_record_id,
        purpose=purpose,
        expires_at=expires_at,
    )
