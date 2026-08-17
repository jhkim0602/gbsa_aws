"""Let the database enforce that a job requirement names a real criterion.

``CompetencyModelVersion.requirements_reference_known_criteria`` already rejects an
unknown ``criterion_code``, but only for writes that build the aggregate. The column
is a bare ``String(40)`` in the schema, so anything reaching the table by another
route -- a backfill, a repair script, a future lane -- can leave a requirement
pointing at a criterion that does not exist. ``uq_evaluation_criteria_version_code``
already provides the referenced key, so the constraint costs nothing to add.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "m_005_requirement_criterion_fk"
down_revision: str = "m_004_hot_path_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "fk_job_requirements_criterion"


def upgrade() -> None:
    # Batch mode so the SQLite-backed test databases, which cannot ALTER a
    # constraint into place, recreate the table instead.
    with op.batch_alter_table("job_requirements") as batch:
        batch.create_foreign_key(
            CONSTRAINT,
            "evaluation_criteria",
            ["company_id", "competency_model_version_id", "criterion_code"],
            ["company_id", "competency_model_version_id", "code"],
        )


def downgrade() -> None:
    with op.batch_alter_table("job_requirements") as batch:
        batch.drop_constraint(CONSTRAINT, type_="foreignkey")
