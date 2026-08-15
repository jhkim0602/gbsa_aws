"""Create Lane A company, hiring, invitation, consent, and retention tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a_001_company_hiring"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("company",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand_config", sa.JSON(), nullable=False),
        sa.Column("default_retention_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "default_retention_days BETWEEN 1 AND 3650",
            name="company_retention_days",
        ),
        sa.PrimaryKeyConstraint("company_id"),
    )
    op.create_table(
        "company_users",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("company_user_id", sa.Uuid(), nullable=False),
        sa.Column("identity_subject", sa.String(512), nullable=False),
        sa.Column("email_normalized", sa.String(320), nullable=False),
        sa.Column("role_code", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.PrimaryKeyConstraint("company_id", "company_user_id"),
        sa.UniqueConstraint(
            "company_id",
            "identity_subject",
            name="uq_company_users_company_identity_subject",
        ),
        sa.UniqueConstraint(
            "company_id",
            "email_normalized",
            name="uq_company_users_company_email",
        ),
    )
    op.create_table(
        "positions",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(20_000), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.PrimaryKeyConstraint("company_id", "position_id"),
        sa.CheckConstraint("row_version >= 1", name="position_row_version"),
    )
    op.create_table(
        "competency_model_versions",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("prohibited_topics", sa.JSON(), nullable=False),
        sa.Column("interview_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("persona_definition", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["company_id", "position_id"],
            ["positions.company_id", "positions.position_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "competency_model_version_id"),
        sa.UniqueConstraint(
            "company_id",
            "position_id",
            "version_number",
            name="uq_competency_versions_position_number",
        ),
        sa.CheckConstraint(
            "interview_duration_minutes BETWEEN 10 AND 120",
            name="competency_duration",
        ),
        sa.CheckConstraint("row_version >= 1", name="competency_row_version"),
    )
    op.create_table(
        "evaluation_criteria",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(4000), nullable=False),
        sa.Column("weight", sa.Numeric(10, 4), nullable=False),
        sa.Column("good_evidence", sa.JSON(), nullable=False),
        sa.Column("weak_evidence", sa.JSON(), nullable=False),
        sa.Column("abstain_guidance", sa.String(4000), nullable=False),
        sa.Column("common_questions", sa.JSON(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "competency_model_version_id"],
            [
                "competency_model_versions.company_id",
                "competency_model_versions.competency_model_version_id",
            ],
        ),
        sa.PrimaryKeyConstraint(
            "company_id",
            "competency_model_version_id",
            "criterion_id",
        ),
        sa.UniqueConstraint(
            "company_id",
            "competency_model_version_id",
            "code",
            name="uq_evaluation_criteria_version_code",
        ),
        sa.CheckConstraint("weight >= 0", name="criterion_weight"),
    )
    op.create_table(
        "campaigns",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("candidate_instructions", sa.String(10_000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["company_id", "position_id"],
            ["positions.company_id", "positions.position_id"],
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "competency_model_version_id"],
            [
                "competency_model_versions.company_id",
                "competency_model_versions.competency_model_version_id",
            ],
        ),
        sa.PrimaryKeyConstraint("company_id", "campaign_id"),
        sa.CheckConstraint("row_version >= 1", name="campaign_row_version"),
    )
    op.create_table(
        "invitations",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_email_normalized", sa.String(320), nullable=False),
        sa.Column("applicant_display_name", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("identity_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_state_actor_type", sa.String(30), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "campaign_id"],
            ["campaigns.company_id", "campaigns.campaign_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "invitation_id"),
        sa.UniqueConstraint(
            "company_id",
            "applicant_id",
            name="uq_invitations_company_applicant",
        ),
        sa.UniqueConstraint(
            "company_id",
            "token_hash",
            name="uq_invitations_company_token_hash",
        ),
        sa.CheckConstraint("row_version >= 1", name="invitation_row_version"),
    )
    op.create_table(
        "invitation_state_history",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_state_change_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(40), nullable=False),
        sa.Column("to_status", sa.String(40), nullable=False),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "invitation_id"],
            ["invitations.company_id", "invitations.invitation_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "invitation_state_change_id"),
        sa.UniqueConstraint(
            "company_id",
            "invitation_id",
            "aggregate_version",
            name="uq_invitation_history_aggregate_version",
        ),
    )
    op.create_table(
        "applicant_profiles",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("verification_method", sa.String(50), nullable=False),
        sa.Column("technology_tags", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "invitation_id"],
            ["invitations.company_id", "invitations.invitation_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "applicant_id"),
        sa.UniqueConstraint(
            "company_id",
            "invitation_id",
            name="uq_applicant_profiles_company_invitation",
        ),
    )
    op.create_table(
        "consent_records",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("consent_record_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("purposes", sa.JSON(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id", "invitation_id"],
            ["invitations.company_id", "invitations.invitation_id"],
        ),
        sa.PrimaryKeyConstraint("company_id", "consent_record_id"),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="consent_retention_days",
        ),
    )
    op.create_table(
        "retention_policies",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("retention_policy_id", sa.Uuid(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.PrimaryKeyConstraint("company_id", "retention_policy_id"),
        sa.UniqueConstraint(
            "company_id",
            "policy_version",
            name="uq_retention_policies_company_version",
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="retention_policy_days",
        ),
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: downgrade removes only schema introduced by this root revision.
    op.drop_table("retention_policies")
    op.drop_table("consent_records")
    op.drop_table("applicant_profiles")
    op.drop_table("invitation_state_history")
    op.drop_table("invitations")
    op.drop_table("campaigns")
    op.drop_table("evaluation_criteria")
    op.drop_table("competency_model_versions")
    op.drop_table("positions")
    op.drop_table("company_users")
    op.drop_table("companies")
