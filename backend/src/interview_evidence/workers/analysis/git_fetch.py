from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from random import Random
from typing import Final, Protocol, cast
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from interview_evidence.submission_analysis.domain.git_analysis import CommitIdentityInput

#: Git's canonical empty tree. Diffing a root commit against it is the standard way to
#: say "every line here is new", which is what an initial commit means. Without this a
#: repository whose history is one commit -- a very ordinary candidate project -- would
#: fail the parent lookup and lose its only evidence.
EMPTY_TREE_SHA: Final = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

#: GitHub's maximum commits per listing call.
_LISTING_PAGE_SIZE: Final = 100

#: File suffixes that carry authored source code. Screening on these is what makes
#: sampling worth doing: the analysis builds its evidence out of code units, so a commit
#: that only touched a changelog costs a call and yields nothing to ask about. Measured
#: over a real 300-commit history, screening here raised the share of budgeted commits
#: that produced evidence from three in ten to ten in ten.
SOURCE_SUFFIXES: Final = (
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".swift",
    ".ts",
    ".tsx",
)

#: Commit subjects that describe housekeeping rather than authored work. Nobody can be
#: asked what they understood from bumping a version, and a merge commit carries no code
#: of its own. In a 300-commit history measured here, 62% were merges and 36% matched
#: this pattern -- two thirds of a naive random draw would have bought nothing.
_HOUSEKEEPING_SUBJECT: Final = re.compile(
    r"^(merge|bump|typo|lint|format|style|chore|release|update changelog|fix ci|pin )",
    re.IGNORECASE,
)


class GitFetchError(RuntimeError):
    """Sanitized bounded-repository fetch failure."""


@dataclass(frozen=True, slots=True)
class GitFetchLimits:
    max_files: int = 2_000
    max_total_bytes: int = 50 * 1024 * 1024
    max_file_bytes: int = 2 * 1024 * 1024
    #: Ceiling on how many commits a repository may list before it is refused as too
    #: large to reason about.
    max_commits: int = 500
    #: How many of the listed commits are deep-fetched for diffs and file contents.
    #: Each one costs a detail call plus a call per changed file, so this -- not
    #: ``max_commits`` -- is the dial that decides how long an analysis takes.
    max_analyzed_commits: int = 20
    #: How many listing pages are paged through to build the candidate pool. Listing is
    #: the cheap part of the fetch -- 100 commits per call against one call per commit
    #: for the details -- so paging wide costs little and is what lets the sample span a
    #: whole history instead of the most recent week.
    max_listing_pages: int = 5
    #: Candidate commits screened per commit actually analyzed. Screening reuses the
    #: detail call the analysis needs anyway, so only the rejected candidates cost extra.
    screening_multiple: int = 3
    #: Concurrent HTTPS calls. The fetch is entirely network-bound, so this is the
    #: difference between an analysis a recruiter waits out and one they abandon. Kept
    #: modest so one analysis does not look like abuse to GitHub.
    max_workers: int = 8
    timeout_seconds: int = 120


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    path: str
    content: bytes
    #: The commit this blob was read at. Empty means the pinned head snapshot, which is
    #: what a transport that only reports current file contents returns.
    commit_sha: str = ""


@dataclass(frozen=True, slots=True)
class RepositoryCommit:
    parent_sha: str
    commit_sha: str
    author_name: str
    author_email: str
    changed_line_ranges: dict[str, tuple[tuple[int, int], ...]]
    author_login: str | None = None

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
        limits: GitFetchLimits,
        identity: CommitIdentityInput | None = None,
    ) -> RepositorySnapshot: ...


class StaticGitTransport:
    def __init__(self, snapshot: RepositorySnapshot) -> None:
        self._snapshot = snapshot
        self.calls: list[str] = []

    def fetch(
        self,
        repository_url: str,
        *,
        limits: GitFetchLimits,
        identity: CommitIdentityInput | None = None,
    ) -> RepositorySnapshot:
        del limits, identity
        self.calls.append(repository_url)
        if repository_url != self._snapshot.repository_url:
            raise GitFetchError("repository_not_found")
        return self._snapshot


class GitHubPublicTransport:
    """Fetch reproducible public GitHub commits through bounded parallel HTTPS calls.

    An anonymous caller gets 60 GitHub API requests an hour, which a single analysis of
    a real repository can exhaust by itself; a personal access token raises that to
    5000. The token is therefore the difference between an analysis that completes and
    one that dies on rate limiting. It is only ever placed in a request header -- never
    in a snapshot, an error code or a log line.

    When the candidate's identity is known the commit listing is filtered by author
    server-side, so the calls are spent on the commits that can actually be attributed
    to them rather than on whatever landed on the default branch most recently.

    An authored history is routinely far larger than any analysis budget -- 876 commits
    for one contributor measured while building this -- so the budgeted commits are
    sampled across the whole history rather than taken from its head. Listing is the
    cheap half of the fetch, at a hundred commits per call against one call per commit
    for the details, which is what makes drawing from a wide pool affordable.
    """

    def __init__(self, *, token: str | None = None) -> None:
        self._token = token

    def fetch(
        self,
        repository_url: str,
        *,
        limits: GitFetchLimits,
        identity: CommitIdentityInput | None = None,
    ) -> RepositorySnapshot:
        owner, repository, requested_branch = _github_repository(repository_url)
        api_root = f"https://api.github.com/repos/{quote(owner)}/{quote(repository)}"
        metadata = self._json_dict(api_root, limits.timeout_seconds)
        default_branch = requested_branch or _required_string(metadata, "default_branch")
        branch_page = self._commit_listing(api_root, default_branch, limits, author=None)
        if not branch_page:
            raise GitFetchError("repository_has_no_commits")
        # The pinned head always comes from the unfiltered branch listing, so an
        # author-filtered analysis still records which repository state it read.
        pinned_head_sha = _required_string(branch_page[0], "sha")
        authored = self._authored_pool(api_root, default_branch, limits, identity)
        if identity is not None and not authored:
            raise GitFetchError("candidate_github_identity_has_no_commits")
        listed = authored or self._paged_listing(
            api_root, default_branch, limits, author=None, first_page=branch_page
        )
        order = _sampling_order(listed, limits, _sample_seed(repository_url, identity))
        selected = self._screened_details(api_root, order, limits)
        # Back into listing order: the sampling order exists only to decide which
        # commits are read, and evidence for one repository has to read the same way
        # every time it is produced.
        rank = {_required_string(item, "sha"): index for index, item in enumerate(listed)}
        selected.sort(key=lambda pair: rank.get(pair[0], len(rank)))
        files, ranges_by_sha = self._blob_fetch(selected, limits)
        commits = tuple(
            RepositoryCommit(
                parent_sha=_first_parent_sha(detail),
                commit_sha=sha,
                author_name=author_name,
                author_email=author_email,
                changed_line_ranges=ranges_by_sha[sha],
                author_login=author_login,
            )
            for sha, detail, (author_name, author_email, author_login) in (
                (sha, detail, _commit_author(detail)) for sha, detail in selected
            )
            # A commit whose every change was a deletion or an unreadable blob carries
            # no code to ask about, and the domain refuses a candidate with no paths.
            if ranges_by_sha[sha]
        )
        if not commits:
            raise GitFetchError("repository_commit_files_unavailable")
        return RepositorySnapshot(
            repository_url=repository_url,
            default_branch=default_branch,
            pinned_head_sha=pinned_head_sha,
            files=files,
            commit_count=len(listed),
            commits=commits,
        )

    def _screened_details(
        self,
        api_root: str,
        order: tuple[str, ...],
        limits: GitFetchLimits,
    ) -> list[tuple[str, dict[str, object]]]:
        """Commit details for the sampled commits that carry authored source.

        The screen is free in the common case: reading a commit's diff needs the detail
        call anyway, and that same response lists the changed files, so a commit that
        turns out to touch only a changelog is recognised without spending a blob call
        on it. Only rejected candidates cost anything extra, which is why the search is
        bounded to ``screening_multiple`` times the budget.

        Candidates are screened in parallel waves as wide as the remaining budget, so a
        history whose commits mostly touch code costs a single round of concurrent calls
        while one padded with documentation edits keeps looking.
        """
        budget = max(1, limits.max_analyzed_commits)
        ceiling = min(len(order), budget * max(1, limits.screening_multiple))
        selected: list[tuple[str, dict[str, object]]] = []
        screened: list[tuple[str, dict[str, object]]] = []
        with ThreadPoolExecutor(max_workers=max(1, limits.max_workers)) as pool:
            while len(screened) < ceiling and len(selected) < budget:
                wave = order[len(screened) : len(screened) + budget - len(selected)][
                    : ceiling - len(screened)
                ]
                details = pool.map(
                    lambda sha: self._json_dict(
                        f"{api_root}/commits/{sha}",
                        limits.timeout_seconds,
                    ),
                    wave,
                )
                for sha, detail in zip(wave, details, strict=True):
                    screened.append((sha, detail))
                    if _touches_source(detail):
                        selected.append((sha, detail))
        # A repository written in a language this screen does not know about, or one
        # holding only prose, would otherwise analyse to nothing. Falling back to what
        # was screened keeps the old unscreened behaviour for those.
        return selected or screened[:budget]

    def _blob_fetch(
        self,
        selected: list[tuple[str, dict[str, object]]],
        limits: GitFetchLimits,
    ) -> tuple[tuple[RepositoryFile, ...], dict[str, dict[str, tuple[tuple[int, int], ...]]]]:
        """Read every selected commit's changed blobs concurrently.

        Order is preserved against the selection rather than taken from completion
        order, because two runs over the same repository have to produce the same
        evidence.
        """
        blobs = [
            (sha, path, raw_url, patch)
            for sha, detail in selected
            for path, raw_url, patch in _changed_blobs(detail)
        ]
        with ThreadPoolExecutor(max_workers=max(1, limits.max_workers)) as pool:
            contents = list(
                pool.map(
                    lambda blob: self._optional_bytes(blob[2], limits.timeout_seconds),
                    blobs,
                )
            )
        files: list[RepositoryFile] = []
        ranges_by_sha: dict[str, dict[str, tuple[tuple[int, int], ...]]] = {
            sha: {} for sha, _detail in selected
        }
        for (sha, path, _raw_url, patch), content in zip(blobs, contents, strict=True):
            if content is None:
                continue
            files.append(RepositoryFile(path=path, content=content, commit_sha=sha))
            ranges = _changed_ranges(patch)
            if not ranges:
                ranges = ((1, max(1, content.count(b"\n") + 1)),)
            ranges_by_sha[sha][path] = ranges
        return tuple(files), ranges_by_sha

    def _authored_pool(
        self,
        api_root: str,
        default_branch: str,
        limits: GitFetchLimits,
        identity: CommitIdentityInput | None,
    ) -> list[dict[str, object]]:
        """The candidate's own commits, or nothing if we cannot name them.

        GitHub's ``author`` filter takes one login or address at a time, so the claimed
        identities are tried in turn and the first that matches wins. An identity that
        matches nothing returns an empty list and the caller rejects the submission;
        unrelated branch commits must never be sent to the embedding model.
        """
        if identity is None:
            return []
        for author in (*identity.claimed_handles, *identity.claimed_emails):
            if not author.strip():
                continue
            listing = self._paged_listing(api_root, default_branch, limits, author=author)
            if listing:
                return listing
        return []

    def _paged_listing(
        self,
        api_root: str,
        default_branch: str,
        limits: GitFetchLimits,
        *,
        author: str | None,
        first_page: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        """Page through the listing to build the pool the sample is drawn from.

        Paging stops at a short page, which is GitHub's way of saying the history ended,
        so a small repository still costs one call. ``first_page`` hands over a page the
        caller already read, so no listing call is made twice.
        """
        pooled: list[dict[str, object]] = []
        for page in range(1, max(1, limits.max_listing_pages) + 1):
            listing = (
                first_page
                if page == 1 and first_page is not None
                else self._commit_listing(
                    api_root,
                    default_branch,
                    limits,
                    author=author,
                    page=page,
                )
            )
            pooled.extend(listing)
            if len(listing) < _LISTING_PAGE_SIZE or len(pooled) >= limits.max_commits:
                break
        return pooled

    def _commit_listing(
        self,
        api_root: str,
        default_branch: str,
        limits: GitFetchLimits,
        *,
        author: str | None,
        page: int = 1,
    ) -> list[dict[str, object]]:
        parameters: dict[str, object] = {
            "sha": default_branch,
            "per_page": min(_LISTING_PAGE_SIZE, limits.max_commits),
        }
        if author is not None:
            parameters["author"] = author
        if page > 1:
            parameters["page"] = page
        raw = self._json_list(f"{api_root}/commits?{urlencode(parameters)}", limits.timeout_seconds)
        listing: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise GitFetchError("public_git_response_invalid")
            listing.append(cast(dict[str, object], item))
        return listing

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

    def _optional_bytes(self, url: str, timeout_seconds: int) -> bytes | None:
        """A blob, or None when GitHub no longer serves it.

        A missing blob costs one piece of evidence; failing the whole analysis over it
        costs the recruiter the entire repository.
        """
        try:
            return self._bytes(url, timeout_seconds)
        except GitFetchError:
            return None

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
        except HTTPError as error:
            raise GitFetchError("public_git_file_unavailable") from error
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

    def fetch(
        self,
        repository_url: str,
        *,
        identity: CommitIdentityInput | None = None,
    ) -> RepositorySnapshot:
        snapshot = self._transport.fetch(
            repository_url,
            limits=self._limits,
            identity=identity,
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
            # Downstream analysis reads every included file as UTF-8 text. Rejecting an
            # undecodable file here keeps one oddly encoded blob from aborting the
            # analysis of an otherwise readable repository.
            try:
                file.content.decode("utf-8")
            except UnicodeDecodeError:
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


def _github_repository(repository_url: str) -> tuple[str, str, str | None]:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitFetchError("only_public_github_https_is_supported")
    parts = tuple(part for part in parsed.path.removesuffix(".git").split("/") if part)
    if len(parts) == 2:
        return parts[0], parts[1], None
    if len(parts) >= 4 and parts[2] == "tree":
        return parts[0], parts[1], unquote("/".join(parts[3:]))
    raise GitFetchError("github_repository_url_invalid")


def _listed_shas(listing: list[dict[str, object]]) -> tuple[str, ...]:
    return tuple(_required_string(item, "sha") for item in listing)


def _sample_seed(repository_url: str, identity: CommitIdentityInput | None) -> str:
    """Seed material for the draw.

    Derived from the repository and the claimed identity so that re-analysing one
    submission reads the same commits. A clock- or process-seeded draw would make two
    runs disagree about what the candidate wrote, and a recruiter could not go back to
    the evidence a question came from.
    """
    claimed: tuple[str, ...] = ()
    if identity is not None:
        claimed = (*identity.claimed_handles, *identity.claimed_emails)
    return "\n".join((repository_url, *sorted(claimed)))


def _sampling_order(
    listing: list[dict[str, object]],
    limits: GitFetchLimits,
    seed: str,
) -> tuple[str, ...]:
    """The order candidate commits are screened in.

    Housekeeping is dropped first: merges carry no code of their own and a version bump
    is not something anyone can be asked what they understood. The survivors are then
    grouped by authoring month and taken round-robin across those months, so the sample
    reflects a candidate's work over time rather than whatever they did the week before
    applying. Measured against taking the newest commits, this widened the span of an
    analysis from one month to ten at the same number of API calls.
    """
    pool = [item for item in listing if not _is_housekeeping(item)]
    # An author whose whole history is merges and bumps still deserves an analysis.
    ordered = pool or listing
    if len(ordered) <= limits.max_analyzed_commits:
        return _listed_shas(ordered)
    buckets: dict[str, list[str]] = {}
    for item in ordered:
        buckets.setdefault(_authored_month(item), []).append(_required_string(item, "sha"))
    random = Random(sha256(seed.encode("utf-8")).hexdigest())
    for shas in buckets.values():
        random.shuffle(shas)
    drawn: list[str] = []
    months = sorted(buckets)
    while len(drawn) < len(ordered):
        for month in months:
            if buckets[month]:
                drawn.append(buckets[month].pop())
    return tuple(drawn)


def _is_housekeeping(item: dict[str, object]) -> bool:
    parents = item.get("parents")
    if isinstance(parents, list) and len(parents) > 1:
        return True
    commit = item.get("commit")
    if not isinstance(commit, dict):
        return False
    message = cast(dict[str, object], commit).get("message")
    if not isinstance(message, str):
        return False
    return _HOUSEKEEPING_SUBJECT.match(message.strip()) is not None


def _authored_month(item: dict[str, object]) -> str:
    """The commit's authoring month, or an empty bucket when GitHub omits the date."""
    commit = item.get("commit")
    if not isinstance(commit, dict):
        return ""
    author = cast(dict[str, object], commit).get("author")
    if not isinstance(author, dict):
        return ""
    date = cast(dict[str, object], author).get("date")
    return date[:7] if isinstance(date, str) else ""


def _touches_source(detail: dict[str, object]) -> bool:
    """Whether a commit changed a file the analysis can build code units from."""
    raw_files = detail.get("files")
    if not isinstance(raw_files, list):
        return False
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = cast(dict[str, object], item).get("filename")
        if not isinstance(path, str) or item.get("status") == "removed":
            continue
        if path.endswith(SOURCE_SUFFIXES):
            return True
    return False


def _required_string(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise GitFetchError("public_git_response_invalid")
    return result


def _first_parent_sha(detail: dict[str, object]) -> str:
    parents = detail.get("parents")
    if not isinstance(parents, list):
        raise GitFetchError("public_git_parent_unavailable")
    if not parents:
        return EMPTY_TREE_SHA
    if not isinstance(parents[0], dict):
        raise GitFetchError("public_git_parent_unavailable")
    return _required_string(cast(dict[str, object], parents[0]), "sha")


def _commit_author(detail: dict[str, object]) -> tuple[str, str, str | None]:
    commit = detail.get("commit")
    if not isinstance(commit, dict):
        raise GitFetchError("public_git_author_unavailable")
    author = commit.get("author")
    if not isinstance(author, dict):
        raise GitFetchError("public_git_author_unavailable")
    github_author = detail.get("author")
    author_login = github_author.get("login") if isinstance(github_author, dict) else None
    return (
        _required_string(author, "name"),
        _required_string(author, "email"),
        author_login if isinstance(author_login, str) and author_login else None,
    )


def _changed_blobs(detail: dict[str, object]) -> list[tuple[str, str, object]]:
    raw_files = detail.get("files")
    if not isinstance(raw_files, list):
        raise GitFetchError("repository_commit_files_unavailable")
    blobs: list[tuple[str, str, object]] = []
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = item.get("filename")
        raw_url = item.get("raw_url")
        if not isinstance(path, str) or not isinstance(raw_url, str):
            continue
        # A commit that deletes a file leaves no blob to read at that commit, and a
        # deletion is not authored code to build a question from.
        if item.get("status") == "removed":
            continue
        blobs.append((path, raw_url, item.get("patch")))
    return blobs


def _changed_ranges(patch: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(patch, str):
        return ()
    ranges: list[tuple[int, int]] = []
    for start, raw_count in re.findall(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch):
        count = int(raw_count or "1")
        if count > 0:
            ranges.append((int(start), int(start) + count - 1))
    return tuple(ranges)
