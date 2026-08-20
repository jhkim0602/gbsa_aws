"""The four lane branches converge, and they converge on exactly one head.

The head used to be a literal here (``CURRENT_REVISION = "m_010_report_item_axis_scores"``)
and went stale twice without anyone noticing -- ``m_011`` and ``m_012`` were added and this
file kept asserting the old value, so both tests failed for a reason that had nothing to do
with the property they exist to protect. The head is now read from the migration scripts, so
adding a revision cannot break these tests, and what they check is stated directly instead:
**the script directory has one head, and an upgrade arrives at it.**

A second head is the failure this guards against. Alembic's ``upgrade heads`` (plural)
happily applies a fork, so a revision hung off an already-merged branch root -- say a new
``d_00N`` behind ``d_001_reporting`` -- deploys cleanly and then diverges forever.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[4]
MERGE_REVISION = "merge_001_lane_heads"
LANE_HEADS = (
    "a_001_company_hiring",
    "b_001_submission_analysis",
    "c_001_interview_session",
    "d_001_reporting",
)


def alembic_config(database: Path) -> Config:
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
    return config


def script_heads(database: Path) -> set[str]:
    """Whatever the migration files currently converge on, read from the scripts."""
    return set(ScriptDirectory.from_config(alembic_config(database)).get_heads())


def current_revisions(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    return {str(row[0]) for row in rows}


def test_the_migration_graph_has_exactly_one_head(tmp_path: Path) -> None:
    heads = script_heads(tmp_path / "unused.sqlite3")

    assert len(heads) == 1, f"migration graph forked into {sorted(heads)}"


def test_empty_database_upgrades_to_single_merged_head(tmp_path: Path) -> None:
    database = tmp_path / "empty.sqlite3"

    command.upgrade(alembic_config(database), "heads")

    assert current_revisions(database) == script_heads(database)
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {
        "job_requirements",
        "retrieval_documents",
        "candidate_verification_maps",
        "verification_progress",
        "question_rationales",
    } <= tables


def test_existing_four_head_snapshot_converges_to_merge(tmp_path: Path) -> None:
    database = tmp_path / "snapshot.sqlite3"
    config = alembic_config(database)
    for revision in LANE_HEADS:
        command.upgrade(config, revision)
    assert current_revisions(database) == set(LANE_HEADS)

    command.upgrade(config, "heads")

    assert current_revisions(database) == script_heads(database)
