"""Persist the interview stage for each generated question."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_016_interview_stage"
down_revision: str = "m_015_assistant_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_rationales",
        sa.Column(
            "interview_stage",
            sa.String(40),
            nullable=False,
            server_default="technical",
        ),
    )


def downgrade() -> None:
    op.drop_column("question_rationales", "interview_stage")
