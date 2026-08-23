"""Add the recruiter-assistant report search projection."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "m_015_assistant_retrieval"
down_revision: str = "m_014_report_scoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "assistant_retrieval_documents",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_document_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("report_item_id", sa.Uuid()),
        sa.Column("criterion_id", sa.Uuid()),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("source_version", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("protected_text", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("embedding_version", sa.String(100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("company_id", "assistant_document_id"),
    )
    op.create_index(
        "ix_assistant_retrieval_scope",
        "assistant_retrieval_documents",
        ["company_id", "position_id", "document_type"],
    )
    op.create_index(
        "ix_assistant_retrieval_report",
        "assistant_retrieval_documents",
        ["company_id", "report_id"],
    )
    op.create_index(
        "ix_assistant_retrieval_invitation",
        "assistant_retrieval_documents",
        ["company_id", "invitation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_retrieval_invitation",
        table_name="assistant_retrieval_documents",
    )
    op.drop_index(
        "ix_assistant_retrieval_report",
        table_name="assistant_retrieval_documents",
    )
    op.drop_index(
        "ix_assistant_retrieval_scope",
        table_name="assistant_retrieval_documents",
    )
    op.drop_table("assistant_retrieval_documents")
