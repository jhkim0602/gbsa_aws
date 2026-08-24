"""Add configurable recruiting stages and applicant capacity."""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "m_018_recruiting_pipeline"
down_revision: str = "m_017_capacity_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_STAGES = ("보류", "검토", "1차 합격", "최종합격", "불합격")


def upgrade() -> None:
    with op.batch_alter_table("positions") as batch:
        batch.add_column(sa.Column("applicant_capacity", sa.Integer(), nullable=True))

    op.create_table(
        "recruiting_stages",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("recruiting_stage_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "position_id"],
            ["positions.company_id", "positions.position_id"],
            name="fk_recruiting_stages_position",
        ),
        sa.PrimaryKeyConstraint("company_id", "recruiting_stage_id"),
        sa.UniqueConstraint(
            "company_id",
            "position_id",
            "name",
            name="uq_recruiting_stages_position_name",
        ),
    )
    op.create_index(
        "ix_recruiting_stages_position",
        "recruiting_stages",
        ["company_id", "position_id"],
    )

    with op.batch_alter_table("invitations") as batch:
        batch.add_column(sa.Column("recruiting_stage_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column(
                "pipeline_row_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch.create_foreign_key(
            "fk_invitations_recruiting_stage",
            "recruiting_stages",
            ["company_id", "recruiting_stage_id"],
            ["company_id", "recruiting_stage_id"],
        )
    op.create_index(
        "ix_invitations_recruiting_stage",
        "invitations",
        ["company_id", "recruiting_stage_id"],
    )

    connection = op.get_bind()
    positions = sa.table(
        "positions",
        sa.column("company_id", sa.Uuid()),
        sa.column("position_id", sa.Uuid()),
    )
    stages = sa.table(
        "recruiting_stages",
        sa.column("company_id", sa.Uuid()),
        sa.column("recruiting_stage_id", sa.Uuid()),
        sa.column("position_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("row_version", sa.Integer()),
    )
    invitations = sa.table(
        "invitations",
        sa.column("company_id", sa.Uuid()),
        sa.column("position_id", sa.Uuid()),
        sa.column("status", sa.String()),
        sa.column("recruiting_stage_id", sa.Uuid()),
    )
    for company_id, position_id in connection.execute(
        sa.select(positions.c.company_id, positions.c.position_id)
    ):
        stage_ids = {name: uuid4() for name in DEFAULT_STAGES}
        connection.execute(
            stages.insert(),
            [
                {
                    "company_id": company_id,
                    "recruiting_stage_id": stage_ids[name],
                    "position_id": position_id,
                    "name": name,
                    "sort_order": sort_order,
                    "row_version": 1,
                }
                for sort_order, name in enumerate(DEFAULT_STAGES)
            ],
        )
        status_groups = {
            "보류": ("interrupted", "expired", "revoked"),
            "1차 합격": ("completed",),
            "최종합격": ("reviewed", "deleted"),
        }
        assigned_statuses = tuple(
            status for statuses in status_groups.values() for status in statuses
        )
        for stage_name, statuses in status_groups.items():
            connection.execute(
                invitations.update()
                .where(
                    invitations.c.company_id == company_id,
                    invitations.c.position_id == position_id,
                    invitations.c.status.in_(statuses),
                )
                .values(recruiting_stage_id=stage_ids[stage_name])
            )
        connection.execute(
            invitations.update()
            .where(
                invitations.c.company_id == company_id,
                invitations.c.position_id == position_id,
                invitations.c.status.not_in(assigned_statuses),
            )
            .values(recruiting_stage_id=stage_ids["검토"])
        )


def downgrade() -> None:
    op.drop_index("ix_invitations_recruiting_stage", table_name="invitations")
    with op.batch_alter_table("invitations") as batch:
        batch.drop_constraint("fk_invitations_recruiting_stage", type_="foreignkey")
        batch.drop_column("pipeline_row_version")
        batch.drop_column("recruiting_stage_id")
    op.drop_index("ix_recruiting_stages_position", table_name="recruiting_stages")
    op.drop_table("recruiting_stages")
    with op.batch_alter_table("positions") as batch:
        batch.drop_column("applicant_capacity")
