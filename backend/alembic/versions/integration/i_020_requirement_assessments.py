"""Store requirement fulfillment separately from interview scores."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_020_requirement_assessments"
down_revision: str = "m_019_merge_review_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.add_column(
            sa.Column(
                "requirement_assessments",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("requirement_assessments")
