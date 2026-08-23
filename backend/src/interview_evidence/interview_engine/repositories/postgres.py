from __future__ import annotations

from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    delete,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    InstrumentedAttribute,
    Mapped,
    Session,
    mapped_column,
)

from interview_evidence.interview_engine.domain.session import (
    EquipmentCheck,
    EquipmentComponent,
    EquipmentStatus,
    InterviewSession,
)
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    QuestionRationale,
    QuestionSourceReference,
    RecordingChunk,
    RecordingUploadStatus,
    SessionCheckpoint,
    TurnSpeaker,
    TurnStatus,
    VerificationProgress,
    VerificationProgressState,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class TenantScopedInterviewNotFound(LookupError):
    """Raised without revealing another tenant's interview resource."""


class TenantOwned(Protocol):
    @property
    def company_id(self) -> UUID: ...


TenantOwnedT = TypeVar("TenantOwnedT", bound=TenantOwned)


class Base(DeclarativeBase):
    pass


class EquipmentCheckRow(Base):
    __tablename__ = "equipment_checks"
    __table_args__ = (Index("ix_equipment_checks_invitation", "company_id", "invitation_id"),)

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    equipment_check_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid)
    applicant_id: Mapped[UUID] = mapped_column(Uuid)
    camera_status: Mapped[str] = mapped_column(String(30))
    camera_sanitized_code: Mapped[str | None] = mapped_column(String(100))
    microphone_status: Mapped[str] = mapped_column(String(30))
    microphone_sanitized_code: Mapped[str | None] = mapped_column(String(100))
    network_status: Mapped[str] = mapped_column(String(30))
    network_sanitized_code: Mapped[str | None] = mapped_column(String(100))
    overall_status: Mapped[str] = mapped_column(String(30))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewSessionRow(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        UniqueConstraint("company_id", "invitation_id", name="uq_interview_sessions_invitation"),
    )

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid)
    applicant_id: Mapped[UUID] = mapped_column(Uuid)
    interview_strategy_id: Mapped[UUID] = mapped_column(Uuid)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(40))
    session_sequence: Mapped[int] = mapped_column(Integer)
    row_version: Mapped[int] = mapped_column(Integer)
    degraded_modes: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InterviewTurnRow(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
            name="fk_interview_turns_company_id_interview_sessions",
        ),
        UniqueConstraint(
            "company_id",
            "interview_session_id",
            "idempotency_key",
            name="uq_interview_turns_idempotency",
        ),
        UniqueConstraint(
            "company_id", "interview_session_id", "sequence", name="uq_interview_turns_sequence"
        ),
    )

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    text: Mapped[str | None] = mapped_column(Text)
    target_criterion_id: Mapped[UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    model_config_version: Mapped[str | None] = mapped_column(String(100))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionCheckpointRow(Base):
    __tablename__ = "session_checkpoints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
            name="fk_session_checkpoints_company_id_interview_sessions",
        ),
        UniqueConstraint(
            "company_id",
            "interview_session_id",
            "session_sequence",
            name="uq_session_checkpoints_sequence",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    checkpoint_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid)
    session_sequence: Mapped[int] = mapped_column(Integer)
    last_final_turn_id: Mapped[UUID | None] = mapped_column(Uuid)
    last_media_chunk_sequence: Mapped[int] = mapped_column(Integer)
    pending_turn_id: Mapped[UUID | None] = mapped_column(Uuid)
    hot_view_sync_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecordingChunkRow(Base):
    __tablename__ = "recording_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
            name="fk_recording_chunks_company_id_interview_sessions",
        ),
        UniqueConstraint(
            "company_id",
            "interview_session_id",
            "idempotency_key",
            name="uq_recording_chunks_idempotency",
        ),
        UniqueConstraint(
            "company_id", "interview_session_id", "sequence", name="uq_recording_chunks_sequence"
        ),
    )

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    recording_chunk_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(2048))
    content_hash: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    session_start_ms: Mapped[int] = mapped_column(Integer)
    session_end_ms: Mapped[int] = mapped_column(Integer)
    upload_status: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionSourceReferenceRow(Base):
    __tablename__ = "question_source_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
            name="fk_question_source_references_company_id_interview_sessions",
        ),
        ForeignKeyConstraint(
            ["company_id", "question_turn_id"],
            ["interview_turns.company_id", "interview_turns.turn_id"],
            name="fk_question_source_references_company_id_interview_turns",
        ),
        UniqueConstraint(
            "company_id",
            "question_turn_id",
            "source_id",
            name="uq_question_source_references_source",
        ),
        Index("ix_question_source_references_session", "company_id", "interview_session_id"),
    )

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_reference_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid)
    question_turn_id: Mapped[UUID] = mapped_column(Uuid)
    source_id: Mapped[UUID] = mapped_column(Uuid)
    source_type: Mapped[str] = mapped_column(String(100))
    locator: Mapped[dict[str, object]] = mapped_column(JSON)
    excerpt: Mapped[str] = mapped_column(String(2000), default="")
    relevance_score: Mapped[float]
    ownership_confidence: Mapped[float]
    retrieval_config_version: Mapped[str] = mapped_column(String(100))
    model_config_version: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VerificationProgressRow(Base):
    __tablename__ = "verification_progress"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "interview_session_id",
            "verification_target_id",
            name="uq_verification_progress_target",
        ),
        Index("ix_verification_progress_session", "company_id", "interview_session_id"),
    )

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    verification_progress_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid)
    applicant_id: Mapped[UUID] = mapped_column(Uuid)
    verification_target_id: Mapped[UUID] = mapped_column(Uuid)
    criterion_id: Mapped[UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(40))
    follow_up_count: Mapped[int] = mapped_column(Integer)
    final_answer_turn_ids: Mapped[list[str]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionRationaleRow(Base):
    __tablename__ = "question_rationales"
    __table_args__ = (
        UniqueConstraint("company_id", "question_turn_id", name="uq_question_rationale_turn"),
        Index("ix_question_rationales_session", "company_id", "interview_session_id"),
    )

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    question_rationale_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid)
    question_turn_id: Mapped[UUID] = mapped_column(Uuid)
    applicant_id: Mapped[UUID] = mapped_column(Uuid)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid)
    criterion_id: Mapped[UUID] = mapped_column(Uuid)
    verification_target_id: Mapped[UUID] = mapped_column(Uuid)
    verification_target_type: Mapped[str] = mapped_column(String(40))
    objective: Mapped[str] = mapped_column(String(4000))
    question_type: Mapped[str] = mapped_column(String(40))
    interview_stage: Mapped[str] = mapped_column(String(40), server_default="technical")
    retrieval_version: Mapped[str] = mapped_column(String(100))
    generation_version: Mapped[str] = mapped_column(String(100))
    policy_result: Mapped[str] = mapped_column(String(100))
    source_reference_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewRepository(Protocol):
    def save_equipment_check(
        self, context: TenantContext, check: EquipmentCheck
    ) -> EquipmentCheck: ...
    def get_equipment_check(
        self, context: TenantContext, equipment_check_id: UUID
    ) -> EquipmentCheck: ...
    def save_session(
        self, context: TenantContext, session: InterviewSession
    ) -> InterviewSession: ...
    def get_session(self, context: TenantContext, session_id: UUID) -> InterviewSession: ...
    def find_session_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> InterviewSession | None: ...
    def save_turn(self, context: TenantContext, turn: InterviewTurn) -> InterviewTurn: ...
    def get_turn(self, context: TenantContext, turn_id: UUID) -> InterviewTurn: ...
    def list_turns(self, context: TenantContext, session_id: UUID) -> tuple[InterviewTurn, ...]: ...
    def list_final_turns(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[InterviewTurn, ...]: ...
    def save_checkpoint(
        self, context: TenantContext, checkpoint: SessionCheckpoint
    ) -> SessionCheckpoint: ...
    def latest_checkpoint(
        self, context: TenantContext, session_id: UUID
    ) -> SessionCheckpoint | None: ...
    def list_checkpoints(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[SessionCheckpoint, ...]: ...
    def save_recording_chunk(
        self, context: TenantContext, chunk: RecordingChunk
    ) -> RecordingChunk: ...
    def list_recording_chunks(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[RecordingChunk, ...]: ...
    def save_question_source_references(
        self,
        context: TenantContext,
        references: tuple[QuestionSourceReference, ...],
    ) -> tuple[QuestionSourceReference, ...]: ...
    def list_question_source_references(
        self,
        context: TenantContext,
        *,
        question_turn_id: UUID,
    ) -> tuple[QuestionSourceReference, ...]: ...
    def list_session_source_references(
        self,
        context: TenantContext,
        session_id: UUID,
    ) -> tuple[QuestionSourceReference, ...]: ...
    def save_verification_progress(
        self,
        context: TenantContext,
        progress: VerificationProgress,
    ) -> VerificationProgress: ...
    def list_verification_progress(
        self,
        context: TenantContext,
        session_id: UUID,
    ) -> tuple[VerificationProgress, ...]: ...
    def save_question_rationale(
        self,
        context: TenantContext,
        rationale: QuestionRationale,
    ) -> QuestionRationale: ...
    def get_question_rationale(
        self,
        context: TenantContext,
        *,
        question_turn_id: UUID,
    ) -> QuestionRationale | None: ...
    def list_question_rationales(
        self,
        context: TenantContext,
        session_id: UUID,
    ) -> tuple[QuestionRationale, ...]: ...
    def delete_and_verify_target(
        self,
        context: TenantContext,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> bool: ...


class SqlAlchemyInterviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _delete_row(
        self,
        context: TenantContext,
        *,
        row_type: type[Base],
        company_column: InstrumentedAttribute[UUID],
        id_column: InstrumentedAttribute[UUID],
        resource_id: UUID,
    ) -> bool:
        tenant = require_tenant_context(context)
        predicate = (
            company_column == tenant.company_id,
            id_column == resource_id,
        )
        self._session.execute(delete(row_type).where(*predicate))
        self._session.flush()
        return self._session.scalar(select(row_type).where(*predicate)) is None

    def save_session(self, context: TenantContext, interview: InterviewSession) -> InterviewSession:
        require_tenant_context(context).assert_company(interview.company_id)
        self._session.merge(
            InterviewSessionRow(
                interview_session_id=interview.interview_session_id,
                company_id=interview.company_id,
                invitation_id=interview.invitation_id,
                applicant_id=interview.applicant_id,
                interview_strategy_id=interview.interview_strategy_id,
                competency_model_version_id=interview.competency_model_version_id,
                state=interview.state.value,
                session_sequence=interview.session_sequence,
                row_version=interview.row_version,
                degraded_modes=list(interview.degraded_modes),
                created_at=interview.created_at,
                started_at=interview.started_at,
                completed_at=interview.completed_at,
            )
        )
        self._session.flush()
        return interview

    def save_equipment_check(self, context: TenantContext, check: EquipmentCheck) -> EquipmentCheck:
        require_tenant_context(context).assert_company(check.company_id)
        self._session.merge(
            EquipmentCheckRow(
                equipment_check_id=check.equipment_check_id,
                company_id=check.company_id,
                invitation_id=check.invitation_id,
                applicant_id=check.applicant_id,
                camera_status=check.camera.status.value,
                camera_sanitized_code=check.camera.sanitized_code,
                microphone_status=check.microphone.status.value,
                microphone_sanitized_code=check.microphone.sanitized_code,
                network_status=check.network.status.value,
                network_sanitized_code=check.network.sanitized_code,
                overall_status=check.overall_status.value,
                checked_at=check.checked_at,
            )
        )
        self._session.flush()
        return check

    def get_equipment_check(
        self, context: TenantContext, equipment_check_id: UUID
    ) -> EquipmentCheck:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(EquipmentCheckRow).where(
                EquipmentCheckRow.company_id == tenant.company_id,
                EquipmentCheckRow.equipment_check_id == equipment_check_id,
            )
        )
        if row is None:
            raise TenantScopedInterviewNotFound("interview resource not found")
        return EquipmentCheck(
            equipment_check_id=row.equipment_check_id,
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            applicant_id=row.applicant_id,
            camera=EquipmentComponent(
                status=EquipmentStatus(row.camera_status),
                sanitized_code=row.camera_sanitized_code,
            ),
            microphone=EquipmentComponent(
                status=EquipmentStatus(row.microphone_status),
                sanitized_code=row.microphone_sanitized_code,
            ),
            network=EquipmentComponent(
                status=EquipmentStatus(row.network_status),
                sanitized_code=row.network_sanitized_code,
            ),
            overall_status=EquipmentStatus(row.overall_status),
            checked_at=row.checked_at,
        )

    def get_session(self, context: TenantContext, session_id: UUID) -> InterviewSession:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(InterviewSessionRow).where(
                InterviewSessionRow.company_id == tenant.company_id,
                InterviewSessionRow.interview_session_id == session_id,
            )
        )
        if row is None:
            raise TenantScopedInterviewNotFound("interview resource not found")
        return self._session_domain(row)

    def find_session_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> InterviewSession | None:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(InterviewSessionRow)
            .where(
                InterviewSessionRow.company_id == tenant.company_id,
                InterviewSessionRow.invitation_id == invitation_id,
            )
            .order_by(InterviewSessionRow.created_at.desc())
        )
        return None if row is None else self._session_domain(row)

    def save_turn(self, context: TenantContext, turn: InterviewTurn) -> InterviewTurn:
        require_tenant_context(context).assert_company(turn.company_id)
        self.get_session(context, turn.interview_session_id)
        self._session.merge(
            InterviewTurnRow(
                turn_id=turn.turn_id,
                company_id=turn.company_id,
                interview_session_id=turn.interview_session_id,
                sequence=turn.sequence,
                speaker=turn.speaker.value,
                status=turn.status.value,
                text=turn.text,
                target_criterion_id=turn.target_criterion_id,
                idempotency_key=turn.idempotency_key,
                model_config_version=turn.model_config_version,
                finalized_at=turn.finalized_at,
            )
        )
        self._session.flush()
        return turn

    def get_turn(self, context: TenantContext, turn_id: UUID) -> InterviewTurn:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(InterviewTurnRow).where(
                InterviewTurnRow.company_id == tenant.company_id,
                InterviewTurnRow.turn_id == turn_id,
            )
        )
        if row is None:
            raise TenantScopedInterviewNotFound("interview resource not found")
        return self._turn_domain(row)

    def list_turns(self, context: TenantContext, session_id: UUID) -> tuple[InterviewTurn, ...]:
        tenant = require_tenant_context(context)
        self.get_session(context, session_id)
        rows = self._session.scalars(
            select(InterviewTurnRow)
            .where(
                InterviewTurnRow.company_id == tenant.company_id,
                InterviewTurnRow.interview_session_id == session_id,
            )
            .order_by(InterviewTurnRow.sequence)
        )
        return tuple(self._turn_domain(row) for row in rows)

    def list_final_turns(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[InterviewTurn, ...]:
        return tuple(
            turn for turn in self.list_turns(context, session_id) if turn.status is TurnStatus.FINAL
        )

    def save_checkpoint(
        self, context: TenantContext, checkpoint: SessionCheckpoint
    ) -> SessionCheckpoint:
        require_tenant_context(context).assert_company(checkpoint.company_id)
        self.get_session(context, checkpoint.interview_session_id)
        self._session.merge(
            SessionCheckpointRow(
                checkpoint_id=checkpoint.checkpoint_id,
                company_id=checkpoint.company_id,
                interview_session_id=checkpoint.interview_session_id,
                session_sequence=checkpoint.session_sequence,
                last_final_turn_id=checkpoint.last_final_turn_id,
                last_media_chunk_sequence=checkpoint.last_media_chunk_sequence,
                pending_turn_id=checkpoint.pending_turn_id,
                hot_view_sync_status=checkpoint.hot_view_sync_status.value,
                created_at=checkpoint.created_at,
            )
        )
        self._session.flush()
        return checkpoint

    def latest_checkpoint(
        self, context: TenantContext, session_id: UUID
    ) -> SessionCheckpoint | None:
        tenant = require_tenant_context(context)
        self.get_session(context, session_id)
        row = self._session.scalar(
            select(SessionCheckpointRow)
            .where(
                SessionCheckpointRow.company_id == tenant.company_id,
                SessionCheckpointRow.interview_session_id == session_id,
            )
            .order_by(
                SessionCheckpointRow.session_sequence.desc(),
                SessionCheckpointRow.created_at.desc(),
            )
            .limit(1)
        )
        return None if row is None else self._checkpoint_domain(row)

    def list_checkpoints(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[SessionCheckpoint, ...]:
        tenant = require_tenant_context(context)
        self.get_session(context, session_id)
        rows = self._session.scalars(
            select(SessionCheckpointRow)
            .where(
                SessionCheckpointRow.company_id == tenant.company_id,
                SessionCheckpointRow.interview_session_id == session_id,
            )
            .order_by(
                SessionCheckpointRow.session_sequence,
                SessionCheckpointRow.created_at,
            )
        )
        return tuple(self._checkpoint_domain(row) for row in rows)

    def save_recording_chunk(self, context: TenantContext, chunk: RecordingChunk) -> RecordingChunk:
        require_tenant_context(context).assert_company(chunk.company_id)
        self.get_session(context, chunk.interview_session_id)
        self._session.merge(
            RecordingChunkRow(
                recording_chunk_id=chunk.recording_chunk_id,
                company_id=chunk.company_id,
                interview_session_id=chunk.interview_session_id,
                sequence=chunk.sequence,
                object_key=chunk.object_key,
                content_hash=chunk.content_hash,
                byte_size=chunk.byte_size,
                session_start_ms=chunk.session_start_ms,
                session_end_ms=chunk.session_end_ms,
                upload_status=chunk.upload_status.value,
                idempotency_key=chunk.idempotency_key,
                created_at=chunk.created_at,
            )
        )
        self._session.flush()
        return chunk

    def list_recording_chunks(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[RecordingChunk, ...]:
        tenant = require_tenant_context(context)
        self.get_session(context, session_id)
        rows = self._session.scalars(
            select(RecordingChunkRow)
            .where(
                RecordingChunkRow.company_id == tenant.company_id,
                RecordingChunkRow.interview_session_id == session_id,
            )
            .order_by(RecordingChunkRow.sequence)
        )
        return tuple(self._chunk_domain(row) for row in rows)

    def save_question_source_references(
        self,
        context: TenantContext,
        references: tuple[QuestionSourceReference, ...],
    ) -> tuple[QuestionSourceReference, ...]:
        for reference in references:
            require_tenant_context(context).assert_company(reference.company_id)
            self.get_session(context, reference.interview_session_id)
            self.get_turn(context, reference.question_turn_id)
            self._session.merge(
                QuestionSourceReferenceRow(
                    source_reference_id=reference.source_reference_id,
                    company_id=reference.company_id,
                    interview_session_id=reference.interview_session_id,
                    question_turn_id=reference.question_turn_id,
                    source_id=reference.source_id,
                    source_type=reference.source_type,
                    locator=dict(reference.locator),
                    excerpt=reference.excerpt,
                    relevance_score=reference.relevance_score,
                    ownership_confidence=reference.ownership_confidence,
                    retrieval_config_version=reference.retrieval_config_version,
                    model_config_version=reference.model_config_version,
                    created_at=reference.created_at,
                )
            )
        self._session.flush()
        return references

    def list_question_source_references(
        self,
        context: TenantContext,
        *,
        question_turn_id: UUID,
    ) -> tuple[QuestionSourceReference, ...]:
        tenant = require_tenant_context(context)
        self.get_turn(context, question_turn_id)
        rows = self._session.scalars(
            select(QuestionSourceReferenceRow).where(
                QuestionSourceReferenceRow.company_id == tenant.company_id,
                QuestionSourceReferenceRow.question_turn_id == question_turn_id,
            )
        )
        return tuple(self._source_reference_domain(row) for row in rows)

    def save_verification_progress(
        self,
        context: TenantContext,
        progress: VerificationProgress,
    ) -> VerificationProgress:
        require_tenant_context(context).assert_company(progress.company_id)
        self.get_session(context, progress.interview_session_id)
        existing = self._session.scalar(
            select(VerificationProgressRow).where(
                VerificationProgressRow.company_id == progress.company_id,
                VerificationProgressRow.interview_session_id == progress.interview_session_id,
                VerificationProgressRow.verification_target_id == progress.verification_target_id,
            )
        )
        row_id = (
            existing.verification_progress_id
            if existing is not None
            else progress.verification_progress_id
        )
        self._session.merge(
            VerificationProgressRow(
                verification_progress_id=row_id,
                company_id=progress.company_id,
                interview_session_id=progress.interview_session_id,
                applicant_id=progress.applicant_id,
                verification_target_id=progress.verification_target_id,
                criterion_id=progress.criterion_id,
                state=progress.state.value,
                follow_up_count=progress.follow_up_count,
                final_answer_turn_ids=[str(value) for value in progress.final_answer_turn_ids],
                updated_at=progress.updated_at,
            )
        )
        self._session.flush()
        return progress.model_copy(update={"verification_progress_id": row_id})

    def list_verification_progress(
        self,
        context: TenantContext,
        session_id: UUID,
    ) -> tuple[VerificationProgress, ...]:
        tenant = require_tenant_context(context)
        self.get_session(context, session_id)
        rows = self._session.scalars(
            select(VerificationProgressRow)
            .where(
                VerificationProgressRow.company_id == tenant.company_id,
                VerificationProgressRow.interview_session_id == session_id,
            )
            .order_by(VerificationProgressRow.updated_at)
        )
        return tuple(self._verification_progress_domain(row) for row in rows)

    def save_question_rationale(
        self,
        context: TenantContext,
        rationale: QuestionRationale,
    ) -> QuestionRationale:
        require_tenant_context(context).assert_company(rationale.company_id)
        self.get_session(context, rationale.interview_session_id)
        self._session.merge(
            QuestionRationaleRow(
                question_rationale_id=rationale.question_rationale_id,
                company_id=rationale.company_id,
                interview_session_id=rationale.interview_session_id,
                question_turn_id=rationale.question_turn_id,
                applicant_id=rationale.applicant_id,
                competency_model_version_id=(rationale.competency_model_version_id),
                criterion_id=rationale.criterion_id,
                verification_target_id=rationale.verification_target_id,
                verification_target_type=rationale.verification_target_type,
                objective=rationale.objective,
                question_type=rationale.question_type,
                interview_stage=rationale.interview_stage,
                retrieval_version=rationale.retrieval_version,
                generation_version=rationale.generation_version,
                policy_result=rationale.policy_result,
                source_reference_ids=[str(value) for value in rationale.source_reference_ids],
                created_at=rationale.created_at,
            )
        )
        self._session.flush()
        return rationale

    def get_question_rationale(
        self,
        context: TenantContext,
        *,
        question_turn_id: UUID,
    ) -> QuestionRationale | None:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(QuestionRationaleRow).where(
                QuestionRationaleRow.company_id == tenant.company_id,
                QuestionRationaleRow.question_turn_id == question_turn_id,
            )
        )
        return None if row is None else self._question_rationale_domain(row)

    def list_question_rationales(
        self,
        context: TenantContext,
        session_id: UUID,
    ) -> tuple[QuestionRationale, ...]:
        tenant = require_tenant_context(context)
        self.get_session(context, session_id)
        rows = self._session.scalars(
            select(QuestionRationaleRow)
            .where(
                QuestionRationaleRow.company_id == tenant.company_id,
                QuestionRationaleRow.interview_session_id == session_id,
            )
            .order_by(QuestionRationaleRow.created_at)
        )
        return tuple(self._question_rationale_domain(row) for row in rows)

    def delete_and_verify_target(
        self,
        context: TenantContext,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> bool:
        row: tuple[
            type[Base],
            InstrumentedAttribute[UUID],
            InstrumentedAttribute[UUID],
        ]
        if resource_type == "interview_session":
            row = (
                InterviewSessionRow,
                InterviewSessionRow.company_id,
                InterviewSessionRow.interview_session_id,
            )
        elif resource_type == "interview_turn":
            row = (
                InterviewTurnRow,
                InterviewTurnRow.company_id,
                InterviewTurnRow.turn_id,
            )
        elif resource_type == "session_checkpoint":
            row = (
                SessionCheckpointRow,
                SessionCheckpointRow.company_id,
                SessionCheckpointRow.checkpoint_id,
            )
        elif resource_type == "question_source_reference":
            row = (
                QuestionSourceReferenceRow,
                QuestionSourceReferenceRow.company_id,
                QuestionSourceReferenceRow.source_reference_id,
            )
        elif resource_type == "recording_chunk":
            row = (
                RecordingChunkRow,
                RecordingChunkRow.company_id,
                RecordingChunkRow.recording_chunk_id,
            )
        elif resource_type == "verification_progress":
            row = (
                VerificationProgressRow,
                VerificationProgressRow.company_id,
                VerificationProgressRow.verification_progress_id,
            )
        elif resource_type == "question_rationale":
            row = (
                QuestionRationaleRow,
                QuestionRationaleRow.company_id,
                QuestionRationaleRow.question_rationale_id,
            )
        else:
            raise ValueError("unsupported interview deletion target")
        return self._delete_row(
            context,
            row_type=row[0],
            company_column=row[1],
            id_column=row[2],
            resource_id=resource_id,
        )

    def list_session_source_references(
        self,
        context: TenantContext,
        session_id: UUID,
    ) -> tuple[QuestionSourceReference, ...]:
        tenant = require_tenant_context(context)
        self.get_session(context, session_id)
        rows = self._session.scalars(
            select(QuestionSourceReferenceRow).where(
                QuestionSourceReferenceRow.company_id == tenant.company_id,
                QuestionSourceReferenceRow.interview_session_id == session_id,
            )
        )
        return tuple(self._source_reference_domain(row) for row in rows)

    @staticmethod
    def _session_domain(row: InterviewSessionRow) -> InterviewSession:
        return InterviewSession(
            interview_session_id=row.interview_session_id,
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            applicant_id=row.applicant_id,
            interview_strategy_id=row.interview_strategy_id,
            competency_model_version_id=row.competency_model_version_id,
            state=row.state,
            session_sequence=row.session_sequence,
            row_version=row.row_version,
            degraded_modes=tuple(row.degraded_modes),
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )

    @staticmethod
    def _turn_domain(row: InterviewTurnRow) -> InterviewTurn:
        return InterviewTurn(
            turn_id=row.turn_id,
            company_id=row.company_id,
            interview_session_id=row.interview_session_id,
            sequence=row.sequence,
            speaker=TurnSpeaker(row.speaker),
            status=TurnStatus(row.status),
            text=row.text,
            target_criterion_id=row.target_criterion_id,
            idempotency_key=row.idempotency_key,
            model_config_version=row.model_config_version,
            finalized_at=row.finalized_at,
        )

    @staticmethod
    def _checkpoint_domain(row: SessionCheckpointRow) -> SessionCheckpoint:
        return SessionCheckpoint(
            checkpoint_id=row.checkpoint_id,
            company_id=row.company_id,
            interview_session_id=row.interview_session_id,
            session_sequence=row.session_sequence,
            last_final_turn_id=row.last_final_turn_id,
            last_media_chunk_sequence=row.last_media_chunk_sequence,
            pending_turn_id=row.pending_turn_id,
            hot_view_sync_status=HotViewSyncStatus(row.hot_view_sync_status),
            created_at=row.created_at,
        )

    @staticmethod
    def _chunk_domain(row: RecordingChunkRow) -> RecordingChunk:
        return RecordingChunk(
            recording_chunk_id=row.recording_chunk_id,
            company_id=row.company_id,
            interview_session_id=row.interview_session_id,
            sequence=row.sequence,
            object_key=row.object_key,
            content_hash=row.content_hash,
            byte_size=row.byte_size,
            session_start_ms=row.session_start_ms,
            session_end_ms=row.session_end_ms,
            upload_status=RecordingUploadStatus(row.upload_status),
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
        )

    @staticmethod
    def _source_reference_domain(
        row: QuestionSourceReferenceRow,
    ) -> QuestionSourceReference:
        return QuestionSourceReference(
            source_reference_id=row.source_reference_id,
            company_id=row.company_id,
            interview_session_id=row.interview_session_id,
            question_turn_id=row.question_turn_id,
            source_id=row.source_id,
            source_type=row.source_type,
            locator=dict(row.locator),
            excerpt=row.excerpt,
            relevance_score=row.relevance_score,
            ownership_confidence=row.ownership_confidence,
            retrieval_config_version=row.retrieval_config_version,
            model_config_version=row.model_config_version,
            created_at=row.created_at,
        )

    @staticmethod
    def _verification_progress_domain(
        row: VerificationProgressRow,
    ) -> VerificationProgress:
        return VerificationProgress(
            verification_progress_id=row.verification_progress_id,
            company_id=row.company_id,
            interview_session_id=row.interview_session_id,
            applicant_id=row.applicant_id,
            verification_target_id=row.verification_target_id,
            criterion_id=row.criterion_id,
            state=VerificationProgressState(row.state),
            follow_up_count=row.follow_up_count,
            final_answer_turn_ids=tuple(UUID(value) for value in row.final_answer_turn_ids),
            updated_at=row.updated_at,
        )

    @staticmethod
    def _question_rationale_domain(
        row: QuestionRationaleRow,
    ) -> QuestionRationale:
        return QuestionRationale(
            question_rationale_id=row.question_rationale_id,
            company_id=row.company_id,
            interview_session_id=row.interview_session_id,
            question_turn_id=row.question_turn_id,
            applicant_id=row.applicant_id,
            competency_model_version_id=row.competency_model_version_id,
            criterion_id=row.criterion_id,
            verification_target_id=row.verification_target_id,
            verification_target_type=row.verification_target_type,
            objective=row.objective,
            question_type=row.question_type,
            interview_stage=row.interview_stage,
            retrieval_version=row.retrieval_version,
            generation_version=row.generation_version,
            policy_result=row.policy_result,
            source_reference_ids=tuple(UUID(value) for value in row.source_reference_ids),
            created_at=row.created_at,
        )
