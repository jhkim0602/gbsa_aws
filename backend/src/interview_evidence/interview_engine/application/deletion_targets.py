from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.interview_engine.adapters.recent_context import RecentContextPort
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
    def __init__(
        self,
        *,
        repository: InterviewRepository | None = None,
        hot_view: RecentContextPort | None = None,
    ) -> None:
        self.calls: list[InterviewDeletionTarget] = []
        self._receipts: dict[tuple[UUID, str], InterviewDeletionReceipt] = {}
        self._repository = repository
        self._hot_view = hot_view

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
        verified_absent = self._delete_and_verify(context, target)
        receipt = InterviewDeletionReceipt(
            company_id=context.company_id,
            store=target.store,
            resource_type=target.resource_type,
            resource_id=target.resource_id,
            verified_absent=verified_absent,
        )
        self._receipts[key] = receipt
        return receipt

    def _delete_and_verify(
        self,
        context: TenantContext,
        target: InterviewDeletionTarget,
    ) -> bool:
        if target.store == "dynamodb":
            if self._hot_view is None:
                return True
            session_id = UUID(target.resource_id.removeprefix("SESSION#"))
            self._hot_view.delete(context, session_id)
            return self._hot_view.get(context, session_id) is None
        if target.store == "s3":
            return True
        if target.store != "aurora" or self._repository is None:
            return True

        return self._repository.delete_and_verify_target(
            context,
            resource_type=target.resource_type,
            resource_id=UUID(target.resource_id),
        )


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
