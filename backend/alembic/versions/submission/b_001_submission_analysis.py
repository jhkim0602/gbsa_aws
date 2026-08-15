"""Create Lane B submission, analysis, source, Git, and strategy tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b_001_submission_analysis"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("submission",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_uri", sa.String(4096), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("byte_size", sa.Integer()),
        sa.Column("media_type", sa.String(200)),
        sa.Column("candidate_identity_inputs", sa.JSON()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("impact_summary", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "submission_id"),
        sa.CheckConstraint("row_version >= 1", name="submission_row_version"),
    )
    op.create_table(
        "submission_analyses",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=False),
        sa.Column("extractor_version", sa.String(100), nullable=False),
        sa.Column("chunk_config_version", sa.String(100), nullable=False),
        sa.Column("claims", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("verification_points", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("impact_summary", sa.String(2000)),
        sa.ForeignKeyConstraint(
            ["company_id", "submission_id"],
            ["submissions.company_id", "submissions.submission_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "analysis_id"),
        sa.UniqueConstraint(
            "company_id",
            "submission_id",
            "analysis_version",
            name="uq_submission_analyses_version",
        ),
    )
    op.create_table(
        "submission_chunks",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("source_location", sa.JSON(), nullable=False),
        sa.Column("text_object_key", sa.String(2048), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("chunk_hash", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("embedding_version", sa.String(100), nullable=False),
        sa.Column("index_document_id", sa.String(512), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["company_id", "submission_id"],
            ["submissions.company_id", "submissions.submission_id"],
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "analysis_id"],
            ["submission_analyses.company_id", "submission_analyses.analysis_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "chunk_id"),
        sa.UniqueConstraint(
            "company_id",
            "index_document_id",
            name="uq_submission_chunks_index_document",
        ),
    )
    op.create_table(
        "git_repository_analyses",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("repository_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("repository_url", sa.String(4096), nullable=False),
        sa.Column("default_branch", sa.String(500), nullable=False),
        sa.Column("pinned_head_sha", sa.String(40), nullable=False),
        sa.Column("candidate_identity_inputs", sa.JSON(), nullable=False),
        sa.Column("limits_applied", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "submission_id"],
            ["submissions.company_id", "submissions.submission_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "repository_analysis_id"),
    )
    op.create_table(
        "git_commit_analyses",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("git_commit_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("repository_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("parent_sha", sa.String(40), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("author_match_inputs", sa.JSON(), nullable=False),
        sa.Column("change_summary_object_key", sa.String(2048), nullable=False),
        sa.Column("ownership_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("ownership_class", sa.String(30), nullable=False),
        sa.Column("ownership_explanation", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "repository_analysis_id"],
            [
                "git_repository_analyses.company_id",
                "git_repository_analyses.repository_analysis_id",
            ],
        ),
        sa.PrimaryKeyConstraint("company_id", "git_commit_analysis_id"),
        sa.UniqueConstraint(
            "company_id",
            "repository_analysis_id",
            "commit_sha",
            name="uq_git_commit_analyses_commit",
        ),
        sa.CheckConstraint(
            "ownership_confidence BETWEEN 0 AND 1",
            name="git_commit_ownership_confidence",
        ),
    )
    op.create_table(
        "candidate_code_units",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("code_unit_id", sa.Uuid(), nullable=False),
        sa.Column("git_commit_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(1000), nullable=False),
        sa.Column("language", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(500), nullable=False),
        sa.Column("original_line_range", sa.JSON(), nullable=False),
        sa.Column("current_line_range", sa.JSON(), nullable=False),
        sa.Column("authored_snapshot_key", sa.String(2048), nullable=False),
        sa.Column("current_snapshot_key", sa.String(2048), nullable=False),
        sa.Column("candidate_owned_regions", sa.JSON(), nullable=False),
        sa.Column("related_test_ids", sa.JSON(), nullable=False),
        sa.Column("dependency_ids", sa.JSON(), nullable=False),
        sa.Column("index_document_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "git_commit_analysis_id"],
            [
                "git_commit_analyses.company_id",
                "git_commit_analyses.git_commit_analysis_id",
            ],
        ),
        sa.PrimaryKeyConstraint("company_id", "code_unit_id"),
    )
    op.create_table(
        "interview_strategies",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("interview_strategy_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("common_topics", sa.JSON(), nullable=False),
        sa.Column("verification_points", sa.JSON(), nullable=False),
        sa.Column("follow_up_directions", sa.JSON(), nullable=False),
        sa.Column("time_budget", sa.JSON(), nullable=False),
        sa.Column("required_evidence_plan", sa.JSON(), nullable=False),
        sa.Column("source_reference_candidates", sa.JSON(), nullable=False),
        sa.Column("model_config_version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "interview_strategy_id"),
        sa.UniqueConstraint(
            "company_id",
            "invitation_id",
            "strategy_version",
            name="uq_interview_strategies_invitation_version",
        ),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: downgrade removes only Lane B schema from this root revision.
    op.drop_table("interview_strategies")
    op.drop_table("candidate_code_units")
    op.drop_table("git_commit_analyses")
    op.drop_table("git_repository_analyses")
    op.drop_table("submission_chunks")
    op.drop_table("submission_analyses")
    op.drop_table("submissions")
