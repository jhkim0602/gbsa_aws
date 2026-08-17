"""Index the tenant-scoped child lookups that previously scanned a whole company.

Every child read filters on ``(company_id, <parent_id>)`` but the primary key is
``(company_id, <own_id>)``, so the planner could only narrow by ``company_id`` and
discarded the rest as a filter. Tables whose UNIQUE constraint already leads with
``(company_id, <parent_id>)`` are deliberately absent -- that constraint's index
already serves the lookup. The outbox poller had no usable index at all.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "m_004_hot_path_indexes"
down_revision: str = "merge_002_criterion_grounded_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHILD_LOOKUPS: tuple[tuple[str, str, str], ...] = (
    ("ix_report_items_report", "report_items", "report_id"),
    ("ix_evidence_report_item", "evidence", "report_item_id"),
    ("ix_human_reviews_report", "human_reviews", "report_id"),
    ("ix_reports_invitation", "reports", "invitation_id"),
    ("ix_transcript_segments_session", "transcript_segments", "interview_session_id"),
    ("ix_recording_assets_session", "recording_assets", "interview_session_id"),
    ("ix_session_events_session", "session_events", "interview_session_id"),
    ("ix_question_rationales_session", "question_rationales", "interview_session_id"),
    (
        "ix_question_source_references_session",
        "question_source_references",
        "interview_session_id",
    ),
    ("ix_equipment_checks_invitation", "equipment_checks", "invitation_id"),
    ("ix_submission_chunks_submission", "submission_chunks", "submission_id"),
    ("ix_submission_chunks_analysis", "submission_chunks", "analysis_id"),
    ("ix_git_repository_analyses_submission", "git_repository_analyses", "submission_id"),
    ("ix_candidate_code_units_commit", "candidate_code_units", "git_commit_analysis_id"),
    ("ix_claim_conflicts_invitation", "claim_conflicts", "invitation_id"),
    ("ix_invitations_position", "invitations", "position_id"),
    ("ix_invitations_criterion_version", "invitations", "competency_model_version_id"),
    ("ix_consent_records_invitation", "consent_records", "invitation_id"),
    ("ix_deletion_manifests_request", "deletion_manifests", "deletion_request_id"),
    ("ix_deletion_targets_manifest", "deletion_targets", "manifest_id"),
)


def upgrade() -> None:
    """Add the missing ``(company_id, <parent_id>)`` and outbox poller indexes."""
    for name, table, column in CHILD_LOOKUPS:
        op.create_index(name, table, ["company_id", column])
    op.create_index(
        "ix_outbox_events_pending",
        "outbox_events",
        ["publish_status", "occurred_at", "outbox_event_id"],
    )


def downgrade() -> None:
    """Drop the indexes added by this revision."""
    op.drop_index("ix_outbox_events_pending", table_name="outbox_events")
    for name, table, _ in reversed(CHILD_LOOKUPS):
        op.drop_index(name, table_name=table)
