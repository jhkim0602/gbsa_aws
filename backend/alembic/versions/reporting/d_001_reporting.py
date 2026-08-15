"""Create Lane D transcript, report, review, and deletion tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d_001_reporting"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("reporting",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcript_segments",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_segment_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("speaker", sa.String(30), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("session_start_ms", sa.Integer(), nullable=False),
        sa.Column("session_end_ms", sa.Integer(), nullable=False),
        sa.Column("source_audio_key", sa.String(2048), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("corrected_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "transcript_segment_id"),
        sa.UniqueConstraint(
            "company_id",
            "turn_id",
            "version",
            name="uq_transcript_segment_version",
        ),
        sa.CheckConstraint(
            "session_end_ms > session_start_ms",
            name="transcript_time_range",
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="transcript_confidence",
        ),
    )
    op.create_table(
        "recording_assets",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("recording_asset_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("asset_type", sa.String(30), nullable=False),
        sa.Column("object_key", sa.String(2048), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("missing_ranges", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "recording_asset_id"),
        sa.CheckConstraint("duration_ms > 0", name="recording_asset_duration"),
    )
    op.create_table(
        "session_events",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("session_event_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("session_start_ms", sa.Integer(), nullable=False),
        sa.Column("session_end_ms", sa.Integer(), nullable=False),
        sa.Column("technical_failure", sa.Boolean(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "session_event_id"),
        sa.CheckConstraint(
            "session_end_ms > session_start_ms",
            name="session_event_time_range",
        ),
    )
    op.create_table(
        "reports",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("config_version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "report_id"),
        sa.UniqueConstraint(
            "company_id",
            "interview_session_id",
            "version",
            name="uq_report_session_version",
        ),
    )
    op.create_table(
        "report_items",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("report_item_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_state", sa.String(40), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("sufficiency", sa.String(30), nullable=False),
        sa.Column("uncertainty", sa.Text(), nullable=False),
        sa.Column("follow_up_question", sa.Text()),
        sa.ForeignKeyConstraint(
            ["company_id", "report_id"],
            ["reports.company_id", "reports.report_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "report_item_id"),
    )
    op.create_table(
        "evidence",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("report_item_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("answer_turn_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_segment_id", sa.Uuid(), nullable=False),
        sa.Column("video_start_ms", sa.Integer(), nullable=False),
        sa.Column("video_end_ms", sa.Integer(), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("sufficiency", sa.String(30), nullable=False),
        sa.Column("generation_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "report_item_id"],
            ["report_items.company_id", "report_items.report_item_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "evidence_id"),
        sa.CheckConstraint(
            "video_end_ms > video_start_ms",
            name="evidence_video_range",
        ),
    )
    op.create_table(
        "human_reviews",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("human_review_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("company_user_id", sa.Uuid(), nullable=False),
        sa.Column("review_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "report_id"],
            ["reports.company_id", "reports.report_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "human_review_id"),
    )
    op.create_table(
        "deletion_requests",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("deletion_request_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(30), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requester_type", sa.String(30), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "deletion_request_id"),
    )
    op.create_table(
        "deletion_manifests",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), nullable=False),
        sa.Column("deletion_request_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "deletion_request_id"],
            ["deletion_requests.company_id", "deletion_requests.deletion_request_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "manifest_id"),
    )
    op.create_table(
        "deletion_targets",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), nullable=False),
        sa.Column("owner_lane", sa.String(1), nullable=False),
        sa.Column("store", sa.String(30), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["company_id", "manifest_id"],
            ["deletion_manifests.company_id", "deletion_manifests.manifest_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "target_id"),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: downgrade removes only Lane D-owned derived reporting data.
    op.drop_table("deletion_targets")
    op.drop_table("deletion_manifests")
    op.drop_table("deletion_requests")
    op.drop_table("human_reviews")
    op.drop_table("evidence")
    op.drop_table("report_items")
    op.drop_table("reports")
    op.drop_table("session_events")
    op.drop_table("recording_assets")
    op.drop_table("transcript_segments")
