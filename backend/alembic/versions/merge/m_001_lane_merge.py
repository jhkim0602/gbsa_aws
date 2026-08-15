"""Merge the four independently delivered lane roots."""

from collections.abc import Sequence

revision: str = "merge_001_lane_heads"
down_revision: tuple[str, str, str, str] = (
    "a_001_company_hiring",
    "b_001_submission_analysis",
    "c_001_interview_session",
    "d_001_reporting",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the lane heads without mutating their already-created schema."""


def downgrade() -> None:
    """Let Alembic split the version graph back to the four lane heads."""
