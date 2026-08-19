"""Connect position requirements to typed applicant submissions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_011_submission_requirements"
down_revision: str = "m_010_report_item_axis_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_REQUIREMENTS = [
    {"material_type": "resume", "required": True, "enabled": True, "instructions": None},
    {
        "material_type": "cover_letter",
        "required": True,
        "enabled": True,
        "instructions": None,
    },
    {
        "material_type": "career_description",
        "required": False,
        "enabled": True,
        "instructions": None,
    },
    {"material_type": "projects", "required": False, "enabled": True, "instructions": None},
    {
        "material_type": "portfolio",
        "required": False,
        "enabled": True,
        "instructions": None,
    },
]


def upgrade() -> None:
    for table_name in ("positions", "invitations"):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(sa.Column("submission_requirements", sa.JSON(), nullable=True))
        table = sa.table(
            table_name,
            sa.column("submission_requirements", sa.JSON()),
        )
        op.get_bind().execute(
            sa.update(table)
            .where(table.c.submission_requirements.is_(None))
            .values(submission_requirements=DEFAULT_REQUIREMENTS)
        )
        with op.batch_alter_table(table_name) as batch:
            batch.alter_column("submission_requirements", nullable=False)

    with op.batch_alter_table("submissions") as batch:
        batch.add_column(sa.Column("material_type", sa.String(40), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE submissions
            SET material_type = CASE
                WHEN source_type = 'public_git' THEN 'projects'
                WHEN source_type = 'cover_letter' THEN 'cover_letter'
                WHEN source_type = 'resume' THEN 'resume'
                ELSE 'resume'
            END
            """
        )
    )
    with op.batch_alter_table("submissions") as batch:
        batch.alter_column("material_type", nullable=False)
        batch.create_index(
            "ix_submissions_invitation_material",
            ["company_id", "invitation_id", "material_type"],
        )


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_index("ix_submissions_invitation_material")
        batch.drop_column("material_type")
    for table_name in ("invitations", "positions"):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column("submission_requirements")
