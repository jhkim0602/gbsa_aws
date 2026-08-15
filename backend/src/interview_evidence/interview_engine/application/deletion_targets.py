from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class InterviewDeletionTarget:
    company_id: UUID
    owner_lane: str
    store: str
    resource_type: str
    resource_id: str
    verification_required: bool = True


@dataclass(frozen=True, slots=True)
class InterviewDeletionReceipt:
    company_id: UUID
    store: str
    resource_type: str
    resource_id: str
    verified_absent: bool


class InterviewTargetDeleter(Protocol):
    def delete_and_verify(
        self,
        context: TenantContext,
        target: InterviewDeletionTarget,
        meta: CommandMeta,
    ) -> InterviewDeletionReceipt: ...


class InMemoryInterviewTargetDeleter:
    def __init__(self) -> None:
        self.calls: list[InterviewDeletionTarget] = []
        self._receipts: dict[tuple[UUID, str], InterviewDeletionReceipt] = {}

    def delete_and_verify(
        self,
        context: TenantContext,
        target: InterviewDeletionTarget,
        meta: CommandMeta,
    ) -> InterviewDeletionReceipt:
        context.assert_company(target.company_id)
        if target.owner_lane != "C":
            raise PermissionError("deletion target is not owned by Lane C")
        key = (context.company_id, meta.idempotency_key)
        existing = self._receipts.get(key)
        if existing is not None:
            return existing
        self.calls.append(target)
        receipt = InterviewDeletionReceipt(
            company_id=context.company_id,
            store=target.store,
            resource_type=target.resource_type,
            resource_id=target.resource_id,
            verified_absent=True,
        )
        self._receipts[key] = receipt
        return receipt


class InterviewDeletionTargets:
    def __init__(self, repository: InterviewRepository) -> None:
        self._repository = repository

    def enumerate_owned_targets(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> tuple[InterviewDeletionTarget, ...]:
        session = self._repository.get_session(context, session_id)
        turns = self._repository.list_turns(context, session_id)
        checkpoints = self._repository.list_checkpoints(context, session_id)
        source_references = self._repository.list_session_source_references(context, session_id)
        chunks = self._repository.list_recording_chunks(context, session_id)
        targets = [
            InterviewDeletionTarget(
                company_id=context.company_id,
                owner_lane="C",
                store="aurora",
                resource_type="interview_session",
                resource_id=str(session.interview_session_id),
            ),
            InterviewDeletionTarget(
                company_id=context.company_id,
                owner_lane="C",
                store="dynamodb",
                resource_type="interview_hot_view",
                resource_id=f"SESSION#{session.interview_session_id}",
            ),
        ]
        targets.extend(
            InterviewDeletionTarget(
                company_id=context.company_id,
                owner_lane="C",
                store="aurora",
                resource_type="interview_turn",
                resource_id=str(turn.turn_id),
            )
            for turn in turns
        )
        targets.extend(
            InterviewDeletionTarget(
                company_id=context.company_id,
                owner_lane="C",
                store="aurora",
                resource_type="session_checkpoint",
                resource_id=str(checkpoint.checkpoint_id),
            )
            for checkpoint in checkpoints
        )
        targets.extend(
            InterviewDeletionTarget(
                company_id=context.company_id,
                owner_lane="C",
                store="aurora",
                resource_type="question_source_reference",
                resource_id=str(reference.source_reference_id),
            )
            for reference in source_references
        )
        for chunk in chunks:
            targets.extend(
                (
                    InterviewDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="C",
                        store="s3",
                        resource_type="recording_chunk_object",
                        resource_id=chunk.object_key,
                    ),
                    InterviewDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="C",
                        store="aurora",
                        resource_type="recording_chunk",
                        resource_id=str(chunk.recording_chunk_id),
                    ),
                )
            )
        return tuple(targets)
