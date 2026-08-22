"""Guard the ORM declarations against drifting from the Alembic migrations.

Alembic owns the DDL that production runs, but most tests build their schema with
``Base.metadata.create_all``. When the two disagree those tests validate a schema that
never ships -- the divergence that let a single-column primary key stand in for a
composite ``(company_id, <own_id>)`` one. Comparing both schemas on the same SQLite
dialect keeps that class of drift from returning silently.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from interview_evidence.capacity_management.repository import CapacityReservationRow
from interview_evidence.company_management.repositories.postgres import Base as CompanyBase
from interview_evidence.interview_engine.application.idempotency import (
    InterviewCommandResultRow,
)
from interview_evidence.interview_engine.repositories.postgres import Base as InterviewBase
from interview_evidence.recruiting_assistant.repository import Base as AssistantBase
from interview_evidence.reporting.repositories.postgres import Base as ReportingBase
from interview_evidence.shared.persistence import Base as SharedBase
from interview_evidence.submission_analysis.repositories.postgres import Base as SubmissionBase
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Inspector

ROOT = Path(__file__).resolve().parents[4]
LANE_BASES = (
    CompanyBase,
    SubmissionBase,
    InterviewBase,
    ReportingBase,
    AssistantBase,
    SharedBase,
)

# Imported for its side effect of registering the table on the interview engine Base.
assert InterviewCommandResultRow.__tablename__ == "interview_command_results"
assert CapacityReservationRow.__tablename__ == "capacity_reservations"


def _migrated_inspector(database: Path) -> Inspector:
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
    command.upgrade(config, "heads")
    return inspect(create_engine(f"sqlite+pysqlite:///{database}"))


def _orm_inspector(database: Path) -> Inspector:
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    for base in LANE_BASES:
        base.metadata.create_all(engine)
    return inspect(engine)


def _shared_tables(migrated: Inspector, orm: Inspector) -> tuple[str, ...]:
    return tuple(sorted(set(migrated.get_table_names()) & set(orm.get_table_names())))


def test_orm_declares_every_migrated_table(tmp_path: Path) -> None:
    migrated = _migrated_inspector(tmp_path / "migrated.sqlite3")
    orm = _orm_inspector(tmp_path / "orm.sqlite3")

    missing = set(migrated.get_table_names()) - set(orm.get_table_names()) - {"alembic_version"}
    assert missing == set()


def test_primary_keys_match_the_migrations(tmp_path: Path) -> None:
    migrated = _migrated_inspector(tmp_path / "migrated.sqlite3")
    orm = _orm_inspector(tmp_path / "orm.sqlite3")

    mismatched = {
        table: (
            migrated.get_pk_constraint(table)["constrained_columns"],
            orm.get_pk_constraint(table)["constrained_columns"],
        )
        for table in _shared_tables(migrated, orm)
        if migrated.get_pk_constraint(table)["constrained_columns"]
        != orm.get_pk_constraint(table)["constrained_columns"]
    }
    assert mismatched == {}


def test_indexes_match_the_migrations(tmp_path: Path) -> None:
    migrated = _migrated_inspector(tmp_path / "migrated.sqlite3")
    orm = _orm_inspector(tmp_path / "orm.sqlite3")

    def named(inspector: Inspector, table: str) -> dict[str, list[str]]:
        return {
            index["name"]: list(index["column_names"])
            for index in inspector.get_indexes(table)
            if index["name"] is not None
        }

    mismatched = {
        table: (named(migrated, table), named(orm, table))
        for table in _shared_tables(migrated, orm)
        if named(migrated, table) != named(orm, table)
    }
    assert mismatched == {}


def test_foreign_keys_match_the_migrations(tmp_path: Path) -> None:
    migrated = _migrated_inspector(tmp_path / "migrated.sqlite3")
    orm = _orm_inspector(tmp_path / "orm.sqlite3")

    def keyed(
        inspector: Inspector, table: str
    ) -> set[tuple[str, tuple[str, ...], tuple[str, ...]]]:
        return {
            (
                key["referred_table"],
                tuple(key["constrained_columns"]),
                tuple(key["referred_columns"]),
            )
            for key in inspector.get_foreign_keys(table)
        }

    mismatched = {
        table: (sorted(keyed(migrated, table)), sorted(keyed(orm, table)))
        for table in _shared_tables(migrated, orm)
        if keyed(migrated, table) != keyed(orm, table)
    }
    assert mismatched == {}


def test_unique_constraints_match_the_migrations(tmp_path: Path) -> None:
    migrated = _migrated_inspector(tmp_path / "migrated.sqlite3")
    orm = _orm_inspector(tmp_path / "orm.sqlite3")

    def uniques(inspector: Inspector, table: str) -> set[tuple[str, ...]]:
        return {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table)
        }

    mismatched = {
        table: (sorted(uniques(migrated, table)), sorted(uniques(orm, table)))
        for table in _shared_tables(migrated, orm)
        if uniques(migrated, table) != uniques(orm, table)
    }
    assert mismatched == {}
