"""Store position interview capacity and scheduled time separately."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_012_position_interview"
down_revision: str = "m_011_submission_requirements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("positions") as batch:
        batch.add_column(sa.Column("interview_capacity", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("interview_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("positions") as batch:
        batch.drop_column("interview_at")
        batch.drop_column("interview_capacity")
