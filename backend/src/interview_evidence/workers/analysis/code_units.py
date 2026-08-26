from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

_CONTEXT_LINES = 8
_MAX_CHANGED_LINES_PER_UNIT = 120
_STRUCTURAL_SYMBOL_PATTERNS = (
    re.compile(
        r"\b(?:class|interface|struct|enum|trait|def|func|function|fn|fun)\s+"
        r"([A-Za-z_$][\w$]*)"
    ),
    re.compile(
        r"^\s*(?:[\w<>\[\],.?]+\s+)+([A-Za-z_$][\w$]*)\s*"
        r"\([^;]*\)\s*(?:\{|=>)"
    ),
    re.compile(r"\b(?:CREATE\s+(?:TABLE|VIEW|FUNCTION|PROCEDURE))\s+([\w.]+)", re.I),
)
_VARIABLE_SYMBOL_PATTERN = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=")
_LANGUAGE_BY_SUFFIX = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".css": "css",
    ".go": "go",
    ".graphql": "graphql",
    ".h": "c",
    ".hpp": "cpp",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".md": "markdown",
    ".php": "php",
    ".proto": "protobuf",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".sh": "shell",
    ".sql": "sql",
    ".swift": "swift",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "vue",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass(frozen=True, slots=True)
class ExpandedCodeUnit:
    path: str
    language: str
    symbol: str
    line_range: tuple[int, int]
    candidate_owned_regions: tuple[tuple[int, int], ...]
    related_test_paths: tuple[str, ...]


def expand_commit_code_units(
    *,
    path: str,
    source: str,
    changed_line_ranges: tuple[tuple[int, int], ...],
    related_files: dict[str, str],
) -> tuple[ExpandedCodeUnit, ...]:
    """Build evidence from changed text regardless of the file extension.

    Python keeps its AST-level symbol expansion when possible. Every other readable
    text file, and Python that cannot be parsed, falls back to bounded commit hunks so
    an unfamiliar language never disappears from the applicant's project evidence.
    """
    if PurePosixPath(path).suffix.casefold() == ".py":
        try:
            python_units = expand_python_code_units(
                path=path,
                source=source,
                changed_line_ranges=changed_line_ranges,
                related_files=related_files,
            )
        except SyntaxError:
            python_units = ()
        if python_units:
            return python_units
    return expand_changed_text_units(
        path=path,
        source=source,
        changed_line_ranges=changed_line_ranges,
        related_files=related_files,
    )


def expand_changed_text_units(
    *,
    path: str,
    source: str,
    changed_line_ranges: tuple[tuple[int, int], ...],
    related_files: dict[str, str],
) -> tuple[ExpandedCodeUnit, ...]:
    lines = source.splitlines()
    if not lines:
        return ()
    units: list[ExpandedCodeUnit] = []
    for changed_start, changed_end in _normalized_changed_ranges(
        changed_line_ranges,
        line_count=len(lines),
    ):
        for owned_start in range(
            changed_start,
            changed_end + 1,
            _MAX_CHANGED_LINES_PER_UNIT,
        ):
            owned_end = min(changed_end, owned_start + _MAX_CHANGED_LINES_PER_UNIT - 1)
            unit_start = max(1, owned_start - _CONTEXT_LINES)
            unit_end = min(len(lines), owned_end + _CONTEXT_LINES)
            if not "\n".join(lines[unit_start - 1 : unit_end]).strip():
                continue
            symbol = _nearest_symbol(lines, owned_start, owned_end)
            related: tuple[str, ...]
            if symbol is None:
                symbol = f"{PurePosixPath(path).name}:{owned_start}-{owned_end}"
                related = ()
            else:
                related = tuple(
                    related_path
                    for related_path, content in sorted(related_files.items())
                    if symbol in content
                )
            units.append(
                ExpandedCodeUnit(
                    path=path,
                    language=_language_for_path(path),
                    symbol=symbol,
                    line_range=(unit_start, unit_end),
                    candidate_owned_regions=((owned_start, owned_end),),
                    related_test_paths=related,
                )
            )
    return tuple(units)


def expand_python_code_units(
    *,
    path: str,
    source: str,
    changed_line_ranges: tuple[tuple[int, int], ...],
    related_files: dict[str, str],
) -> tuple[ExpandedCodeUnit, ...]:
    tree = ast.parse(source)
    units: list[ExpandedCodeUnit] = []
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue
        end_line = getattr(node, "end_lineno", node.lineno)
        owned = tuple(
            (max(node.lineno, start), min(end_line, end))
            for start, end in changed_line_ranges
            if start <= end_line and end >= node.lineno
        )
        if not owned:
            continue
        related = tuple(
            related_path
            for related_path, content in sorted(related_files.items())
            if node.name in content
        )
        units.append(
            ExpandedCodeUnit(
                path=path,
                language="python",
                symbol=node.name,
                line_range=(node.lineno, end_line),
                candidate_owned_regions=owned,
                related_test_paths=related,
            )
        )
    return tuple(sorted(units, key=lambda item: item.line_range))


def _normalized_changed_ranges(
    ranges: tuple[tuple[int, int], ...],
    *,
    line_count: int,
) -> tuple[tuple[int, int], ...]:
    normalized = sorted(
        (
            max(1, min(start, line_count)),
            max(1, min(end, line_count)),
        )
        for start, end in ranges
        if start <= end and end >= 1 and start <= line_count
    )
    merged: list[tuple[int, int]] = []
    for start, end in normalized:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)


def _nearest_symbol(
    lines: list[str],
    changed_start: int,
    changed_end: int,
) -> str | None:
    search_start = max(0, changed_start - _CONTEXT_LINES - 1)
    search_end = min(len(lines), changed_end + _CONTEXT_LINES)
    candidates = [
        *range(changed_start - 1, min(len(lines), changed_end)),
        *range(changed_start - 2, search_start - 1, -1),
        *range(changed_end, search_end),
    ]
    for index in candidates:
        line = lines[index]
        for pattern in _STRUCTURAL_SYMBOL_PATTERNS:
            match = pattern.search(line)
            if match:
                return match.group(1)
    for index in range(changed_start - 1, min(len(lines), changed_end)):
        match = _VARIABLE_SYMBOL_PATTERN.search(lines[index])
        if match:
            return match.group(1)
    return None


def _language_for_path(path: str) -> str:
    name = PurePosixPath(path).name.casefold()
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "dockerfile"
    return _LANGUAGE_BY_SUFFIX.get(PurePosixPath(path).suffix.casefold(), "text")
