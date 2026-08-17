"""Store the 신입/주니어/시니어 interview level on each competency model version.

The level belongs to the versioned criteria rather than to ``positions`` because it
changes the questions that were asked: a report has to stay traceable to the level its
interview was conducted at, and a published version is immutable, so raising the level
produces a new version instead of silently reinterpreting past interviews.

The column is NOT NULL with a ``junior`` server default. Versions published before the
toggle existed were written for candidates with some experience, so junior is the
reading that leaves their interviews behaving as they did before this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_009_competency_interview_level"
down_revision: str = "m_008_report_item_criterion_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("competency_model_versions") as batch:
        batch.add_column(
            sa.Column(
                "interview_level",
                sa.String(20),
                nullable=False,
                server_default="junior",
            )
        )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: this discards the level each published version was
    # interviewed at, so existing reports lose that provenance.
    with op.batch_alter_table("competency_model_versions") as batch:
        batch.drop_column("interview_level")
