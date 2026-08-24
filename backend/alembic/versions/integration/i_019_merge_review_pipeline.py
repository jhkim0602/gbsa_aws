"""Merge the review backfill and recruiting pipeline migration branches."""

from collections.abc import Sequence

revision: str = "m_019_merge_review_pipeline"
down_revision: tuple[str, str] = (
    "m_018_recruiting_pipeline",
    "m_018_review_state_backfill",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
