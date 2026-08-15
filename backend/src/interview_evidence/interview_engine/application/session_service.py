from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from interview_evidence.interview_engine.application.authorization import (
    InterviewAuthorizationPort,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.idempotency import InMemoryIdempotencyStore
from interview_evidence.interview_engine.application.recording_service import (
    RecordingService,
    RecordingUploadIntent,
)
from interview_evidence.interview_engine.application.state_machine import SessionStateMachine
from interview_evidence.interview_engine.domain.session import (
    EquipmentCheck,
    EquipmentComponent,
    EquipmentStatus,
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    TurnSpeaker,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext


class ResumeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    interview_session_id: UUID
    state: str
    server_sequence: int
    last_final_turn_id: UUID | None
    pending_turn: dict[str, object] | None
    last_verified_recording_chunk_sequence: int
    degraded_modes: tuple[str, ...]


class SessionApplicationService:
    def __init__(
        self,
        *,
        repository: InterviewRepository,
        authorization: InterviewAuthorizationPort,
        idempotency: InMemoryIdempotencyStore,
        checkpoints: CheckpointService,
        reconciler: ContextReconciler,
        recording: RecordingService,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._authorization = authorization
        self._idempotency = idempotency
        self._checkpoints = checkpoints
        self._reconciler = reconciler
        self._recording = recording
        self._clock = clock
        self._state_machine = SessionStateMachine()

    def record_equipment_check(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        camera: EquipmentComponent,
        microphone: EquipmentComponent,
        network: EquipmentComponent,
        idempotency_key: str,
    ) -> EquipmentCheck:
        return self._idempotency.execute(
            context,
            session_id=principal.session_id,
            operation="equipment.check",
            idempotency_key=idempotency_key,
            request_payload={
                "camera_status": camera.status.value,
                "camera_code": camera.sanitized_code,
                "microphone_status": microphone.status.value,
                "microphone_code": microphone.sanitized_code,
                "network_status": network.status.value,
                "network_code": network.sanitized_code,
            },
            execute=lambda: self._record_equipment_once(
                context,
                principal,
                camera=camera,
                microphone=microphone,
                network=network,
            ),
            occurred_at=self._clock.now(),
        )

    def _record_equipment_once(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        camera: EquipmentComponent,
        microphone: EquipmentComponent,
        network: EquipmentComponent,
    ) -> EquipmentCheck:
        statuses = (camera.status, microphone.status, network.status)
        overall = (
            EquipmentStatus.FAILED
            if EquipmentStatus.FAILED in statuses
            else (
                EquipmentStatus.WARNING
                if EquipmentStatus.WARNING in statuses
                else EquipmentStatus.READY
            )
        )
        check = EquipmentCheck(
            equipment_check_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            invitation_id=principal.invitation_id,
            applicant_id=principal.applicant_id,
            camera=camera,
            microphone=microphone,
            network=network,
            overall_status=overall,
            checked_at=self._clock.now(),
        )
        return self._repository.save_equipment_check(context, check)

    def create_session(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        equipment_check_id: UUID,
        strategy_id: UUID,
        acknowledged_partial_analysis: bool,
        idempotency_key: str,
    ) -> InterviewSession:
        authorization = self._authorization.authorize_start(
            context,
            principal,
            strategy_id=strategy_id,
            acknowledged_partial_analysis=acknowledged_partial_analysis,
        )
        check = self._repository.get_equipment_check(context, equipment_check_id)
        if (
            check.invitation_id != principal.invitation_id
            or check.applicant_id != principal.applicant_id
            or check.overall_status is EquipmentStatus.FAILED
        ):
            raise PermissionError("equipment check is not authorized for session start")
        return self._idempotency.execute(
            context,
            session_id=principal.session_id,
            operation="interview.session.create",
            idempotency_key=idempotency_key,
            request_payload={
                "equipment_check_id": str(equipment_check_id),
                "strategy_id": str(strategy_id),
                "acknowledged_partial_analysis": acknowledged_partial_analysis,
            },
            execute=lambda: self._create_session_once(
                context,
                principal,
                strategy_id=strategy_id,
                competency_model_version_id=authorization.competency_model_version_id,
            ),
            occurred_at=self._clock.now(),
        )

    def _create_session_once(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        strategy_id: UUID,
        competency_model_version_id: UUID,
    ) -> InterviewSession:
        session = self._repository.save_session(
            context,
            InterviewSession(
                interview_session_id=new_uuid7(self._clock.now()),
                company_id=context.company_id,
                invitation_id=principal.invitation_id,
                applicant_id=principal.applicant_id,
                interview_strategy_id=strategy_id,
                competency_model_version_id=competency_model_version_id,
                created_at=self._clock.now(),
            ),
        )
        self._checkpoints.create(
            context,
            session_id=session.interview_session_id,
            last_final_turn_id=None,
            last_media_chunk_sequence=0,
            pending_turn_id=None,
            hot_view_sync_status=HotViewSyncStatus.PENDING,
            occurred_at=self._clock.now(),
        )
        return session

    def resume(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        session_id: UUID,
    ) -> ResumeSnapshot:
        session = self._authorized_session(context, principal, session_id)
        reconciled = self._reconciler.get_or_rebuild(
            context,
            session_id=session_id,
            last_reconciled_event_id=None,
        )
        pending_turn: dict[str, object] | None = None
        if reconciled.pending_turn_id is not None:
            turn = self._repository.get_turn(context, reconciled.pending_turn_id)
            pending_turn = {
                "turn_id": str(turn.turn_id),
                "speaker": turn.speaker.value,
                "status": turn.status.value,
            }
        return ResumeSnapshot(
            interview_session_id=session_id,
            state=session.state.value,
            server_sequence=session.session_sequence,
            last_final_turn_id=reconciled.last_final_turn_id,
            pending_turn=pending_turn,
            last_verified_recording_chunk_sequence=reconciled.last_media_chunk_sequence,
            degraded_modes=tuple(
                dict.fromkeys((*session.degraded_modes, *reconciled.degraded_modes))
            ),
        )

    def start_session(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        session_id: UUID,
        expected_sequence: int,
        idempotency_key: str,
    ) -> InterviewSession:
        self._authorized_session(context, principal, session_id)
        return self._idempotency.execute(
            context,
            session_id=session_id,
            operation="session.start",
            idempotency_key=idempotency_key,
            request_payload={"expected_sequence": expected_sequence},
            execute=lambda: self._start_session_once(
                context,
                session_id=session_id,
                expected_sequence=expected_sequence,
            ),
            occurred_at=self._clock.now(),
        )

    def _start_session_once(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
    ) -> InterviewSession:
        current = self._repository.get_session(context, session_id)
        started = self._state_machine.transition(
            current,
            expected_sequence=expected_sequence,
            target=InterviewSessionState.IN_PROGRESS,
        )
        self._repository.save_session(context, started)
        self._checkpoints.create(
            context,
            session_id=session_id,
            last_final_turn_id=None,
            last_media_chunk_sequence=0,
            pending_turn_id=None,
            hot_view_sync_status=HotViewSyncStatus.PENDING,
            occurred_at=self._clock.now(),
        )
        return started

    def repeat_question(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        session_id: UUID,
        question_turn_id: UUID,
    ) -> InterviewTurn:
        self._authorized_session(context, principal, session_id)
        turn = self._repository.get_turn(context, question_turn_id)
        if turn.interview_session_id != session_id or turn.speaker is not TurnSpeaker.INTERVIEWER:
            raise LookupError("question turn not found")
        return turn

    def create_recording_upload_intent(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        session_id: UUID,
        sequence: int,
        byte_size: int,
        content_hash: str,
        session_start_ms: int,
        session_end_ms: int,
        idempotency_key: str,
    ) -> RecordingUploadIntent:
        self._authorized_session(context, principal, session_id)
        return self._idempotency.execute(
            context,
            session_id=session_id,
            operation="recording.upload",
            idempotency_key=idempotency_key,
            request_payload={
                "sequence": sequence,
                "byte_size": byte_size,
                "content_hash": content_hash,
                "session_start_ms": session_start_ms,
                "session_end_ms": session_end_ms,
            },
            execute=lambda: self._recording.issue_upload_intent(
                context,
                session_id=session_id,
                sequence=sequence,
                byte_size=byte_size,
                content_hash=content_hash,
                session_start_ms=session_start_ms,
                session_end_ms=session_end_ms,
                idempotency_key=idempotency_key,
                occurred_at=self._clock.now(),
            ),
            occurred_at=self._clock.now(),
        )

    def upload_intent_expires_at(self) -> datetime:
        return self._clock.now() + timedelta(minutes=15)

    def _authorized_session(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        session_id: UUID,
    ) -> InterviewSession:
        session = self._repository.get_session(context, session_id)
        if (
            session.company_id != principal.company_id
            or session.invitation_id != principal.invitation_id
            or session.applicant_id != principal.applicant_id
        ):
            raise PermissionError("interview session is outside applicant scope")
        return session
