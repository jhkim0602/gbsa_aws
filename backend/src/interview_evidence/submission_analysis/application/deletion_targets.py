from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
)


@dataclass(frozen=True, slots=True)
class SubmissionDeletionTarget:
    company_id: UUID
    owner_lane: str
    store: str
    resource_type: str
    resource_id: str
    verification_required: bool = True


@dataclass(frozen=True, slots=True)
class SubmissionDeletionReceipt:
    company_id: UUID
    resource_type: str
    resource_id: str
    store: str
    verified_absent: bool


class SubmissionTargetDeleter(Protocol):
    def delete_and_verify(
        self,
        context: TenantContext,
        target: SubmissionDeletionTarget,
        meta: CommandMeta,
    ) -> SubmissionDeletionReceipt: ...


class SubmissionDeletionTargets:
    def __init__(self, repository: SubmissionRepository) -> None:
        self._repository = repository

    def enumerate_owned_targets(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
    ) -> tuple[SubmissionDeletionTarget, ...]:
        submissions = tuple(
            submission
            for submission in self._repository.list_submissions(context, applicant_id)
            if submission.invitation_id == invitation_id
        )
        submission_ids = frozenset(submission.submission_id for submission in submissions)
        analyses = self._repository.list_analyses(context, submission_ids)
        chunks = self._repository.list_chunks(context, applicant_id)
        repository_analyses = self._repository.list_git_repository_analyses(context, submission_ids)
        repository_analysis_ids = frozenset(
            analysis.repository_analysis_id for analysis in repository_analyses
        )
        commit_analyses = self._repository.list_git_commit_analyses(
            context, repository_analysis_ids
        )
        commit_analysis_ids = frozenset(
            analysis.git_commit_analysis_id for analysis in commit_analyses
        )
        code_units = self._repository.list_code_units(context, commit_analysis_ids)
        strategy = self._repository.latest_strategy(context, invitation_id)
        claims = self._repository.list_candidate_claims(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
        )
        conflicts = self._repository.list_claim_conflicts(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
        )
        verification_maps = self._repository.list_verification_maps(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
        )
        verification_targets = tuple(
            target
            for verification_map in verification_maps
            for target in self._repository.list_verification_targets(
                context,
                verification_map,
            )
        )
        retrieval_document_ids = self._repository.list_retrieval_document_ids(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
        )
        targets: list[SubmissionDeletionTarget] = []
        for submission in submissions:
            targets.append(
                SubmissionDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="B",
                    store="aurora",
                    resource_type="submission",
                    resource_id=str(submission.submission_id),
                )
            )
            if submission.source_uri.startswith("tenants/"):
                targets.append(
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="s3",
                        resource_type="submission_original",
                        resource_id=submission.source_uri,
                    )
                )
        for chunk in chunks:
            if chunk.submission_id not in submission_ids:
                continue
            targets.extend(
                [
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="s3",
                        resource_type="submission_chunk_text",
                        resource_id=chunk.text_object_key,
                    ),
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="retrieval",
                        resource_type="submission_chunk_index",
                        resource_id=chunk.index_document_id,
                    ),
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="aurora",
                        resource_type="submission_chunk",
                        resource_id=str(chunk.chunk_id),
                    ),
                ]
            )
        for analysis in analyses:
            targets.append(
                SubmissionDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="B",
                    store="aurora",
                    resource_type="submission_analysis",
                    resource_id=str(analysis.analysis_id),
                )
            )
        for repository_analysis in repository_analyses:
            targets.append(
                SubmissionDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="B",
                    store="aurora",
                    resource_type="git_repository_analysis",
                    resource_id=str(repository_analysis.repository_analysis_id),
                )
            )
        for commit_analysis in commit_analyses:
            targets.extend(
                [
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="s3",
                        resource_type="git_commit_diff",
                        resource_id=commit_analysis.change_summary_object_key,
                    ),
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="aurora",
                        resource_type="git_commit_analysis",
                        resource_id=str(commit_analysis.git_commit_analysis_id),
                    ),
                ]
            )
        for code_unit in code_units:
            targets.extend(
                [
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="s3",
                        resource_type="code_authored_snapshot",
                        resource_id=code_unit.authored_snapshot_key,
                    ),
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="s3",
                        resource_type="code_current_snapshot",
                        resource_id=code_unit.current_snapshot_key,
                    ),
                    SubmissionDeletionTarget(
                        company_id=context.company_id,
                        owner_lane="B",
                        store="aurora",
                        resource_type="candidate_code_unit",
                        resource_id=str(code_unit.code_unit_id),
                    ),
                ]
            )
            targets.extend(
                SubmissionDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="B",
                    store="retrieval",
                    resource_type="candidate_code_unit_index",
                    resource_id=document_id,
                )
                for document_id in code_unit.index_document_ids
            )
        if strategy is not None:
            targets.append(
                SubmissionDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="B",
                    store="aurora",
                    resource_type="interview_strategy",
                    resource_id=str(strategy.interview_strategy_id),
                )
            )
        targets.extend(
            SubmissionDeletionTarget(
                company_id=context.company_id,
                owner_lane="B",
                store="aurora",
                resource_type="candidate_claim",
                resource_id=str(claim.candidate_claim_id),
            )
            for claim in claims
        )
        targets.extend(
            SubmissionDeletionTarget(
                company_id=context.company_id,
                owner_lane="B",
                store="aurora",
                resource_type="claim_conflict",
                resource_id=str(conflict.claim_conflict_id),
            )
            for conflict in conflicts
        )
        targets.extend(
            SubmissionDeletionTarget(
                company_id=context.company_id,
                owner_lane="B",
                store="aurora",
                resource_type="verification_target",
                resource_id=str(target.verification_target_id),
            )
            for target in verification_targets
        )
        targets.extend(
            SubmissionDeletionTarget(
                company_id=context.company_id,
                owner_lane="B",
                store="aurora",
                resource_type="candidate_verification_map",
                resource_id=str(verification_map.candidate_verification_map_id),
            )
            for verification_map in verification_maps
        )
        targets.extend(
            SubmissionDeletionTarget(
                company_id=context.company_id,
                owner_lane="B",
                store="retrieval",
                resource_type="retrieval_document",
                resource_id=str(document_id),
            )
            for document_id in retrieval_document_ids
        )
        return tuple(
            {
                (target.store, target.resource_type, target.resource_id): target
                for target in targets
            }.values()
        )
