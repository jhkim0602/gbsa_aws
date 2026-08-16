"""Add answer-driven verification progress and question rationale."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c_002_verification_progress"
down_revision: str | None = "a_003_position_owned_recruiting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_source_references",
        sa.Column(
            "excerpt",
            sa.String(2000),
            nullable=False,
            server_default="",
        ),
    )
    op.create_table(
        "verification_progress",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("verification_progress_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("verification_target_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("follow_up_count", sa.Integer(), nullable=False),
        sa.Column("final_answer_turn_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "verification_progress_id"),
        sa.UniqueConstraint(
            "company_id",
            "interview_session_id",
            "verification_target_id",
            name="uq_verification_progress_target",
        ),
    )
    op.create_index(
        "ix_verification_progress_session",
        "verification_progress",
        ["company_id", "interview_session_id"],
    )

    op.create_table(
        "question_rationales",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("question_rationale_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("question_turn_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("verification_target_id", sa.Uuid(), nullable=False),
        sa.Column("verification_target_type", sa.String(40), nullable=False),
        sa.Column("objective", sa.String(4000), nullable=False),
        sa.Column("question_type", sa.String(40), nullable=False),
        sa.Column("retrieval_version", sa.String(100), nullable=False),
        sa.Column("generation_version", sa.String(100), nullable=False),
        sa.Column("policy_result", sa.String(100), nullable=False),
        sa.Column("source_reference_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "question_rationale_id"),
        sa.UniqueConstraint(
            "company_id",
            "question_turn_id",
            name="uq_question_rationale_turn",
        ),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: removes rebuildable progress and question rationale projections.
    op.drop_table("question_rationales")
    op.drop_index("ix_verification_progress_session", table_name="verification_progress")
    op.drop_table("verification_progress")
    op.drop_column("question_source_references", "excerpt")
