from interview_evidence.workers.analysis.git_evidence_selector import (
    GitEvidenceCandidate,
    project_area,
    select_git_evidence,
)


def _candidate(
    index: int,
    *,
    commit: str = "a",
    path: str = "src/payments/service.py",
    symbol: str | None = None,
    text: str | None = None,
    ownership: float = 0.9,
    line_range: tuple[int, int] = (1, 20),
    owned: tuple[tuple[int, int], ...] = ((1, 15),),
    related_tests: tuple[str, ...] = (),
    content_hash: str | None = None,
) -> GitEvidenceCandidate:
    resolved_symbol = symbol or f"candidate_{index}"
    resolved_text = text or f"def {resolved_symbol}():\n    return {index}\n"
    return GitEvidenceCandidate(
        original_index=index,
        commit_sha=commit * 40,
        path=path,
        symbol=resolved_symbol,
        text=resolved_text,
        content_hash=content_hash or f"{index:064x}",
        ownership_confidence=ownership,
        line_range=line_range,
        candidate_owned_regions=owned,
        related_test_paths=related_tests,
    )


def _select(
    candidates: tuple[GitEvidenceCandidate, ...],
    *,
    max_units: int = 10,
    max_units_per_commit: int = 10,
    max_characters: int = 100_000,
) -> tuple[int, ...]:
    return tuple(
        item.original_index
        for item in select_git_evidence(
            candidates,
            max_units=max_units,
            max_units_per_commit=max_units_per_commit,
            max_characters=max_characters,
            max_characters_per_unit=7_000,
        )
    )


def test_prefers_owned_source_with_related_tests() -> None:
    candidates = (
        _candidate(0, ownership=0.2, owned=((1, 2),)),
        _candidate(
            1,
            path="src/payments/retry.py",
            ownership=0.9,
            related_tests=("tests/test_retry.py",),
        ),
        _candidate(2, path="migrations/0001_initial.py", ownership=0.9),
    )

    assert _select(candidates, max_units=1) == (1,)


def test_deduplicates_identical_code_before_selection() -> None:
    candidates = (
        _candidate(0, ownership=0.2, content_hash="f" * 64),
        _candidate(1, ownership=0.9, content_hash="f" * 64),
        _candidate(2),
    )

    assert _select(candidates) == (1, 2)


def test_balances_commits_and_project_areas() -> None:
    candidates = (
        _candidate(0, commit="a", path="src/payments/create.py"),
        _candidate(1, commit="a", path="src/payments/cancel.py"),
        _candidate(2, commit="b", path="src/notifications/email.py"),
        _candidate(3, commit="b", path="src/notifications/sms.py"),
    )

    selected = _select(candidates, max_units=2)

    assert {candidates[index].commit_sha for index in selected} == {"a" * 40, "b" * 40}
    assert {project_area(candidates[index].path) for index in selected} == {
        "payments",
        "notifications",
    }


def test_respects_commit_and_character_budgets() -> None:
    candidates = tuple(_candidate(index, commit="a", text="x" * 100) for index in range(5)) + (
        _candidate(5, commit="b", text="x" * 100),
    )

    selected = _select(
        candidates,
        max_units=6,
        max_units_per_commit=2,
        max_characters=300,
    )

    assert len(selected) == 3
    assert sum(candidates[index].commit_sha == "a" * 40 for index in selected) == 2


def test_selection_is_deterministic() -> None:
    candidates = tuple(
        _candidate(index, commit="a" if index % 2 == 0 else "b") for index in range(8)
    )

    assert _select(candidates, max_units=5) == _select(candidates, max_units=5)


def test_large_repository_keeps_bounded_diverse_evidence() -> None:
    candidates = tuple(
        _candidate(
            index,
            commit=format(index % 16, "x"),
            path=f"backend/src/domain_{index % 10}/service_{index // 10}.py",
            text="x" * 800,
        )
        for index in range(400)
    )

    selected = _select(
        candidates,
        max_units=60,
        max_units_per_commit=12,
        max_characters=54_000,
    )

    commit_counts = {
        commit: sum(candidates[index].commit_sha == commit for index in selected)
        for commit in {candidates[index].commit_sha for index in selected}
    }
    areas = {project_area(candidates[index].path) for index in selected}
    assert len(selected) == 60
    assert max(commit_counts.values()) <= 12
    assert len(areas) == 10


def test_project_area_skips_generic_roots() -> None:
    assert project_area("backend/src/payments/service.py") == "payments"
    assert project_area("src/main.py") == "src"
    assert project_area("manage.py") == "(root)"
