from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class GitFetchError(RuntimeError):
    """Sanitized bounded-repository fetch failure."""


@dataclass(frozen=True, slots=True)
class GitFetchLimits:
    max_files: int = 2_000
    max_total_bytes: int = 50 * 1024 * 1024
    max_file_bytes: int = 2 * 1024 * 1024
    max_commits: int = 500
    timeout_seconds: int = 120


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    path: str
    content: bytes


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    repository_url: str
    default_branch: str
    pinned_head_sha: str
    files: tuple[RepositoryFile, ...]
    commit_count: int


class GitTransport(Protocol):
    def fetch(
        self,
        repository_url: str,
        *,
        timeout_seconds: int,
        max_commits: int,
    ) -> RepositorySnapshot: ...


class StaticGitTransport:
    def __init__(self, snapshot: RepositorySnapshot) -> None:
        self._snapshot = snapshot
        self.calls: list[str] = []

    def fetch(
        self,
        repository_url: str,
        *,
        timeout_seconds: int,
        max_commits: int,
    ) -> RepositorySnapshot:
        del timeout_seconds, max_commits
        self.calls.append(repository_url)
        if repository_url != self._snapshot.repository_url:
            raise GitFetchError("repository_not_found")
        return self._snapshot


class BoundedGitFetcher:
    EXCLUDED_SEGMENTS = {
        ".git",
        "node_modules",
        "vendor",
        "dist",
        "build",
        ".next",
        "__pycache__",
    }
    SECRET_NAMES = {
        ".env",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "secrets.json",
    }

    def __init__(self, transport: GitTransport, limits: GitFetchLimits) -> None:
        self._transport = transport
        self._limits = limits

    def fetch(self, repository_url: str) -> RepositorySnapshot:
        snapshot = self._transport.fetch(
            repository_url,
            timeout_seconds=self._limits.timeout_seconds,
            max_commits=self._limits.max_commits,
        )
        if snapshot.commit_count > self._limits.max_commits:
            raise GitFetchError("repository_commit_limit_exceeded")
        included: list[RepositoryFile] = []
        total_bytes = 0
        for file in snapshot.files:
            segments = set(file.path.split("/"))
            if segments & self.EXCLUDED_SEGMENTS:
                continue
            if file.path.rsplit("/", 1)[-1].casefold() in self.SECRET_NAMES:
                continue
            if len(file.content) > self._limits.max_file_bytes:
                continue
            if b"\x00" in file.content[:4096]:
                continue
            included.append(file)
            total_bytes += len(file.content)
            if len(included) > self._limits.max_files:
                raise GitFetchError("repository_file_limit_exceeded")
            if total_bytes > self._limits.max_total_bytes:
                raise GitFetchError("repository_byte_limit_exceeded")
        return RepositorySnapshot(
            repository_url=snapshot.repository_url,
            default_branch=snapshot.default_branch,
            pinned_head_sha=snapshot.pinned_head_sha,
            files=tuple(included),
            commit_count=snapshot.commit_count,
        )
