from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[4]
MERGE_REVISION = "merge_001_lane_heads"
CURRENT_REVISION = "m_010_report_item_axis_scores"
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


def current_revisions(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    return {str(row[0]) for row in rows}


def test_empty_database_upgrades_to_single_merged_head(tmp_path: Path) -> None:
    database = tmp_path / "empty.sqlite3"

    command.upgrade(alembic_config(database), "heads")

    assert current_revisions(database) == {CURRENT_REVISION}
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

    assert current_revisions(database) == {CURRENT_REVISION}
