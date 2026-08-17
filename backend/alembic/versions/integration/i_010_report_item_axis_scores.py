"""Store the model's per-axis scores on each report item.

The report previously carried only ``assessment_state`` -- whether a valid Evidence
interval existed -- which is a check on the recording, not a judgement about the answer.
Reviewers had no way to see how a candidate did on correctness, depth, CS fundamentals,
ownership or communication, so they were left comparing prose.

The scores arrive from the model and are stored rather than recomputed on read, because a
report is an immutable AI original: reassessing it at display time would let two reviewers
open the same report and read different numbers. Every stored axis names the Evidence it
cited, verified to resolve before the write, so a score always traces to an answer a
reviewer can play.

JSON rather than a child table: the axes are read and written as one unit with their
report item, never queried across reports, and a five-row-per-item table would double the
report read cost for no query we make.

The column is NOT NULL with an empty-array default so reports generated before this
migration stay valid rows; the console reads an empty array as "this report has no
scores".

The revision id is short because ``alembic_version.version_num`` is varchar(32): sqlite
silently accepts an over-long id, so a longer name passes the test suite and then fails
the first real Postgres upgrade. ``scripts/check_migrations.py`` now enforces the limit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_010_report_item_axis_scores"
down_revision: str = "m_009_competency_interview_level"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("report_items") as batch:
        batch.add_column(
            sa.Column(
                "axis_assessments",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: this discards every per-axis score and rationale captured on
    # existing reports. The reports themselves stay readable without them.
    with op.batch_alter_table("report_items") as batch:
        batch.drop_column("axis_assessments")
