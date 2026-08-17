"""Snapshot the criterion name onto each report item.

The review report showed a bare UUID because ``report_items`` stored only
``criterion_id`` and Lane D may not read Lane A's criterion tables. Copying the name at
generation time also keeps an existing report readable after its criterion version is
deleted under a retention or privacy request, which a join could not.

The column is NOT NULL with an empty-string default so reports generated before this
migration stay valid rows; the console falls back to the id when the name is empty.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_008_report_item_criterion_name"
down_revision: str = "m_007_invitation_email_template"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("report_items") as batch:
        batch.add_column(
            sa.Column(
                "criterion_name",
                sa.String(200),
                nullable=False,
                server_default="",
            )
        )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: this discards the criterion names captured on existing reports.
    with op.batch_alter_table("report_items") as batch:
        batch.drop_column("criterion_name")
