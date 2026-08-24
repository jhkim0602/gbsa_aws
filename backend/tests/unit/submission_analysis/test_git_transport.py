"""The public GitHub transport had no tests, which is how three defects survived it.

Before this module ``GitHubPublicTransport`` analyzed exactly one commit -- the newest
one on the default branch, whoever wrote it -- while ``GitFetchLimits.max_commits=500``
suggested it read up to five hundred. It also issued every HTTPS call in sequence, so a
commit touching twenty files cost twenty round trips one after another, and it fetched
whatever landed on the branch last rather than the applicant's own work.

The calls are counted rather than timed: wall clock is a property of the network, but
"how many round trips, and were they issued concurrently" is a property of this code.
"""

from __future__ import annotations

import json
import threading
from typing import Any
from urllib.parse import urlencode

import pytest
from interview_evidence.submission_analysis.domain.git_analysis import CommitIdentityInput
from interview_evidence.workers.analysis.git_fetch import (
    EMPTY_TREE_SHA,
    BoundedGitFetcher,
    GitFetchError,
    GitFetchLimits,
    GitHubPublicTransport,
    RepositoryFile,
    RepositorySnapshot,
)

REPOSITORY_URL = "https://github.com/example/candidate-project"
API_ROOT = "https://api.github.com/repos/example/candidate-project"
APPLICANT_EMAIL = "applicant@example.com"


def _sha(marker: str) -> str:
    return marker * 40


def _listed(
    sha: str,
    *,
    email: str = APPLICANT_EMAIL,
    message: str = "feat: 결제 재시도 추가",
    month: str = "2026-03",
    parents: int = 1,
) -> dict[str, Any]:
    return {
        "sha": sha,
        "parents": [{"sha": _sha("f")}] * parents,
        "commit": {
            "author": {"name": "홍길동", "email": email, "date": f"{month}-01T00:00:00Z"},
            "message": message,
        },
    }


def _detail(
    sha: str,
    *,
    parents: list[str] | None = None,
    files: list[dict[str, Any]] | None = None,
    email: str = APPLICANT_EMAIL,
    login: str | None = "candidate-dev",
) -> dict[str, Any]:
    parent_shas = parents if parents is not None else [_sha("f")]
    return {
        "sha": sha,
        "author": {"login": login} if login is not None else None,
        "parents": [{"sha": parent} for parent in parent_shas],
        "commit": {"author": {"name": "홍길동", "email": email}},
        "files": files
        if files is not None
        else [
            {
                "filename": "src/payment.py",
                "raw_url": f"https://raw.githubusercontent.com/example/{sha}/src/payment.py",
                "patch": "@@ -1,2 +1,2 @@",
            }
        ],
    }


class RecordingTransport(GitHubPublicTransport):
    """A transport whose HTTPS layer is replaced by a fixture map.

    Only ``_request`` and ``_bytes`` are overridden -- the URL construction, the author
    filtering, the concurrency and the ordering all remain the real code under test.
    """

    def __init__(
        self,
        responses: dict[str, Any],
        *,
        token: str | None = None,
        blob_barrier: threading.Barrier | None = None,
    ) -> None:
        super().__init__(token=token)
        self._responses = responses
        self._blob_barrier = blob_barrier
        self.requested: list[str] = []
        self.blob_urls: list[str] = []
        self.headers_seen: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def _request(self, url: str, timeout_seconds: int) -> str:
        del timeout_seconds
        with self._lock:
            self.requested.append(url)
            self.headers_seen.append(self._headers())
        if url not in self._responses:
            raise GitFetchError("public_git_fetch_failed")
        return json.dumps(self._responses[url])

    def _bytes(self, url: str, timeout_seconds: int) -> bytes:
        del timeout_seconds
        with self._lock:
            self.blob_urls.append(url)
        if self._blob_barrier is not None:
            # Deadlocks unless the blob fetches genuinely overlap, so a regression to
            # sequential fetching fails here instead of merely running slower.
            self._blob_barrier.wait(timeout=5)
        if url in self._responses:
            body = self._responses[url]
            return body if isinstance(body, bytes) else str(body).encode("utf-8")
        raise GitFetchError("public_git_file_unavailable")


def _listing_url(*, author: str | None = None, page: int = 1) -> str:
    """Built the way the transport builds it, so an address with an ``@`` still matches."""
    parameters: dict[str, Any] = {"sha": "main", "per_page": 100}
    if author is not None:
        parameters["author"] = author
    if page > 1:
        parameters["page"] = page
    return f"{API_ROOT}/commits?{urlencode(parameters)}"


def _responses(
    *,
    listing: list[dict[str, Any]],
    details: dict[str, dict[str, Any]],
    authored: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    responses: dict[str, Any] = {
        API_ROOT: {"default_branch": "main"},
        _listing_url(): listing,
        # Paging stops at a short page, so a fixture listing shorter than a full page
        # never asks for a second one. A full page would, hence the empty follow-up.
        _listing_url(page=2): [],
    }
    for sha, detail in details.items():
        responses[f"{API_ROOT}/commits/{sha}"] = detail
        for item in detail["files"]:
            # A file marked unavailable is deliberately left out of the map so its blob
            # fetch fails the way GitHub failing to serve it would.
            if item.pop("unavailable", False):
                continue
            responses[item["raw_url"]] = b"def retry_payment():\n    return True\n"
    for author, author_listing in (authored or {}).items():
        responses[_listing_url(author=author)] = author_listing
        responses[_listing_url(author=author, page=2)] = []
    return responses


def test_more_than_one_commit_is_analyzed_up_to_the_budget() -> None:
    """The whole point of the fix: evidence from a history, not from one commit.

    A candidate's contribution is spread across commits, so analyzing only the newest
    one throws away almost everything the recruiter asked to have analyzed. Which
    commits are drawn is the sampler's business; that the budget is filled from the
    history is this test's.
    """
    shas = [_sha(marker) for marker in "abcde"]
    transport = RecordingTransport(
        _responses(
            listing=[_listed(sha) for sha in shas],
            details={sha: _detail(sha) for sha in shas},
        )
    )

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_analyzed_commits=3),
        identity=None,
    )

    analyzed = [commit.commit_sha for commit in snapshot.commits]
    assert len(analyzed) == 3
    assert set(analyzed) <= set(shas)
    # commit_count still reports the whole listing, so the limits recorded on the
    # analysis can say the history was larger than the budget.
    assert snapshot.commit_count == len(shas)
    assert snapshot.pinned_head_sha == shas[0]


def test_the_whole_history_is_analyzed_when_it_fits_the_budget() -> None:
    """A small candidate project is read in full -- sampling only bites above the budget."""
    shas = [_sha(marker) for marker in "abc"]
    transport = RecordingTransport(
        _responses(
            listing=[_listed(sha) for sha in shas],
            details={sha: _detail(sha) for sha in shas},
        )
    )

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_analyzed_commits=10),
        identity=None,
    )

    assert [commit.commit_sha for commit in snapshot.commits] == shas


def test_commit_order_follows_the_listing_not_the_completion_order() -> None:
    """Concurrency must not make the same repository produce different evidence."""
    shas = [_sha(marker) for marker in "abcd"]
    transport = RecordingTransport(
        _responses(
            listing=[_listed(sha) for sha in shas],
            details={sha: _detail(sha) for sha in shas},
        )
    )

    first = transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)
    second = transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)

    assert [commit.commit_sha for commit in first.commits] == shas
    assert [commit.commit_sha for commit in second.commits] == shas


def _sampling_fixture(
    *,
    months: tuple[str, ...] = ("2025-01",),
    housekeeping: int = 0,
    documentation: frozenset[str] = frozenset(),
    authored_for: str | None = None,
) -> tuple[RecordingTransport, list[str]]:
    """A history larger than any budget, so the sampler has to choose.

    ``documentation`` names the commits whose only changed file is prose, which is what
    the screen exists to skip.
    """
    shas = [_sha(chr(ord("a") + index)) for index in range(24)]
    listing = []
    for index, sha in enumerate(shas):
        is_noise = index < housekeeping
        listing.append(
            _listed(
                sha,
                # Contiguous blocks, the way a real history reads: months do not
                # interleave, so taking the newest commits reaches only the newest month.
                month=months[min(index * len(months) // len(shas), len(months) - 1)],
                message="bump version to 2.0" if is_noise else "feat: 결제 재시도 추가",
                parents=2 if is_noise else 1,
            )
        )
    details = {}
    for sha in shas:
        prose = [
            {
                "filename": "CHANGES.rst",
                "raw_url": f"https://raw.githubusercontent.com/example/{sha}/CHANGES.rst",
                "patch": "@@ -1,2 +1,2 @@",
            }
        ]
        details[sha] = _detail(sha, files=prose if sha in documentation else None)
    authored = {authored_for: listing} if authored_for is not None else None
    return RecordingTransport(_responses(listing=listing, details=details, authored=authored)), shas


def test_the_sample_spreads_across_the_history_instead_of_taking_the_newest() -> None:
    """Recent commits show last week's work; understanding shows over a whole history.

    A candidate's grasp of their own project is what an interview asks about, so drawing
    only from the head of a long history hides everything they built earlier. Measured
    against a real 300-commit history, spreading the draw widened the span an analysis
    covers from one month to ten at the same number of API calls.
    """
    months = ("2025-01", "2025-06", "2025-11", "2026-04")
    transport, _shas = _sampling_fixture(months=months)

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_analyzed_commits=4),
        identity=None,
    )

    analyzed = {commit.commit_sha for commit in snapshot.commits}
    listed_months = {
        item["sha"]: item["commit"]["author"]["date"][:7]
        for item in transport._responses[_listing_url()]
    }
    assert {listed_months[sha] for sha in analyzed} == set(months)


def test_merges_and_version_bumps_are_not_spent_on() -> None:
    """A merge carries no authored code and nobody can be asked about a version bump."""
    transport, shas = _sampling_fixture(housekeeping=12)

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_analyzed_commits=6),
        identity=None,
    )

    analyzed = {commit.commit_sha for commit in snapshot.commits}
    assert analyzed.isdisjoint(shas[:12])


def test_a_commit_touching_no_source_is_screened_out_before_its_blobs_are_read() -> None:
    """The screen rides on a call the analysis already needs, so it is nearly free.

    Reading a commit's diff costs one detail call whatever happens, and that response
    lists the changed files -- so a commit that only edited a changelog is recognised
    without spending a blob call per file on it.
    """
    prose = frozenset(_sha(chr(ord("a") + index)) for index in range(20))
    transport, shas = _sampling_fixture(documentation=prose)

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_analyzed_commits=4),
        identity=None,
    )

    analyzed = {commit.commit_sha for commit in snapshot.commits}
    # The search is bounded to screening_multiple x the budget, so a history this padded
    # yields fewer than the budget rather than screening the whole pool to fill it.
    assert analyzed
    assert analyzed <= set(shas[20:])
    assert all("CHANGES.rst" not in url for url in transport.blob_urls)


def test_a_repository_of_only_prose_is_still_analyzed() -> None:
    """The screen must not turn a repository it does not recognise into an empty report.

    A project in a language this screen has no suffix for would otherwise analyse to
    nothing, which is worse for the recruiter than unscreened evidence.
    """
    transport, _shas = _sampling_fixture(
        documentation=frozenset(_sha(chr(ord("a") + index)) for index in range(24))
    )

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_analyzed_commits=3),
        identity=None,
    )

    assert [file.path for file in snapshot.files] == ["CHANGES.rst"] * 3


def test_the_same_submission_draws_the_same_commits_every_time() -> None:
    """Evidence has to be reproducible or a recruiter cannot audit where a question came from.

    The draw is seeded from the repository and the claimed identity rather than from a
    clock, so re-running an analysis reads the same commits.
    """
    months = ("2025-01", "2025-06", "2025-11")
    identity = CommitIdentityInput(claimed_emails=(APPLICANT_EMAIL,))
    drawn = []
    for _ in range(3):
        transport, _shas = _sampling_fixture(months=months, authored_for=APPLICANT_EMAIL)
        snapshot = transport.fetch(
            REPOSITORY_URL,
            limits=GitFetchLimits(max_analyzed_commits=5),
            identity=identity,
        )
        drawn.append([commit.commit_sha for commit in snapshot.commits])

    assert drawn[0] == drawn[1] == drawn[2]


def test_a_history_longer_than_one_page_is_paged_into_the_pool() -> None:
    """The pool the sample is drawn from is what makes spreading it possible.

    Listing is the cheap half of the fetch at a hundred commits a call, so paging wide
    costs little next to one detail call per analyzed commit.
    """
    first_page = [_listed(_sha(f"{index:x}" * 2)[:40], month="2025-01") for index in range(100)]
    second_page = [_listed("b" * 39 + str(index), month="2026-01") for index in range(5)]
    responses = _responses(listing=first_page, details={})
    responses[_listing_url()] = first_page
    responses[_listing_url(page=2)] = second_page
    for item in (*first_page, *second_page):
        detail = _detail(str(item["sha"]))
        responses[f"{API_ROOT}/commits/{item['sha']}"] = detail
        for blob in detail["files"]:
            responses[blob["raw_url"]] = b"x = 1\n"
    transport = RecordingTransport(responses)

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_analyzed_commits=2),
        identity=None,
    )

    assert _listing_url(page=2) in transport.requested
    # commit_count reports the pooled history, so the analysis can say how much was there.
    assert snapshot.commit_count == 105


def test_blob_fetches_run_concurrently() -> None:
    """A barrier proves overlap; a stopwatch would only prove the network was fast."""
    sha = _sha("a")
    file_count = 4
    files = [
        {
            "filename": f"src/module_{index}.py",
            "raw_url": f"https://raw.githubusercontent.com/example/{sha}/src/module_{index}.py",
            "patch": "@@ -1,2 +1,2 @@",
        }
        for index in range(file_count)
    ]
    transport = RecordingTransport(
        _responses(listing=[_listed(sha)], details={sha: _detail(sha, files=files)}),
        blob_barrier=threading.Barrier(file_count),
    )

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(max_workers=file_count),
        identity=None,
    )

    assert len(snapshot.files) == file_count
    assert len(transport.blob_urls) == file_count


def test_the_candidate_s_own_commits_are_requested_from_github() -> None:
    """Filtering server-side spends the rate limit on commits that can be attributed.

    Fetching the newest commits and then discarding the ones the candidate did not write
    burns the same API budget to arrive at less evidence.
    """
    theirs, someone_else = _sha("a"), _sha("b")
    transport = RecordingTransport(
        _responses(
            listing=[_listed(someone_else, email="other@example.com"), _listed(theirs)],
            details={
                theirs: _detail(theirs),
                someone_else: _detail(someone_else, email="other@example.com"),
            },
            authored={APPLICANT_EMAIL: [_listed(theirs)]},
        )
    )

    snapshot = transport.fetch(
        REPOSITORY_URL,
        limits=GitFetchLimits(),
        identity=CommitIdentityInput(claimed_emails=(APPLICANT_EMAIL,)),
    )

    assert [commit.commit_sha for commit in snapshot.commits] == [theirs]
    assert snapshot.commits[0].author_login == "candidate-dev"
    assert any("author=" in url for url in transport.requested)
    # The recorded head is still the branch head, so the analysis says which repository
    # state it read even when the commits it analyzed are older.
    assert snapshot.pinned_head_sha == someone_else


def test_an_identity_that_matches_nothing_rejects_unattributed_commits() -> None:
    """A mistyped handle must not analyze another contributor's branch commits."""
    sha = _sha("a")
    transport = RecordingTransport(
        _responses(
            listing=[_listed(sha)],
            details={sha: _detail(sha)},
            authored={"ghost": []},
        )
    )

    with pytest.raises(GitFetchError, match="candidate_github_identity_has_no_commits"):
        transport.fetch(
            REPOSITORY_URL,
            limits=GitFetchLimits(),
            identity=CommitIdentityInput(claimed_handles=("ghost",)),
        )


def test_a_repository_with_a_single_root_commit_is_analyzable() -> None:
    """A root commit has no parent, which used to fail the whole fetch.

    A one-commit repository is an ordinary candidate project. Diffing against Git's
    empty tree is the standard reading of "every line here is new".
    """
    sha = _sha("a")
    transport = RecordingTransport(
        _responses(listing=[_listed(sha)], details={sha: _detail(sha, parents=[])})
    )

    snapshot = transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)

    assert snapshot.commits[0].parent_sha == EMPTY_TREE_SHA


def test_a_deleted_file_and_a_vanished_blob_do_not_fail_the_analysis() -> None:
    """One unreadable path costs one piece of evidence, not the repository."""
    sha = _sha("a")
    detail = _detail(
        sha,
        files=[
            {
                "filename": "src/payment.py",
                "raw_url": f"https://raw.githubusercontent.com/example/{sha}/src/payment.py",
                "patch": "@@ -1,2 +1,2 @@",
            },
            {
                "filename": "src/removed.py",
                "raw_url": f"https://raw.githubusercontent.com/example/{sha}/src/removed.py",
                "status": "removed",
                "patch": "@@ -1,2 +0,0 @@",
            },
            {
                "filename": "src/gone.py",
                # Kept out of the fixture map, so its blob fetch raises the way a blob
                # GitHub no longer serves would.
                "raw_url": f"https://raw.githubusercontent.com/example/{sha}/src/gone.py",
                "patch": "@@ -1,2 +1,2 @@",
                "unavailable": True,
            },
        ],
    )
    transport = RecordingTransport(_responses(listing=[_listed(sha)], details={sha: detail}))

    snapshot = transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)

    assert [file.path for file in snapshot.files] == ["src/payment.py"]
    assert snapshot.commits[0].changed_paths == ("src/payment.py",)


def test_a_commit_with_no_readable_file_is_dropped_rather_than_stored_empty() -> None:
    """The commit domain requires at least one changed path, so an empty one is invalid."""
    readable, empty = _sha("a"), _sha("b")
    details = {
        readable: _detail(readable),
        empty: _detail(
            empty,
            files=[
                {
                    "filename": "docs/readme.md",
                    "raw_url": f"https://raw.githubusercontent.com/example/{empty}/docs/readme.md",
                    "status": "removed",
                }
            ],
        ),
    }
    transport = RecordingTransport(
        _responses(listing=[_listed(readable), _listed(empty)], details=details)
    )

    snapshot = transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)

    assert [commit.commit_sha for commit in snapshot.commits] == [readable]


def test_the_token_is_sent_as_a_header_and_never_lands_in_the_snapshot() -> None:
    """A token raises the hourly ceiling from 60 to 5000 requests.

    The constitution forbids credentials in configuration output or logs, so the token
    is asserted to appear only in request headers.
    """
    sha = _sha("a")
    secret = "ghp-local-test-token"
    transport = RecordingTransport(
        _responses(listing=[_listed(sha)], details={sha: _detail(sha)}),
        token=secret,
    )

    snapshot = transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)

    assert all(headers["Authorization"] == f"Bearer {secret}" for headers in transport.headers_seen)
    assert secret not in repr(snapshot)
    assert all(secret not in url for url in transport.requested)


def test_no_token_sends_no_authorization_header() -> None:
    sha = _sha("a")
    transport = RecordingTransport(_responses(listing=[_listed(sha)], details={sha: _detail(sha)}))

    transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)

    assert all("Authorization" not in headers for headers in transport.headers_seen)


def test_an_empty_repository_is_refused() -> None:
    transport = RecordingTransport(_responses(listing=[], details={}))

    with pytest.raises(GitFetchError, match="repository_has_no_commits"):
        transport.fetch(REPOSITORY_URL, limits=GitFetchLimits(), identity=None)


@pytest.mark.parametrize(
    "url",
    ["http://github.com/example/project", "https://gitlab.com/example/project"],
)
def test_only_public_github_https_is_accepted(url: str) -> None:
    transport = RecordingTransport({})

    with pytest.raises(GitFetchError, match="only_public_github_https_is_supported"):
        transport.fetch(url, limits=GitFetchLimits(), identity=None)


def test_a_github_branch_page_url_analyzes_that_branch() -> None:
    sha = _sha("a")
    branch_api_root = API_ROOT
    branch_listing_url = (
        f"{branch_api_root}/commits?{urlencode({'sha': 'develop', 'per_page': 100})}"
    )
    detail = _detail(sha)
    transport = RecordingTransport(
        {
            branch_api_root: {"default_branch": "main"},
            branch_listing_url: [_listed(sha)],
            f"{branch_api_root}/commits/{sha}": detail,
            detail["files"][0]["raw_url"]: b"def branch_code():\n    return True\n",
        }
    )

    snapshot = transport.fetch(
        "https://github.com/example/candidate-project/tree/develop",
        limits=GitFetchLimits(),
        identity=None,
    )

    assert snapshot.default_branch == "develop"
    assert snapshot.pinned_head_sha == sha


def test_a_file_that_is_not_utf8_is_dropped_instead_of_failing_the_analysis() -> None:
    """Downstream analysis decodes every included file as UTF-8.

    Letting one Latin-1 blob through would raise during analysis and lose the whole
    repository, so the bound drops it here.
    """
    fetcher = BoundedGitFetcher(
        _StaticSnapshotTransport(
            RepositorySnapshot(
                repository_url=REPOSITORY_URL,
                default_branch="main",
                pinned_head_sha=_sha("a"),
                files=(
                    RepositoryFile(path="src/ok.py", content=b"x = 1\n"),
                    RepositoryFile(path="src/latin1.py", content=b"s = '\xe9'\n"),
                ),
                commit_count=1,
            )
        ),
        GitFetchLimits(),
    )

    snapshot = fetcher.fetch(REPOSITORY_URL)

    assert [file.path for file in snapshot.files] == ["src/ok.py"]


def test_a_history_longer_than_the_commit_limit_is_refused() -> None:
    fetcher = BoundedGitFetcher(
        _StaticSnapshotTransport(
            RepositorySnapshot(
                repository_url=REPOSITORY_URL,
                default_branch="main",
                pinned_head_sha=_sha("a"),
                files=(),
                commit_count=501,
            )
        ),
        GitFetchLimits(max_commits=500),
    )

    with pytest.raises(GitFetchError, match="repository_commit_limit_exceeded"):
        fetcher.fetch(REPOSITORY_URL)


class _StaticSnapshotTransport:
    def __init__(self, snapshot: RepositorySnapshot) -> None:
        self._snapshot = snapshot

    def fetch(
        self,
        repository_url: str,
        *,
        limits: GitFetchLimits,
        identity: CommitIdentityInput | None = None,
    ) -> RepositorySnapshot:
        del repository_url, limits, identity
        return self._snapshot
