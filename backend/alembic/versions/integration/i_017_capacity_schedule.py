"""Persist scheduled interview capacity reservations and reconciled ECS actions."""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "m_017_capacity_schedule"
down_revision: tuple[str, str] = (
    "m_016_assistant_search_gin",
    "m_016_interview_stage",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capacity_reservations",
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expected_concurrency", sa.Integer(), nullable=True),
        sa.Column("interview_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interview_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("position_id"),
    )
    op.create_index(
        "ix_capacity_reservations_company_id",
        "capacity_reservations",
        ["company_id"],
    )
    op.create_index(
        "ix_capacity_reservations_active_window",
        "capacity_reservations",
        ["status", "interview_at"],
    )
    # Existing scheduled positions become planner input immediately after deployment; the
    # five-minute reconciliation rule creates their AWS actions without requiring a user edit.
    op.execute(
        sa.text(
            """
            INSERT INTO capacity_reservations (
                position_id,
                company_id,
                source_version,
                status,
                expected_concurrency,
                interview_at,
                interview_duration_minutes,
                updated_at
            )
            SELECT
                position_id,
                company_id,
                row_version,
                CASE
                    WHEN status = 'active'
                         AND interview_capacity IS NOT NULL
                         AND interview_at IS NOT NULL
                    THEN 'active'
                    ELSE 'cancelled'
                END,
                interview_capacity,
                interview_at,
                30,
                CURRENT_TIMESTAMP
            FROM positions
            WHERE interview_capacity IS NOT NULL OR interview_at IS NOT NULL
            """
        )
    )
    op.create_table(
        "capacity_scheduled_actions",
        sa.Column("action_name", sa.String(length=256), nullable=False),
        sa.Column("service_role", sa.String(length=30), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("min_capacity", sa.Integer(), nullable=False),
        sa.Column("max_capacity", sa.Integer(), nullable=False),
        sa.Column("expected_load", sa.Integer(), nullable=False),
        sa.Column("plan_hash", sa.String(length=64), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("action_name"),
    )
    op.create_index(
        "ix_capacity_scheduled_actions_service_time",
        "capacity_scheduled_actions",
        ["service_role", "effective_at"],
    )
    op.create_table(
        "capacity_plan_state",
        sa.Column("plan_key", sa.String(length=30), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("plan_key"),
    )
    plan_state = sa.table(
        "capacity_plan_state",
        sa.column("plan_key", sa.String()),
        sa.column("plan_version", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        plan_state,
        [
            {
                "plan_key": "global",
                "plan_version": 0,
                "updated_at": datetime(1970, 1, 1, tzinfo=UTC),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("capacity_plan_state")
    op.drop_index(
        "ix_capacity_scheduled_actions_service_time",
        table_name="capacity_scheduled_actions",
    )
    op.drop_table("capacity_scheduled_actions")
    op.drop_index(
        "ix_capacity_reservations_active_window",
        table_name="capacity_reservations",
    )
    op.drop_index(
        "ix_capacity_reservations_company_id",
        table_name="capacity_reservations",
    )
    op.drop_table("capacity_reservations")
