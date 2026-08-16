"""Add reusable company AI interviewer profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a_002_interviewer_profiles"
down_revision: str | None = "m_002_runtime_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("positions") as batch:
        batch.add_column(sa.Column("role_type", sa.String(100)))
        batch.add_column(sa.Column("headcount", sa.Integer()))
        batch.add_column(sa.Column("recruitment_start_at", sa.Date()))
        batch.add_column(sa.Column("recruitment_end_at", sa.Date()))
    op.create_table(
        "interviewer_profiles",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("interviewer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("tone", sa.String(30), nullable=False),
        sa.Column("voice_id", sa.String(100), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.PrimaryKeyConstraint("company_id", "interviewer_profile_id"),
        sa.CheckConstraint("row_version >= 1", name="interviewer_profile_row_version"),
    )
    op.create_index(
        "ix_interviewer_profiles_company_created",
        "interviewer_profiles",
        ["company_id", "created_at"],
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: removes only reusable profile definitions;
    # published persona snapshots remain.
    op.drop_index(
        "ix_interviewer_profiles_company_created",
        table_name="interviewer_profiles",
    )
    op.drop_table("interviewer_profiles")
    with op.batch_alter_table("positions") as batch:
        batch.drop_column("recruitment_end_at")
        batch.drop_column("recruitment_start_at")
        batch.drop_column("headcount")
        batch.drop_column("role_type")
