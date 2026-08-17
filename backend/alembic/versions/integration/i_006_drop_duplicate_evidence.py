"""Drop the untyped evidence columns that duplicate the verification guide.

``verification_guide`` already carries ``strong_answer_signals`` and
``weak_answer_signals`` as validated, non-blank tuples, and that is what the console
renders. ``good_evidence`` and ``weak_evidence`` were free-form JSON holding the same
idea with no schema, no reader, and no client sending them -- two ways to say one
thing, where only one of them was trustworthy.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_006_drop_duplicate_evidence"
down_revision: str = "m_005_requirement_criterion_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("good_evidence", "weak_evidence")


def upgrade() -> None:
    with op.batch_alter_table("evaluation_criteria") as batch:
        for column in COLUMNS:
            batch.drop_column(column)


def downgrade() -> None:
    with op.batch_alter_table("evaluation_criteria") as batch:
        for column in COLUMNS:
            batch.add_column(sa.Column(column, sa.JSON(), nullable=False, server_default="{}"))
