from __future__ import annotations

import argparse
import ast
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_ROOT = ROOT / "backend/alembic/versions"
LANE_RULES = {
    "company": "a_",
    "submission": "b_",
    "interview": "c_",
    "reporting": "d_",
}
DESTRUCTIVE_CALLS = {
    "drop_column",
    "drop_constraint",
    "drop_index",
    "drop_table",
}


@dataclass(frozen=True, slots=True)
class Revision:
    path: Path
    revision: str
    down_revisions: tuple[str, ...]
    branch_labels: tuple[str, ...]


def assigned_value(module: ast.Module, name: str) -> Any:
    for node in module.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"missing {name}")


def normalize_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list)):
        return tuple(str(item) for item in value)
    raise ValueError(f"unsupported revision reference {value!r}")


def has_real_downgrade(module: ast.Module) -> bool:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade":
            return bool(node.body) and not all(
                isinstance(item, ast.Pass)
                or (
                    isinstance(item, ast.Expr)
                    and isinstance(item.value, ast.Constant)
                    and item.value.value is Ellipsis
                )
                for item in node.body
            )
    return False


def destructive_calls(module: ast.Module) -> set[str]:
    calls: set[str] = set()
    for node in ast.walk(module):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "op"
            and node.func.attr in DESTRUCTIVE_CALLS
        ):
            calls.add(node.func.attr)
    return calls


def load_revision(path: Path, lane: str, prefix: str) -> tuple[Revision | None, list[str]]:
    errors: list[str] = []
    try:
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(path))
        revision = str(assigned_value(module, "revision"))
        down_revisions = normalize_tuple(assigned_value(module, "down_revision"))
        branch_labels = normalize_tuple(assigned_value(module, "branch_labels"))
    except (OSError, SyntaxError, ValueError) as error:
        return None, [f"{path.relative_to(ROOT)}: {error}"]

    if not revision.startswith(prefix):
        errors.append(f"{path.relative_to(ROOT)}: revision must start with {prefix}")
    if lane not in branch_labels and not down_revisions:
        errors.append(f"{path.relative_to(ROOT)}: root revision must declare branch label {lane}")
    if not has_real_downgrade(module):
        errors.append(f"{path.relative_to(ROOT)}: downgrade must reverse the migration")
    destructive = destructive_calls(module)
    if destructive and "DATA_MIGRATION_NOTE" not in source:
        errors.append(
            f"{path.relative_to(ROOT)}: destructive operations {sorted(destructive)} "
            "require DATA_MIGRATION_NOTE"
        )

    return Revision(path, revision, down_revisions, branch_labels), errors


def check_lane(lane: str, prefix: str) -> list[str]:
    errors: list[str] = []
    revisions: list[Revision] = []
    for path in sorted((VERSIONS_ROOT / lane).glob("*.py")):
        if path.name.startswith("__"):
            continue
        revision, revision_errors = load_revision(path, lane, prefix)
        errors.extend(revision_errors)
        if revision is not None:
            revisions.append(revision)

    revision_ids = {revision.revision for revision in revisions}
    referenced = {
        down_revision
        for revision in revisions
        for down_revision in revision.down_revisions
        if down_revision in revision_ids
    }
    heads = revision_ids - referenced
    if len(heads) > 1:
        errors.append(f"{lane}: multiple unmerged heads {sorted(heads)}")
    return errors


def check_merge_revisions() -> list[str]:
    errors: list[str] = []
    for path in sorted((VERSIONS_ROOT / "merge").glob("*.py")):
        if path.name.startswith("__"):
            continue
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(path))
        revision = str(assigned_value(module, "revision"))
        if not revision.startswith("merge_"):
            errors.append(f"{path.relative_to(ROOT)}: merge revision must start with merge_")
        if len(normalize_tuple(assigned_value(module, "down_revision"))) < 2:
            errors.append(f"{path.relative_to(ROOT)}: merge revision must join at least two heads")
        if not has_real_downgrade(module):
            errors.append(f"{path.relative_to(ROOT)}: downgrade must reverse the merge")
    return errors


def run_orm_drift_check() -> list[str]:
    if os.getenv("CHECK_ORM_DRIFT") != "1":
        return []
    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/alembic"),
            "-c",
            str(ROOT / "backend/alembic.ini"),
            "check",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return []
    return [f"ORM drift check failed:\n{result.stdout}{result.stderr}"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lane-owned Alembic revisions.")
    parser.parse_args()

    errors = [error for lane, prefix in LANE_RULES.items() for error in check_lane(lane, prefix)]
    errors.extend(check_merge_revisions())
    errors.extend(run_orm_drift_check())

    if errors:
        print("\n".join(errors))
        return 1
    print("Migration ownership, head, downgrade and drift rules passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
