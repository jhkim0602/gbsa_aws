"""Store the company-editable invitation email template and its logo.

The template columns are nullable rather than defaulting to a serialized copy of the
platform template. A NULL means "never edited", so improvements to the default copy
reach every company that has not overridden it; a stored default would freeze today's
wording into every row. ``positions.invitation_email_template`` is the per-position
override and falls back to the company column, which falls back to the platform default.

The logo lives in its own table holding the bytes directly. A mail client fetches remote
images with no credentials, so the logo has to be readable by an anonymous request --
storing it here lets one public read-only endpoint serve it without granting anonymous
access to the object store that holds applicant submissions. Uploads are capped, so the
row stays small.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_007_invitation_email_template"
down_revision: str = "m_006_drop_duplicate_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEMPLATE_TABLES = ("companies", "positions")
TEMPLATE_COLUMN = "invitation_email_template"


def upgrade() -> None:
    for table in TEMPLATE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(TEMPLATE_COLUMN, sa.JSON(), nullable=True))
    op.create_table(
        "company_logos",
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.company_id"),
            primary_key=True,
        ),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: this discards company-authored email copy and uploaded logos.
    op.drop_table("company_logos")
    for table in TEMPLATE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column(TEMPLATE_COLUMN)
