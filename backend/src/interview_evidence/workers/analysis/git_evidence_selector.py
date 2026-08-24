from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

_GENERIC_PROJECT_ROOTS = frozenset(
    {
        "app",
        "apps",
        "backend",
        "client",
        "frontend",
        "lib",
        "libs",
        "packages",
        "server",
        "services",
        "src",
    }
)
_LOW_VALUE_PATH_PARTS = frozenset(
    {
        ".venv",
        "build",
        "dist",
        "generated",
        "migrations",
        "node_modules",
        "vendor",
    }
)


@dataclass(frozen=True, slots=True)
class GitEvidenceCandidate:
    original_index: int
    commit_sha: str
    path: str
    symbol: str
    text: str
    content_hash: str
    ownership_confidence: float
    line_range: tuple[int, int]
    candidate_owned_regions: tuple[tuple[int, int], ...]
    related_test_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectedGitEvidence:
    original_index: int
    score: float
    project_area: str
    selection_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _RankedCandidate:
    candidate: GitEvidenceCandidate
    score: float
    project_area: str
    selection_reasons: tuple[str, ...]


def select_git_evidence(
    candidates: tuple[GitEvidenceCandidate, ...],
    *,
    max_units: int,
    max_units_per_commit: int,
    max_characters: int,
    max_characters_per_unit: int,
) -> tuple[SelectedGitEvidence, ...]:
    if not candidates or max_units <= 0 or max_units_per_commit <= 0 or max_characters <= 0:
        return ()
    ranked = _deduplicated_ranked_candidates(candidates)
    selected: list[SelectedGitEvidence] = []
    selected_characters = 0
    commit_counts: dict[str, int] = {}
    area_counts: dict[str, int] = {}
    path_counts: dict[str, int] = {}
    symbol_counts: dict[str, int] = {}
    remaining = list(ranked)
    while remaining and len(selected) < max_units:
        eligible = [
            item
            for item in remaining
            if commit_counts.get(item.candidate.commit_sha, 0) < max_units_per_commit
            and selected_characters + min(len(item.candidate.text), max_characters_per_unit)
            <= max_characters
        ]
        if not eligible:
            break
        chosen = min(
            eligible,
            key=lambda item: (
                -_diversified_score(
                    item,
                    commit_counts=commit_counts,
                    area_counts=area_counts,
                    path_counts=path_counts,
                    symbol_counts=symbol_counts,
                ),
                item.candidate.commit_sha,
                item.candidate.path,
                item.candidate.line_range[0],
                item.candidate.symbol,
                item.candidate.original_index,
            ),
        )
        remaining.remove(chosen)
        candidate = chosen.candidate
        selected.append(
            SelectedGitEvidence(
                original_index=candidate.original_index,
                score=round(chosen.score, 4),
                project_area=chosen.project_area,
                selection_reasons=chosen.selection_reasons,
            )
        )
        selected_characters += min(len(candidate.text), max_characters_per_unit)
        commit_counts[candidate.commit_sha] = commit_counts.get(candidate.commit_sha, 0) + 1
        area_counts[chosen.project_area] = area_counts.get(chosen.project_area, 0) + 1
        path_counts[candidate.path] = path_counts.get(candidate.path, 0) + 1
        symbol_counts[candidate.symbol] = symbol_counts.get(candidate.symbol, 0) + 1
    return tuple(selected)


def project_area(path: str) -> str:
    parts = PurePosixPath(path).parts
    directories = parts[:-1]
    for part in directories:
        if part.casefold() not in _GENERIC_PROJECT_ROOTS:
            return part
    if directories:
        return directories[-1]
    return "(root)"


def _deduplicated_ranked_candidates(
    candidates: tuple[GitEvidenceCandidate, ...],
) -> tuple[_RankedCandidate, ...]:
    by_content_hash: dict[str, _RankedCandidate] = {}
    for candidate in candidates:
        ranked = _rank(candidate)
        existing = by_content_hash.get(candidate.content_hash)
        if existing is None or _rank_order(ranked) < _rank_order(existing):
            by_content_hash[candidate.content_hash] = ranked
    return tuple(sorted(by_content_hash.values(), key=_rank_order))


def _rank(candidate: GitEvidenceCandidate) -> _RankedCandidate:
    start_line, end_line = candidate.line_range
    total_lines = max(1, end_line - start_line + 1)
    owned_lines = sum(end - start + 1 for start, end in candidate.candidate_owned_regions)
    coverage = min(1.0, owned_lines / total_lines)
    path_parts = {part.casefold() for part in PurePosixPath(candidate.path).parts}
    filename = PurePosixPath(candidate.path).name.casefold()
    is_test = "test" in path_parts or "tests" in path_parts or filename.startswith("test_")
    is_low_value = bool(path_parts & _LOW_VALUE_PATH_PARTS)
    score = candidate.ownership_confidence * 3.0
    score += coverage * 2.0
    score += min(1.0, owned_lines / 25) * 1.5
    reasons: list[str] = []
    if candidate.ownership_confidence >= 0.7:
        reasons.append("strong_candidate_ownership")
    elif candidate.ownership_confidence > 0:
        reasons.append("candidate_ownership_signal")
    if coverage >= 0.5:
        reasons.append("substantial_changed_scope")
    if candidate.related_test_paths:
        score += min(1.5, 0.75 + len(candidate.related_test_paths) * 0.15)
        reasons.append("related_tests")
    if not is_test and not is_low_value:
        score += 0.5
        reasons.append("production_source")
    elif is_test:
        score += 0.15
        reasons.append("test_implementation")
    if 4 <= total_lines <= 160:
        score += 0.5
        reasons.append("reviewable_scope")
    elif total_lines <= 2:
        score -= 0.5
    if candidate.symbol.startswith("__") and candidate.symbol.endswith("__"):
        score -= 0.5
    if is_low_value:
        score -= 2.0
        reasons.append("low_priority_path")
    return _RankedCandidate(
        candidate=candidate,
        score=score,
        project_area=project_area(candidate.path),
        selection_reasons=tuple(reasons),
    )


def _rank_order(item: _RankedCandidate) -> tuple[float, str, str, int, str, int]:
    return (
        -item.score,
        item.candidate.commit_sha,
        item.candidate.path,
        item.candidate.line_range[0],
        item.candidate.symbol,
        item.candidate.original_index,
    )


def _diversified_score(
    item: _RankedCandidate,
    *,
    commit_counts: dict[str, int],
    area_counts: dict[str, int],
    path_counts: dict[str, int],
    symbol_counts: dict[str, int],
) -> float:
    candidate = item.candidate
    return (
        item.score
        - commit_counts.get(candidate.commit_sha, 0) * 0.45
        - area_counts.get(item.project_area, 0) * 0.35
        - path_counts.get(candidate.path, 0) * 0.8
        - symbol_counts.get(candidate.symbol, 0) * 0.75
    )
