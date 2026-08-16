from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from interview_evidence.interview_engine.application.deletion_targets import (
    InterviewDeletionReceipt,
    InterviewDeletionTarget,
    InterviewDeletionTargets,
    InterviewTargetDeleter,
)
from interview_evidence.interview_engine.domain.turn import InterviewTurn
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class InterviewSessionSnapshot:
    company_id: UUID
    interview_session_id: UUID
    invitation_id: UUID
    state: str
    session_sequence: int
    interview_strategy_id: UUID
    competency_model_version_id: UUID
    last_final_turn_id: UUID | None
    degraded_modes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecordingChunkSnapshot:
    recording_chunk_id: UUID
    sequence: int
    object_key: str
    content_hash: str
    session_start_ms: int
    session_end_ms: int


@dataclass(frozen=True, slots=True)
class QuestionSourceReferenceSnapshot:
    source_id: UUID
    source_type: str
    locator: dict[str, object]
    excerpt: str


@dataclass(frozen=True, slots=True)
class QuestionRationaleSnapshot:
    question_turn_id: UUID
    criterion_id: UUID
    verification_target_type: str
    objective: str
    question_type: str
    retrieval_version: str
    generation_version: str
    policy_result: str
    source_references: tuple[QuestionSourceReferenceSnapshot, ...]


class InterviewEnginePublic:
    """Frozen Lane C boundary for company and reporting consumers."""

    def __init__(
        self,
        *,
        repository: InterviewRepository,
        deletion_targets: InterviewDeletionTargets,
        target_deleter: InterviewTargetDeleter,
    ) -> None:
        self._repository = repository
        self._deletion_targets = deletion_targets
        self._target_deleter = target_deleter

    def get_session_snapshot(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> InterviewSessionSnapshot:
        session = self._repository.get_session(context, session_id)
        checkpoint = self._repository.latest_checkpoint(context, session_id)
        return InterviewSessionSnapshot(
            company_id=session.company_id,
            interview_session_id=session.interview_session_id,
            invitation_id=session.invitation_id,
            state=session.state.value,
            session_sequence=session.session_sequence,
            interview_strategy_id=session.interview_strategy_id,
            competency_model_version_id=session.competency_model_version_id,
            last_final_turn_id=(checkpoint.last_final_turn_id if checkpoint is not None else None),
            degraded_modes=session.degraded_modes,
        )

    def find_session_for_invitation(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> InterviewSessionSnapshot | None:
        session = self._repository.find_session_for_invitation(
            context,
            invitation_id,
        )
        if session is None:
            return None
        checkpoint = self._repository.latest_checkpoint(
            context,
            session.interview_session_id,
        )
        return InterviewSessionSnapshot(
            company_id=session.company_id,
            interview_session_id=session.interview_session_id,
            invitation_id=session.invitation_id,
            state=session.state.value,
            session_sequence=session.session_sequence,
            interview_strategy_id=session.interview_strategy_id,
            competency_model_version_id=session.competency_model_version_id,
            last_final_turn_id=(checkpoint.last_final_turn_id if checkpoint is not None else None),
            degraded_modes=session.degraded_modes,
        )

    def get_final_turn(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        turn_id: UUID,
    ) -> InterviewTurn:
        turn = self._repository.get_turn(context, turn_id)
        if turn.interview_session_id != session_id or turn.status.value != "final":
            raise LookupError("final interview turn not found")
        return turn

    def list_final_turns(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> tuple[InterviewTurn, ...]:
        return self._repository.list_final_turns(context, session_id)

    def resolve_recording_chunks(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> tuple[RecordingChunkSnapshot, ...]:
        return tuple(
            RecordingChunkSnapshot(
                recording_chunk_id=chunk.recording_chunk_id,
                sequence=chunk.sequence,
                object_key=chunk.object_key,
                content_hash=chunk.content_hash,
                session_start_ms=chunk.session_start_ms,
                session_end_ms=chunk.session_end_ms,
            )
            for chunk in self._repository.list_recording_chunks(context, session_id)
            if chunk.upload_status.value == "verified"
        )

    def list_question_rationales(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> tuple[QuestionRationaleSnapshot, ...]:
        references = {
            reference.source_reference_id: reference
            for reference in self._repository.list_session_source_references(
                context,
                session_id,
            )
        }
        return tuple(
            QuestionRationaleSnapshot(
                question_turn_id=rationale.question_turn_id,
                criterion_id=rationale.criterion_id,
                verification_target_type=(rationale.verification_target_type),
                objective=rationale.objective,
                question_type=rationale.question_type,
                retrieval_version=rationale.retrieval_version,
                generation_version=rationale.generation_version,
                policy_result=rationale.policy_result,
                source_references=tuple(
                    QuestionSourceReferenceSnapshot(
                        source_id=references[reference_id].source_id,
                        source_type=references[reference_id].source_type,
                        locator=dict(references[reference_id].locator),
                        excerpt=references[reference_id].excerpt,
                    )
                    for reference_id in rationale.source_reference_ids
                    if reference_id in references
                ),
            )
            for rationale in self._repository.list_question_rationales(
                context,
                session_id,
            )
        )

    def enumerate_interview_deletion_targets(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> tuple[InterviewDeletionTarget, ...]:
        return self._deletion_targets.enumerate_owned_targets(
            context,
            session_id=session_id,
        )

    def delete_interview_target(
        self,
        context: TenantContext,
        *,
        target: InterviewDeletionTarget,
        meta: CommandMeta,
    ) -> InterviewDeletionReceipt:
        return self._target_deleter.delete_and_verify(context, target, meta)
