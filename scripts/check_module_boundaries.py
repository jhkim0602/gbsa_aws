from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT / "backend/src/interview_evidence"
LANE_MODULES = {
    "company_management",
    "submission_analysis",
    "interview_engine",
    "reporting",
}
PRIVATE_PACKAGES = {"domain", "repositories", "models", "internal"}


@dataclass(frozen=True, slots=True)
class Violation:
    path: Path
    line: int
    importer: str
    imported: str


def module_owner(path: Path, source_root: Path) -> str | None:
    relative = path.relative_to(source_root)
    return relative.parts[0] if relative.parts and relative.parts[0] in LANE_MODULES else None


def imported_modules(module: ast.Module) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def private_lane_import(imported: str) -> tuple[str, str] | None:
    parts = imported.split(".")
    if len(parts) < 3 or parts[0] != "interview_evidence":
        return None
    lane, package = parts[1], parts[2]
    if lane in LANE_MODULES and package in PRIVATE_PACKAGES:
        return lane, package
    return None


def scan(source_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(source_root.rglob("*.py")):
        try:
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as error:
            raise RuntimeError(f"unable to inspect {path}: {error}") from error
        owner = module_owner(path, source_root)
        importer = owner or "integration"
        for line, imported in imported_modules(module):
            target = private_lane_import(imported)
            if target is not None and target[0] != owner:
                violations.append(Violation(path, line, importer, imported))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Reject cross-lane private imports.")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="interview_evidence package root",
    )
    arguments = parser.parse_args()

    violations = scan(arguments.source_root.resolve())
    for violation in violations:
        print(
            f"{violation.path}:{violation.line}: {violation.importer} cannot import "
            f"{violation.imported}"
        )
    if violations:
        return 1
    print("Module boundary rules passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
