"""Add tenant-scoped hybrid retrieval and candidate verification maps."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "b_002_pgvector_verification"
down_revision: str | None = "a_003_position_owned_recruiting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "retrieval_documents",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("retrieval_document_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid()),
        sa.Column("invitation_id", sa.Uuid()),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid()),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("protected_text", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("embedding_version", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("path", sa.String(1000)),
        sa.Column("symbol", sa.String(500)),
        sa.Column("ownership_confidence", sa.Numeric(5, 4)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("company_id", "retrieval_document_id"),
        sa.CheckConstraint(
            "ownership_confidence IS NULL OR ownership_confidence BETWEEN 0 AND 1",
            name="retrieval_ownership_confidence",
        ),
    )
    op.create_index(
        "ix_retrieval_scope",
        "retrieval_documents",
        [
            "company_id",
            "applicant_id",
            "invitation_id",
            "competency_model_version_id",
            "criterion_id",
        ],
    )
    op.create_index(
        "ix_retrieval_source",
        "retrieval_documents",
        ["company_id", "source_id"],
    )

    op.create_table(
        "candidate_claims",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_claim_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("claim_type", sa.String(40), nullable=False),
        sa.Column("neutral_text", sa.String(4000), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extraction_version", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "candidate_claim_id"),
    )
    op.create_index(
        "ix_candidate_claim_scope",
        "candidate_claims",
        ["company_id", "applicant_id", "invitation_id", "criterion_id"],
    )

    op.create_table(
        "claim_conflicts",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("claim_conflict_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("left_claim_id", sa.Uuid(), nullable=False),
        sa.Column("right_claim_id", sa.Uuid(), nullable=False),
        sa.Column("conflict_type", sa.String(50), nullable=False),
        sa.Column("verification_objective", sa.String(4000), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "claim_conflict_id"),
    )

    op.create_table(
        "verification_targets",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("verification_target_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("objective", sa.String(4000), nullable=False),
        sa.Column("missing_dimensions", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("max_follow_ups", sa.Integer(), nullable=False),
        sa.Column("source_reference_candidates", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "verification_target_id"),
    )
    op.create_index(
        "ix_verification_target_scope",
        "verification_targets",
        ["company_id", "applicant_id", "invitation_id", "criterion_id"],
    )

    op.create_table(
        "candidate_verification_maps",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_verification_map_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_version", sa.Integer(), nullable=False),
        sa.Column("material_version", sa.String(100), nullable=False),
        sa.Column("retrieval_version", sa.String(100), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("embedding_version", sa.String(100), nullable=False),
        sa.Column("generation_version", sa.String(100), nullable=False),
        sa.Column("ordered_target_ids", sa.JSON(), nullable=False),
        sa.Column("time_budget_seconds", sa.Integer(), nullable=False),
        sa.Column("readiness_state", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "candidate_verification_map_id"),
        sa.UniqueConstraint(
            "company_id",
            "invitation_id",
            "competency_model_version_id",
            "material_version",
            name="uq_candidate_verification_map_version",
        ),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: removes rebuildable retrieval and verification projections.
    op.drop_table("candidate_verification_maps")
    op.drop_index("ix_verification_target_scope", table_name="verification_targets")
    op.drop_table("verification_targets")
    op.drop_table("claim_conflicts")
    op.drop_index("ix_candidate_claim_scope", table_name="candidate_claims")
    op.drop_table("candidate_claims")
    op.drop_index("ix_retrieval_source", table_name="retrieval_documents")
    op.drop_index("ix_retrieval_scope", table_name="retrieval_documents")
    op.drop_table("retrieval_documents")
