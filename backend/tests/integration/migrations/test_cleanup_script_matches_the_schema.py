"""Keep the local cleanup script in step with the schema it deletes from.

``scripts/cleanup_test_positions.sql`` drops every position except the seeded demo one so
browser runs start from a known roster. Nothing exercises it, so it rots silently: a table
added later is simply not deleted from, and the whole transaction aborts on the first
foreign key it violates. That has already happened twice -- ``session_checkpoints`` and
friends were missing, and ``submission_chunks`` was ordered after the analyses it
references -- each time surfacing as two unrelated-looking browser test failures.

Both failure modes are mechanical, so they are checked against the migrated schema rather
than against a fixture.
"""

from __future__ import annotations

import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Inspector

ROOT = Path(__file__).resolve().parents[4]
CLEANUP_SCRIPT = ROOT / "scripts/cleanup_test_positions.sql"

# A row belongs to a position through one of these. They are the aggregate roots the
# script builds its temp tables from, plus the report and git descendants that hang off
# those roots without carrying an invitation id of their own.
SCOPING_COLUMNS = frozenset(
    {
        "position_id",
        "competency_model_version_id",
        "invitation_id",
        "interview_session_id",
        "submission_id",
        "report_id",
        "report_item_id",
        "repository_analysis_id",
        "git_commit_analysis_id",
    }
)


def _migrated_inspector(database: Path) -> Inspector:
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
    command.upgrade(config, "heads")
    return inspect(create_engine(f"sqlite+pysqlite:///{database}"))


def _deleted_tables() -> dict[str, int]:
    """Every table the script deletes from, mapped to where it does so last."""
    script = CLEANUP_SCRIPT.read_text(encoding="utf-8")
    return {match.group(1): match.start() for match in re.finditer(r"DELETE FROM (\w+)", script)}


def test_the_script_deletes_from_every_position_scoped_table(tmp_path: Path) -> None:
    migrated = _migrated_inspector(tmp_path / "migrated.sqlite3")
    deleted = _deleted_tables()

    scoped = {
        table
        for table in migrated.get_table_names()
        if SCOPING_COLUMNS.intersection(column["name"] for column in migrated.get_columns(table))
    }

    # Left behind, the rows either survive as orphans or abort the whole transaction.
    assert scoped - set(deleted) == set()


def test_the_script_deletes_children_before_their_parents(tmp_path: Path) -> None:
    migrated = _migrated_inspector(tmp_path / "migrated.sqlite3")
    deleted = _deleted_tables()

    # Every FK here is NO ACTION, so a parent deleted first raises instead of cascading.
    inverted = {
        (child, key["referred_table"])
        for child in deleted
        for key in migrated.get_foreign_keys(child)
        if key["referred_table"] in deleted
        and key["referred_table"] != child
        and deleted[child] > deleted[key["referred_table"]]
    }

    assert inverted == set()
