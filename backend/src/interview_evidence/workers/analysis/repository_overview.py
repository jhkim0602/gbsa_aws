from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

from interview_evidence.workers.analysis.git_fetch import RepositorySnapshot

MAX_OVERVIEW_DOCUMENT_CHARACTERS = 7_000
MAX_STRUCTURE_PATH_DEPTH = 4


@dataclass(frozen=True, slots=True)
class RepositoryOverviewDocument:
    path: str
    section: str
    text: str
    end_line: int | None = None


def build_repository_overview_documents(
    snapshot: RepositorySnapshot,
) -> tuple[RepositoryOverviewDocument, ...]:
    documents: list[RepositoryOverviewDocument] = []
    structure = _structure_document(snapshot)
    if structure is not None:
        documents.append(structure)
    seen_content: set[str] = set()
    for file in sorted(
        (file for file in snapshot.files if not file.commit_sha and _is_overview_path(file.path)),
        key=lambda item: item.path.casefold(),
    ):
        text = file.content.decode("utf-8").strip()
        if not text or text in seen_content:
            continue
        seen_content.add(text)
        bounded = text[:MAX_OVERVIEW_DOCUMENT_CHARACTERS]
        section = _section_for(file.path)
        documents.append(
            RepositoryOverviewDocument(
                path=file.path,
                section=section,
                text=(
                    "저장소 전체 구조를 이해하기 위한 최신 HEAD 근거입니다.\n"
                    f"파일: {file.path}\n"
                    f"종류: {section}\n\n"
                    f"{bounded}"
                )[:MAX_OVERVIEW_DOCUMENT_CHARACTERS],
                end_line=max(1, bounded.count("\n") + 1),
            )
        )
    return tuple(documents)


def _structure_document(snapshot: RepositorySnapshot) -> RepositoryOverviewDocument | None:
    if not snapshot.tree_paths:
        return None
    top_level_counts = Counter(PurePosixPath(path).parts[0] for path in snapshot.tree_paths)
    extensions = Counter(
        PurePosixPath(path).suffix.casefold()
        for path in snapshot.tree_paths
        if PurePosixPath(path).suffix
    )
    lines = [
        "저장소 전체 구조를 이해하기 위한 최신 HEAD 요약입니다.",
        f"기본 브랜치: {snapshot.default_branch}",
        f"고정 커밋: {snapshot.pinned_head_sha}",
        f"확인한 파일 경로: {len(snapshot.tree_paths)}개",
        "",
        "최상위 영역:",
        *(
            f"- {name}: {count}개 파일"
            for name, count in sorted(
                top_level_counts.items(),
                key=lambda item: (-item[1], item[0].casefold()),
            )
        ),
        "",
        "주요 확장자:",
        *(f"- {extension}: {count}개" for extension, count in extensions.most_common(12)),
        "",
        f"폴더·파일 구조(깊이 {MAX_STRUCTURE_PATH_DEPTH}단계):",
    ]
    for path in snapshot.tree_paths:
        if len(PurePosixPath(path).parts) > MAX_STRUCTURE_PATH_DEPTH:
            continue
        candidate = f"- {path}"
        if len("\n".join((*lines, candidate))) > MAX_OVERVIEW_DOCUMENT_CHARACTERS:
            break
        lines.append(candidate)
    return RepositoryOverviewDocument(
        path=".",
        section="repository_structure",
        text="\n".join(lines),
    )


def _section_for(path: str) -> str:
    normalized = path.casefold()
    name = PurePosixPath(normalized).name
    if name.startswith("readme"):
        return "readme"
    if "architecture" in normalized:
        return "architecture"
    if name in {"dockerfile", "compose.yml", "compose.yaml", "docker-compose.yml"}:
        return "deployment"
    if normalized.startswith(("infra/", "infrastructure/", ".github/workflows/")):
        return "infrastructure"
    return "project_configuration"


def _is_overview_path(path: str) -> bool:
    normalized = path.casefold()
    name = PurePosixPath(normalized).name
    if name.startswith("readme") or "architecture" in normalized:
        return True
    if name in {
        "cargo.toml",
        "compose.yaml",
        "compose.yml",
        "docker-compose.yaml",
        "docker-compose.yml",
        "dockerfile",
        "go.mod",
        "package.json",
        "pom.xml",
        "pyproject.toml",
        "requirements.txt",
        "settings.gradle",
        "settings.gradle.kts",
    }:
        return True
    return normalized.startswith(("infra/", "infrastructure/", ".github/workflows/"))
