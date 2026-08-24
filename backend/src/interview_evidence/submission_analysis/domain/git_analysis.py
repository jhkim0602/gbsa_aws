from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GitAnalysisStatus(StrEnum):
    RUNNING = "running"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


class OwnershipClass(StrEnum):
    PRIMARY_OWNED = "primary_owned"
    SHARED = "shared"
    CONTEXT_ONLY = "context_only"
    UNRELATED = "unrelated"


class CommitIdentityInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    claimed_names: tuple[str, ...] = ()
    claimed_emails: tuple[str, ...] = ()
    claimed_handles: tuple[str, ...] = ()


class GitCommitCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    author_name: str
    author_email: str
    author_login: str | None = None
    changed_paths: tuple[str, ...] = Field(min_length=1)


class OwnershipAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    ownership_class: OwnershipClass
    confidence: float = Field(ge=0, le=1)
    explanation_codes: tuple[str, ...]
    requires_verification: bool
    verification_prompt: str


def classify_commit_ownership(
    commit: GitCommitCandidate,
    identity: CommitIdentityInput,
) -> OwnershipAssessment:
    name_match = commit.author_name.casefold() in {
        value.casefold() for value in identity.claimed_names
    }
    email_match = commit.author_email.casefold() in {
        value.casefold() for value in identity.claimed_emails
    }
    handle_match = any(
        handle.casefold() in commit.author_email.casefold() for handle in identity.claimed_handles
    )
    login_match = commit.author_login is not None and commit.author_login.casefold() in {
        handle.casefold() for handle in identity.claimed_handles
    }
    score = min(
        0.9,
        (0.35 if name_match else 0)
        + (0.45 if email_match else 0)
        + (0.7 if login_match else 0)
        + (0.2 if handle_match else 0),
    )
    codes = tuple(
        code
        for matched, code in (
            (name_match, "author_name_match"),
            (email_match, "author_email_match"),
            (login_match, "github_login_match"),
            (handle_match, "handle_match"),
        )
        if matched
    )
    if score >= 0.7:
        ownership_class = OwnershipClass.PRIMARY_OWNED
    elif score >= 0.4:
        ownership_class = OwnershipClass.SHARED
    elif score > 0:
        ownership_class = OwnershipClass.CONTEXT_ONLY
    else:
        ownership_class = OwnershipClass.CONTEXT_ONLY
        codes = ("no_identity_match",)
    return OwnershipAssessment(
        ownership_class=ownership_class,
        confidence=score,
        explanation_codes=codes,
        requires_verification=True,
        verification_prompt="이 변경에서 본인이 작성한 범위와 협업 범위를 설명해 주세요.",
    )


class GitRepositoryAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository_analysis_id: UUID
    company_id: UUID
    submission_id: UUID
    repository_url: str
    default_branch: str
    pinned_head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    candidate_identity_inputs: dict[str, object]
    limits_applied: dict[str, int]
    status: GitAnalysisStatus


class GitCommitAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    git_commit_analysis_id: UUID
    company_id: UUID
    repository_analysis_id: UUID
    parent_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    author_match_inputs: dict[str, object]
    change_summary_object_key: str
    ownership_confidence: float = Field(ge=0, le=1)
    ownership_class: OwnershipClass
    ownership_explanation: tuple[str, ...] = Field(min_length=1)


class CandidateCodeUnit(BaseModel):
    model_config = ConfigDict(frozen=True)

    code_unit_id: UUID
    company_id: UUID
    git_commit_analysis_id: UUID
    path: str
    language: str
    symbol: str
    original_line_range: tuple[int, int]
    current_line_range: tuple[int, int]
    authored_snapshot_key: str
    current_snapshot_key: str
    candidate_owned_regions: tuple[tuple[int, int], ...]
    related_test_ids: tuple[str, ...] = ()
    dependency_ids: tuple[str, ...] = ()
    index_document_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def line_ranges_are_ordered(self) -> CandidateCodeUnit:
        for start, end in (
            self.original_line_range,
            self.current_line_range,
            *self.candidate_owned_regions,
        ):
            if start < 1 or end < start:
                raise ValueError("code-unit line range is invalid")
        return self
