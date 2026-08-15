"""Create Lane C session, Turn, checkpoint, idempotency, and media tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c_001_interview_session"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("interview",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "equipment_checks",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_check_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("camera_status", sa.String(30), nullable=False),
        sa.Column("camera_sanitized_code", sa.String(100)),
        sa.Column("microphone_status", sa.String(30), nullable=False),
        sa.Column("microphone_sanitized_code", sa.String(100)),
        sa.Column("network_status", sa.String(30), nullable=False),
        sa.Column("network_sanitized_code", sa.String(100)),
        sa.Column("overall_status", sa.String(30), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "equipment_check_id"),
    )
    op.create_table(
        "interview_sessions",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("interview_strategy_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("session_sequence", sa.Integer(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("degraded_modes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("company_id", "interview_session_id"),
        sa.UniqueConstraint(
            "company_id",
            "invitation_id",
            name="uq_interview_sessions_invitation",
        ),
        sa.CheckConstraint("session_sequence >= 0", name="interview_session_sequence"),
        sa.CheckConstraint("row_version >= 1", name="interview_session_row_version"),
    )
    op.create_table(
        "interview_turns",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("target_criterion_id", sa.Uuid()),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("model_config_version", sa.String(100)),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "turn_id"),
        sa.UniqueConstraint(
            "company_id",
            "interview_session_id",
            "sequence",
            name="uq_interview_turns_sequence",
        ),
        sa.UniqueConstraint(
            "company_id",
            "interview_session_id",
            "idempotency_key",
            name="uq_interview_turns_idempotency",
        ),
    )
    op.create_table(
        "session_checkpoints",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("session_sequence", sa.Integer(), nullable=False),
        sa.Column("last_final_turn_id", sa.Uuid()),
        sa.Column("last_media_chunk_sequence", sa.Integer(), nullable=False),
        sa.Column("pending_turn_id", sa.Uuid()),
        sa.Column("hot_view_sync_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "checkpoint_id"),
        sa.UniqueConstraint(
            "company_id",
            "interview_session_id",
            "session_sequence",
            name="uq_session_checkpoints_sequence",
        ),
        sa.CheckConstraint(
            "last_media_chunk_sequence >= 0",
            name="checkpoint_media_sequence",
        ),
    )
    op.create_table(
        "question_source_references",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("source_reference_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("question_turn_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("ownership_confidence", sa.Float(), nullable=False),
        sa.Column("retrieval_config_version", sa.String(100), nullable=False),
        sa.Column("model_config_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "question_turn_id"],
            ["interview_turns.company_id", "interview_turns.turn_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "source_reference_id"),
        sa.UniqueConstraint(
            "company_id",
            "question_turn_id",
            "source_id",
            name="uq_question_source_references_source",
        ),
        sa.CheckConstraint(
            "ownership_confidence BETWEEN 0 AND 1",
            name="question_source_ownership_confidence",
        ),
        sa.CheckConstraint(
            "relevance_score >= 0",
            name="question_source_relevance_score",
        ),
    )
    op.create_table(
        "recording_chunks",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("recording_chunk_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(2048), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("session_start_ms", sa.Integer(), nullable=False),
        sa.Column("session_end_ms", sa.Integer(), nullable=False),
        sa.Column("upload_status", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "interview_session_id"],
            ["interview_sessions.company_id", "interview_sessions.interview_session_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "recording_chunk_id"),
        sa.UniqueConstraint(
            "company_id",
            "interview_session_id",
            "sequence",
            name="uq_recording_chunks_sequence",
        ),
        sa.UniqueConstraint(
            "company_id",
            "interview_session_id",
            "idempotency_key",
            name="uq_recording_chunks_idempotency",
        ),
        sa.CheckConstraint("byte_size > 0", name="recording_chunk_byte_size"),
        sa.CheckConstraint(
            "session_end_ms > session_start_ms",
            name="recording_chunk_time_range",
        ),
    )
    op.create_table(
        "interview_command_results",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "company_id",
            "interview_session_id",
            "operation",
            "idempotency_key",
        ),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: downgrade removes only Lane C schema from this root revision.
    op.drop_table("interview_command_results")
    op.drop_table("recording_chunks")
    op.drop_table("question_source_references")
    op.drop_table("session_checkpoints")
    op.drop_table("interview_turns")
    op.drop_table("interview_sessions")
    op.drop_table("equipment_checks")
