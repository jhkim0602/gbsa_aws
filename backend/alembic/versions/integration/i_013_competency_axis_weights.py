"""Let a company weight the five scoring axes against each other.

``EvaluationCriterion.weight`` has existed since ``a_001`` and is written by the hiring
wizard, but no scoring code ever read it: a criterion score was the plain mean of its five
axes, and a report score the plain mean of its criteria. So a company saying "system design
matters three times as much as collaboration" changed nothing about the number a recruiter
compares candidates on. Weighting the criteria is only half of that, though -- the axes
themselves also matter differently per role, and a senior backend interview that weighs 깊이
like 설명력 is not measuring what the recruiter asked for.

The weights live on the version rather than on ``AssessmentAxis`` because that is a ``Final``
prompt constant shared by every tenant, and a weight is one company's choice. They are not
per criterion either: five numbers per criterion is a form nobody fills in correctly, and the
company's per-criterion judgement is already expressed by ``weight``.

JSON rather than five columns: they are read and written as one unit with their version and
never queried across versions, and the axis key set is owned by
``shared.assessment_axes`` rather than by this schema.

The column is NOT NULL with an empty-object default so every version published before this
migration stays a valid row. The domain reads an empty mapping as equal weight, which is
exactly how those versions were actually scored -- so there is no backfill to write, and
adding one would silently restate history.

Validation is deliberately not here. ``CompetencyModelVersion`` refuses an unknown key, a
partial mapping and a negative weight at construction time, because the version is frozen and
locks on publish: a bad mapping caught during aggregation would surface after the interview
has already happened, with nothing left to fix.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_013_axis_weights"
down_revision: str = "m_012_position_interview"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("competency_model_versions") as batch:
        batch.add_column(
            sa.Column(
                "axis_weights",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: this discards every per-axis weight a company configured.
    # Scoring falls back to the equal weighting an empty mapping already means, so reports
    # stay readable -- but a report generated while the weights existed keeps the numbers
    # it froze, and those numbers will no longer be reproducible from the version.
    with op.batch_alter_table("competency_model_versions") as batch:
        batch.drop_column("axis_weights")
