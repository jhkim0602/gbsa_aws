"""Add the recruiter-assistant lexical search index."""

from collections.abc import Sequence

from alembic import op

revision: str = "m_016_assistant_search_gin"
down_revision: str = "m_015_assistant_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistant_retrieval_search_text_gin
            ON assistant_retrieval_documents
            USING gin (to_tsvector('simple', search_text))
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_assistant_retrieval_search_text_gin"
        )
