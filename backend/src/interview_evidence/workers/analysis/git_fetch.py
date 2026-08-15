from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


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
class RepositoryCommit:
    parent_sha: str
    commit_sha: str
    author_name: str
    author_email: str
    changed_line_ranges: dict[str, tuple[tuple[int, int], ...]]

    @property
    def changed_paths(self) -> tuple[str, ...]:
        return tuple(sorted(self.changed_line_ranges))


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    repository_url: str
    default_branch: str
    pinned_head_sha: str
    files: tuple[RepositoryFile, ...]
    commit_count: int
    commits: tuple[RepositoryCommit, ...] = ()


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


class GitHubPublicTransport:
    """Fetch one reproducible public GitHub commit through bounded HTTPS calls."""

    def __init__(self, *, token: str | None = None) -> None:
        self._token = token

    def fetch(
        self,
        repository_url: str,
        *,
        timeout_seconds: int,
        max_commits: int,
    ) -> RepositorySnapshot:
        owner, repository = _github_repository(repository_url)
        api_root = f"https://api.github.com/repos/{quote(owner)}/{quote(repository)}"
        metadata = self._json_dict(api_root, timeout_seconds)
        default_branch = _required_string(metadata, "default_branch")
        query = urlencode(
            {
                "sha": default_branch,
                "per_page": min(100, max_commits),
            }
        )
        raw_commits = self._json_list(
            f"{api_root}/commits?{query}",
            timeout_seconds,
        )
        if not raw_commits:
            raise GitFetchError("repository_has_no_commits")
        first_commit = raw_commits[0]
        if not isinstance(first_commit, dict):
            raise GitFetchError("public_git_response_invalid")
        head_sha = _required_string(cast(dict[str, object], first_commit), "sha")
        detail = self._json_dict(f"{api_root}/commits/{head_sha}", timeout_seconds)
        parent_sha = _first_parent_sha(detail)
        author_name, author_email = _commit_author(detail)
        files: list[RepositoryFile] = []
        changed_ranges: dict[str, tuple[tuple[int, int], ...]] = {}
        raw_files = detail.get("files")
        if not isinstance(raw_files, list):
            raise GitFetchError("repository_commit_files_unavailable")
        for item in raw_files:
            if not isinstance(item, dict):
                continue
            path = item.get("filename")
            raw_url = item.get("raw_url")
            if not isinstance(path, str) or not isinstance(raw_url, str):
                continue
            files.append(
                RepositoryFile(
                    path=path,
                    content=self._bytes(raw_url, timeout_seconds),
                )
            )
            ranges = _changed_ranges(item.get("patch"))
            if not ranges:
                line_count = max(1, files[-1].content.count(b"\n") + 1)
                ranges = ((1, line_count),)
            changed_ranges[path] = ranges
        return RepositorySnapshot(
            repository_url=repository_url,
            default_branch=default_branch,
            pinned_head_sha=head_sha,
            files=tuple(files),
            commit_count=len(raw_commits),
            commits=(
                RepositoryCommit(
                    parent_sha=parent_sha,
                    commit_sha=head_sha,
                    author_name=author_name,
                    author_email=author_email,
                    changed_line_ranges=changed_ranges,
                ),
            ),
        )

    def _json_dict(self, url: str, timeout_seconds: int) -> dict[str, object]:
        value = self._json(url, timeout_seconds)
        if not isinstance(value, dict):
            raise GitFetchError("public_git_response_invalid")
        return cast(dict[str, object], value)

    def _json_list(self, url: str, timeout_seconds: int) -> list[object]:
        value = self._json(url, timeout_seconds)
        if not isinstance(value, list):
            raise GitFetchError("public_git_response_invalid")
        return cast(list[object], value)

    def _json(self, url: str, timeout_seconds: int) -> object:
        try:
            return json.loads(self._request(url, timeout_seconds))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise GitFetchError("public_git_fetch_failed") from error

    def _bytes(self, url: str, timeout_seconds: int) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "raw.githubusercontent.com",
            "github.com",
        }:
            raise GitFetchError("public_git_raw_url_invalid")
        try:
            request = Request(url, headers=self._headers())
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                return cast(bytes, response.read())
        except OSError as error:
            raise GitFetchError("public_git_file_fetch_failed") from error

    def _request(self, url: str, timeout_seconds: int) -> str:
        request = Request(url, headers=self._headers())
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return cast(bytes, response.read()).decode("utf-8")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "interview-evidence-platform",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers


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
            commits=snapshot.commits,
        )


def _github_repository(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitFetchError("only_public_github_https_is_supported")
    parts = tuple(part for part in parsed.path.removesuffix(".git").split("/") if part)
    if len(parts) != 2:
        raise GitFetchError("github_repository_url_invalid")
    return parts[0], parts[1]


def _required_string(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise GitFetchError("public_git_response_invalid")
    return result


def _first_parent_sha(detail: dict[str, object]) -> str:
    parents = detail.get("parents")
    if not isinstance(parents, list) or not parents or not isinstance(parents[0], dict):
        raise GitFetchError("public_git_parent_unavailable")
    return _required_string(cast(dict[str, object], parents[0]), "sha")


def _commit_author(detail: dict[str, object]) -> tuple[str, str]:
    commit = detail.get("commit")
    if not isinstance(commit, dict):
        raise GitFetchError("public_git_author_unavailable")
    author = commit.get("author")
    if not isinstance(author, dict):
        raise GitFetchError("public_git_author_unavailable")
    return _required_string(author, "name"), _required_string(author, "email")


def _changed_ranges(patch: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(patch, str):
        return ()
    ranges: list[tuple[int, int]] = []
    for start, raw_count in re.findall(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch):
        count = int(raw_count or "1")
        if count > 0:
            ranges.append((int(start), int(start) + count - 1))
    return tuple(ranges)
