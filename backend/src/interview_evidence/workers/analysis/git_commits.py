from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from interview_evidence.shared.ids import new_uuid7
from interview_evidence.submission_analysis.domain.git_analysis import (
    CommitIdentityInput,
    GitCommitAnalysis,
    GitCommitCandidate,
    classify_commit_ownership,
)


@dataclass(frozen=True, slots=True)
class CommitDiff:
    candidate: GitCommitCandidate
    changed_line_count: int
    summary_object_key: str


def analyze_candidate_commits(
    *,
    company_id: UUID,
    repository_analysis_id: UUID,
    commits: tuple[CommitDiff, ...],
    identity: CommitIdentityInput,
) -> tuple[GitCommitAnalysis, ...]:
    results: list[GitCommitAnalysis] = []
    for commit in commits:
        ownership = classify_commit_ownership(commit.candidate, identity)
        results.append(
            GitCommitAnalysis(
                git_commit_analysis_id=new_uuid7(),
                company_id=company_id,
                repository_analysis_id=repository_analysis_id,
                parent_sha=commit.candidate.parent_sha,
                commit_sha=commit.candidate.commit_sha,
                author_match_inputs=identity.model_dump(mode="json"),
                change_summary_object_key=commit.summary_object_key,
                ownership_confidence=ownership.confidence,
                ownership_class=ownership.ownership_class,
                ownership_explanation=ownership.explanation_codes,
            )
        )
    return tuple(results)
