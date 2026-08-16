"""Move invitation ownership from campaigns to positions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a_003_position_owned_recruiting"
down_revision: str | None = "a_002_interviewer_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("invitations") as batch:
        batch.add_column(sa.Column("position_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("competency_model_version_id", sa.Uuid(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE invitations
            SET position_id = (
                    SELECT campaigns.position_id
                    FROM campaigns
                    WHERE campaigns.company_id = invitations.company_id
                      AND campaigns.campaign_id = invitations.campaign_id
                ),
                competency_model_version_id = (
                    SELECT campaigns.competency_model_version_id
                    FROM campaigns
                    WHERE campaigns.company_id = invitations.company_id
                      AND campaigns.campaign_id = invitations.campaign_id
                )
            """
        )
    )

    with op.batch_alter_table("invitations") as batch:
        batch.alter_column("position_id", existing_type=sa.Uuid(), nullable=False)
        batch.alter_column(
            "competency_model_version_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
        batch.create_foreign_key(
            "fk_invitations_position",
            "positions",
            ["company_id", "position_id"],
            ["company_id", "position_id"],
        )
        batch.create_foreign_key(
            "fk_invitations_criterion_version",
            "competency_model_versions",
            ["company_id", "competency_model_version_id"],
            ["company_id", "competency_model_version_id"],
        )
        batch.drop_column("campaign_id")

    op.drop_table("campaigns")


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: recreates one compatibility campaign per invitation.
    op.create_table(
        "campaigns",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("candidate_instructions", sa.String(10_000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["company_id", "position_id"],
            ["positions.company_id", "positions.position_id"],
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "competency_model_version_id"],
            [
                "competency_model_versions.company_id",
                "competency_model_versions.competency_model_version_id",
            ],
        ),
        sa.PrimaryKeyConstraint("company_id", "campaign_id"),
    )
    with op.batch_alter_table("invitations") as batch:
        batch.add_column(sa.Column("campaign_id", sa.Uuid(), nullable=True))

    op.execute(
        sa.text(
            """
            INSERT INTO campaigns (
                company_id,
                campaign_id,
                position_id,
                competency_model_version_id,
                name,
                candidate_instructions,
                status,
                row_version,
                published_at,
                closed_at
            )
            SELECT
                company_id,
                invitation_id,
                position_id,
                competency_model_version_id,
                'Restored recruiting run',
                'Restored for schema downgrade.',
                'published',
                1,
                expires_at,
                NULL
            FROM invitations
            """
        )
    )
    op.execute(sa.text("UPDATE invitations SET campaign_id = invitation_id"))

    with op.batch_alter_table("invitations") as batch:
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_foreign_key(
            "fk_invitations_campaign",
            "campaigns",
            ["company_id", "campaign_id"],
            ["company_id", "campaign_id"],
        )
        batch.drop_column("competency_model_version_id")
        batch.drop_column("position_id")
