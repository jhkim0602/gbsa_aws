from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExpandedCodeUnit:
    path: str
    language: str
    symbol: str
    line_range: tuple[int, int]
    candidate_owned_regions: tuple[tuple[int, int], ...]
    related_test_paths: tuple[str, ...]


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
