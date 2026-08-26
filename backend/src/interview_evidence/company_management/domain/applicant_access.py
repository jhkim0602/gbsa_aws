from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsentRequiredError(PermissionError):
    """Raised when an applicant has not granted active purpose-specific consent."""


class ProcessingPurpose(StrEnum):
    DOCUMENT_ANALYSIS = "document_analysis"
    RECORDING = "recording"
    AI_ASSESSMENT = "ai_assessment"


class ConsentPolicyPurpose(BaseModel):
    model_config = ConfigDict(frozen=True)

    purpose: ProcessingPurpose
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ConsentPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_version: str = Field(min_length=1, max_length=100)
    ai_role: str = Field(min_length=1)
    recording_notice: str = Field(min_length=1)
    processing_purposes: tuple[ConsentPolicyPurpose, ...] = Field(min_length=1)
    retention_days: int = Field(ge=1, le=3650)
    deletion_method: str = Field(min_length=1)
    required_purposes: frozenset[ProcessingPurpose] = Field(min_length=1)

    @property
    def content_digest(self) -> str:
        payload = self.model_dump(mode="json")
        payload["required_purposes"] = sorted(payload["required_purposes"])
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(encoded.encode("utf-8")).hexdigest()


DEFAULT_CONSENT_POLICY = ConsentPolicy(
    policy_version="2026-08-v1",
    ai_role=(
        "AI는 지원자 자료를 바탕으로 질문과 평가 초안을 만들지만 "
        "최종 채용 결정은 기업의 사람이 수행합니다."
    ),
    recording_notice=(
        "면접 중 음성과 영상이 녹화되며 답변 자막과 Evidence 재생 구간을 만드는 데 사용됩니다."
    ),
    processing_purposes=(
        ConsentPolicyPurpose(
            purpose=ProcessingPurpose.DOCUMENT_ANALYSIS,
            title="문서 분석",
            description="제출한 이력서와 공개 저장소를 질문 준비와 사실 확인에 사용합니다.",
        ),
        ConsentPolicyPurpose(
            purpose=ProcessingPurpose.RECORDING,
            title="면접 녹화",
            description="면접 영상과 음성을 자막, 복구, 사람 검토를 위해 저장합니다.",
        ),
        ConsentPolicyPurpose(
            purpose=ProcessingPurpose.AI_ASSESSMENT,
            title="AI 평가 보조",
            description="최종 답변 근거로 평가 초안을 만들며 기술 장애 구간은 평가에서 제외합니다.",
        ),
    ),
    retention_days=180,
    deletion_method=(
        "기업의 삭제 요청 또는 보관기간 만료 시 PostgreSQL, S3, "
        "검색 인덱스의 원본과 파생 데이터를 확인하며 삭제합니다."
    ),
    required_purposes=frozenset(ProcessingPurpose),
)


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
