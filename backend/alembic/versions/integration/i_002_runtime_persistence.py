"""Add durable shared runtime state after the four-lane merge."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_002_runtime_persistence"
down_revision: str | None = "merge_001_lane_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("outbox_event_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(200), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("trace_id", sa.String(200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publish_status", sa.String(30), nullable=False),
        sa.Column("publish_attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("outbox_event_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency_key"),
    )
    op.create_index("ix_outbox_events_company_id", "outbox_events", ["company_id"])
    op.create_table(
        "processed_messages",
        sa.Column("consumer_name", sa.String(200), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("first_processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_digest", sa.String(128), nullable=False),
        sa.PrimaryKeyConstraint("consumer_name", "event_id", "event_version"),
    )
    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(200), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("audit_event_id"),
    )
    op.create_index("ix_audit_events_company_id", "audit_events", ["company_id"])
    op.create_table(
        "applicant_access_tokens",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_applicant_access_tokens_company_id",
        "applicant_access_tokens",
        ["company_id"],
    )
    op.create_table(
        "applicant_access_sessions",
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_hash"),
        sa.UniqueConstraint("session_id", name="uq_applicant_access_sessions_session_id"),
    )
    op.create_index(
        "ix_applicant_access_sessions_company_id",
        "applicant_access_sessions",
        ["company_id"],
    )
    op.create_table(
        "submission_upload_intents",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("url", sa.String(4096), nullable=False),
        sa.Column("required_headers", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "upload_id"),
    )
    op.create_index(
        "ix_submission_upload_intents_applicant_id",
        "submission_upload_intents",
        ["applicant_id"],
    )
    op.create_table(
        "command_idempotency",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "operation", "idempotency_key"),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: downgrade removes only shared runtime state introduced here.
    op.drop_table("command_idempotency")
    op.drop_index(
        "ix_submission_upload_intents_applicant_id",
        table_name="submission_upload_intents",
    )
    op.drop_table("submission_upload_intents")
    op.drop_index(
        "ix_applicant_access_sessions_company_id",
        table_name="applicant_access_sessions",
    )
    op.drop_table("applicant_access_sessions")
    op.drop_index(
        "ix_applicant_access_tokens_company_id",
        table_name="applicant_access_tokens",
    )
    op.drop_table("applicant_access_tokens")
    op.drop_index("ix_audit_events_company_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("processed_messages")
    op.drop_index("ix_outbox_events_company_id", table_name="outbox_events")
    op.drop_table("outbox_events")
