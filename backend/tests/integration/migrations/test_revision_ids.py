"""Revision ids have to fit the column Alembic stores them in.

``alembic_version.version_num`` is varchar(32). Postgres rejects a longer id when the
upgrade tries to write it, but sqlite -- which every migration test here runs on -- stores
it happily. So a too-long id passes the whole suite and then fails the first real
deployment, after the schema change has already been applied and the version row has not.

These tests measure the real revisions rather than a fixture, because the failure mode is
someone adding a descriptively-named migration, not the checker regressing.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
VERSIONS_ROOT = ROOT / "backend/alembic/versions"


def load_checker() -> Any:
    spec = importlib.util.spec_from_file_location(
        "check_migrations", ROOT / "scripts/check_migrations.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def revision_ids() -> dict[Path, str]:
    found: dict[Path, str] = {}
    for path in sorted(VERSIONS_ROOT.glob("*/*.py")):
        if path.name.startswith("__"):
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in module.body:
            target = (
                node.target.id
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                else None
            )
            if target == "revision" and node.value is not None:  # type: ignore[union-attr]
                found[path] = str(ast.literal_eval(node.value))  # type: ignore[union-attr]
    return found


def test_every_revision_id_fits_the_version_column() -> None:
    checker = load_checker()
    oversized = {
        path.relative_to(ROOT): revision
        for path, revision in revision_ids().items()
        if len(revision) > checker.MAX_REVISION_ID_LENGTH
    }

    assert not oversized, f"revision ids exceed varchar(32): {oversized}"


def test_the_checker_reports_an_oversized_revision_id() -> None:
    checker = load_checker()

    errors = checker.revision_id_errors(
        VERSIONS_ROOT / "integration/i_999_example.py",
        "m_999_a_revision_name_long_enough_to_overflow",
    )

    # Without this the only thing that catches the overflow is a Postgres upgrade.
    assert len(errors) == 1
    assert "45 characters" in errors[0]


def test_the_checker_accepts_a_revision_id_at_the_limit() -> None:
    checker = load_checker()

    errors = checker.revision_id_errors(
        VERSIONS_ROOT / "integration/i_999_example.py",
        "x" * 32,
    )

    assert errors == []
