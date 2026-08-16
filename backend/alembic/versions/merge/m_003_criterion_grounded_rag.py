"""Merge criterion, retrieval, and live verification feature heads."""

from collections.abc import Sequence

revision: str = "merge_002_criterion_grounded_rag"
down_revision: tuple[str, str, str] = (
    "a_004_criterion_grounding",
    "b_002_pgvector_verification",
    "c_002_verification_progress",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the three additive feature heads."""


def downgrade() -> None:
    """Let Alembic split the graph back to the three feature heads."""
