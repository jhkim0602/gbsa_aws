from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.interview_engine.application.authorization import (
    InterviewAuthorizationDenied,
)
from interview_evidence.interview_engine.application.recording_service import (
    RecordingIntegrityError,
    RecordingUploadUnavailable,
)
from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.interview_engine.domain.session import (
    EquipmentComponent,
    EquipmentStatus,
)
from interview_evidence.interview_engine.repositories.postgres import (
    TenantScopedInterviewNotFound,
)
from interview_evidence.shared.audit import AuditAppender
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


class EquipmentComponentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EquipmentStatus
    sanitized_code: str | None = Field(default=None, max_length=100)


class EquipmentCheckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera: EquipmentComponentInput
    microphone: EquipmentComponentInput
    network: EquipmentComponentInput


class EquipmentCheckView(EquipmentCheckCreate):
    equipment_check_id: UUID
    overall_status: EquipmentStatus
    checked_at: datetime


class InterviewSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment_check_id: UUID
    strategy_id: UUID
    acknowledged_partial_analysis: bool


class InterviewSessionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interview_session_id: UUID
    state: str
    session_sequence: int
    websocket_path: str
    protocol_version: str


class InterviewResumeView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interview_session_id: UUID
    state: str
    server_sequence: int
    last_final_turn_id: UUID | None
    pending_turn: dict[str, object] | None
    last_verified_recording_chunk_sequence: int
    degraded_modes: tuple[str, ...]


class RecordingUploadIntentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_sequence: int = Field(ge=0)
    byte_size: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_start_ms: int = Field(ge=0)
    session_end_ms: int = Field(ge=1)


class UploadIntentView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    method: str
    url: str
    required_headers: dict[str, str]
    expires_at: datetime


class RecordingChunkView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recording_chunk_id: UUID
    chunk_sequence: int
    upload_status: str
    session_start_ms: int
    session_end_ms: int


class ApplicantScope(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    principal: ApplicantPrincipal
    context: TenantContext


def create_applicant_interview_router(
    *,
    principal_provider: PrincipalProvider,
    service: SessionApplicationService,
    audit: AuditAppender,
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    def applicant_scope(
        request: Request,
        session_cookie: Annotated[
            str | None,
            Cookie(alias="iep_applicant_session"),
        ] = None,
    ) -> ApplicantScope:
        if session_cookie is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            principal = principal_provider.get_applicant_principal(session_cookie)
        except PrincipalNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
        request_id = _optional_uuid(request.headers.get("x-request-id")) or principal.session_id
        return ApplicantScope(
            principal=principal,
            context=TenantContext(
                company_id=principal.company_id,
                actor_type=ActorType.APPLICANT,
                actor_id=principal.applicant_id,
                request_id=request_id,
                trace_id=request.headers.get("x-trace-id") or str(request_id),
            ),
        )

    IdempotencyKey = Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ]
    Scope = Annotated[ApplicantScope, Depends(applicant_scope)]

    @router.post(
        "/applicant/equipment-checks",
        response_model=EquipmentCheckView,
        status_code=status.HTTP_201_CREATED,
        operation_id="recordEquipmentCheck",
    )
    def record_equipment_check(
        body: EquipmentCheckCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> EquipmentCheckView:
        check = service.record_equipment_check(
            scope.context,
            scope.principal,
            camera=EquipmentComponent.model_validate(body.camera.model_dump()),
            microphone=EquipmentComponent.model_validate(body.microphone.model_dump()),
            network=EquipmentComponent.model_validate(body.network.model_dump()),
            idempotency_key=idempotency_key,
        )
        audit.append(
            scope.context,
            action="interview.equipment_checked",
            resource_type="equipment_check",
            resource_id=check.equipment_check_id,
            result=check.overall_status.value,
            metadata={
                "camera_status": check.camera.status.value,
                "microphone_status": check.microphone.status.value,
                "network_status": check.network.status.value,
            },
        )
        return EquipmentCheckView(
            equipment_check_id=check.equipment_check_id,
            camera=EquipmentComponentInput.model_validate(check.camera.model_dump()),
            microphone=EquipmentComponentInput.model_validate(check.microphone.model_dump()),
            network=EquipmentComponentInput.model_validate(check.network.model_dump()),
            overall_status=check.overall_status,
            checked_at=check.checked_at,
        )

    @router.post(
        "/applicant/interview-sessions",
        response_model=InterviewSessionView,
        status_code=status.HTTP_201_CREATED,
        operation_id="createInterviewSession",
    )
    def create_interview_session(
        body: InterviewSessionCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> InterviewSessionView:
        try:
            interview = service.create_session(
                scope.context,
                scope.principal,
                equipment_check_id=body.equipment_check_id,
                strategy_id=body.strategy_id,
                acknowledged_partial_analysis=body.acknowledged_partial_analysis,
                idempotency_key=idempotency_key,
            )
        except (InterviewAuthorizationDenied, PermissionError) as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from error
        except TenantScopedInterviewNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="interview.session_created",
            resource_type="interview_session",
            resource_id=interview.interview_session_id,
            result="created",
            metadata={
                "strategy_id": str(interview.interview_strategy_id),
                "criterion_version_id": str(interview.competency_model_version_id),
            },
        )
        return InterviewSessionView(
            interview_session_id=interview.interview_session_id,
            state=interview.state.value,
            session_sequence=interview.session_sequence,
            websocket_path=(
                f"/v1/applicant/interview-sessions/{interview.interview_session_id}/stream"
            ),
            protocol_version="1.0",
        )

    @router.get(
        "/applicant/interview-sessions/{session_id}/resume",
        response_model=InterviewResumeView,
        operation_id="getInterviewResumeSnapshot",
    )
    def get_resume(session_id: UUID, scope: Scope) -> InterviewResumeView:
        try:
            snapshot = service.resume(
                scope.context,
                scope.principal,
                session_id=session_id,
            )
        except TenantScopedInterviewNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except PermissionError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from error
        return InterviewResumeView.model_validate(snapshot.model_dump())

    @router.post(
        "/applicant/interview-sessions/{session_id}/media-upload-intents",
        response_model=UploadIntentView,
        status_code=status.HTTP_201_CREATED,
        operation_id="createRecordingUploadIntent",
    )
    def create_recording_upload_intent(
        session_id: UUID,
        body: RecordingUploadIntentCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> UploadIntentView:
        try:
            intent = service.create_recording_upload_intent(
                scope.context,
                scope.principal,
                session_id=session_id,
                sequence=body.chunk_sequence,
                byte_size=body.byte_size,
                content_hash=body.sha256,
                session_start_ms=body.session_start_ms,
                session_end_ms=body.session_end_ms,
                idempotency_key=idempotency_key,
            )
        except TenantScopedInterviewNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except PermissionError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from error
        except RecordingUploadUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "RECORDING_UPLOAD_UNAVAILABLE", "retryable": error.retryable},
            ) from error
        audit.append(
            scope.context,
            action="interview.recording_upload_intent_created",
            resource_type="recording_chunk",
            resource_id=intent.object_id,
            result="created",
            metadata={
                "session_id": str(session_id),
                "chunk_sequence": intent.sequence,
                "byte_size": intent.byte_size,
            },
        )
        # The presigned URL and its headers come from the storage adapter. Rebuilding them
        # here sent the browser to a host that does not exist, so no recording chunk ever
        # reached the bucket and every session finished with an empty timeline.
        return UploadIntentView(
            upload_id=intent.object_id,
            method=intent.method,
            url=intent.url,
            required_headers=intent.required_headers,
            expires_at=intent.expires_at or service.upload_intent_expires_at(),
        )

    @router.post(
        "/applicant/interview-sessions/{session_id}/media-uploads",
        response_model=RecordingChunkView,
        status_code=status.HTTP_201_CREATED,
        operation_id="confirmRecordingUpload",
    )
    def confirm_recording_upload(
        session_id: UUID,
        body: RecordingUploadIntentCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> RecordingChunkView:
        """Record a chunk the applicant has finished uploading.

        The same idempotency key as the intent returns that stored intent rather than
        issuing a second one, so this confirms exactly the upload that was authorized.
        """
        try:
            intent = service.create_recording_upload_intent(
                scope.context,
                scope.principal,
                session_id=session_id,
                sequence=body.chunk_sequence,
                byte_size=body.byte_size,
                content_hash=body.sha256,
                session_start_ms=body.session_start_ms,
                session_end_ms=body.session_end_ms,
                idempotency_key=idempotency_key,
            )
            chunk = service.confirm_recording_upload(
                scope.context,
                scope.principal,
                session_id=session_id,
                intent=intent,
            )
        except TenantScopedInterviewNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except PermissionError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from error
        except RecordingIntegrityError as error:
            # The object is missing or does not match what the intent declared. Retrying
            # the upload is the fix, so this is the applicant's error, not a server fault.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "RECORDING_CHUNK_NOT_VERIFIED", "retryable": True},
            ) from error
        except RecordingUploadUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "RECORDING_UPLOAD_UNAVAILABLE", "retryable": error.retryable},
            ) from error
        audit.append(
            scope.context,
            action="interview.recording_chunk_verified",
            resource_type="recording_chunk",
            resource_id=chunk.recording_chunk_id,
            result="verified",
            metadata={
                "session_id": str(session_id),
                "chunk_sequence": chunk.sequence,
                "byte_size": chunk.byte_size,
            },
        )
        return RecordingChunkView(
            recording_chunk_id=chunk.recording_chunk_id,
            chunk_sequence=chunk.sequence,
            upload_status=chunk.upload_status.value,
            session_start_ms=chunk.session_start_ms,
            session_end_ms=chunk.session_end_ms,
        )

    return router


def _optional_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
