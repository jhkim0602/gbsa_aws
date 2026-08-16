"""Add immutable recruiter requirements and criterion verification guides."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a_004_criterion_grounding"
down_revision: str | None = "a_003_position_owned_recruiting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_criteria") as batch:
        batch.add_column(sa.Column("verification_guide", sa.JSON(), nullable=True))
    evaluation_criteria = sa.table(
        "evaluation_criteria",
        sa.column("verification_guide", sa.JSON()),
    )
    op.get_bind().execute(
        sa.update(evaluation_criteria).values(
            verification_guide={
                "observable_dimensions": ["구체적인 상황", "본인 행동", "결과"],
                "strong_answer_signals": ["본인 행동과 판단 근거가 구체적임"],
                "weak_answer_signals": ["팀 활동 또는 결과만 언급함"],
                "follow_up_directions": ["본인이 직접 수행한 행동"],
                "max_follow_ups": 1,
                "time_budget_seconds": 300,
            }
        )
    )
    with op.batch_alter_table("evaluation_criteria") as batch:
        batch.alter_column(
            "verification_guide",
            existing_type=sa.JSON(),
            nullable=False,
        )

    op.create_table(
        "job_requirements",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("competency_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("job_requirement_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_type", sa.String(20), nullable=False),
        sa.Column("statement", sa.String(4000), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("criterion_code", sa.String(40), nullable=False),
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
            "job_requirement_id",
        ),
        sa.CheckConstraint(
            "requirement_type IN ('required', 'preferred')",
            name="job_requirement_type",
        ),
        sa.CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="job_requirement_priority",
        ),
    )
    op.create_index(
        "ix_job_requirements_version",
        "job_requirements",
        ["company_id", "competency_model_version_id"],
    )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: removes criterion grounding metadata added by this feature.
    op.drop_index("ix_job_requirements_version", table_name="job_requirements")
    op.drop_table("job_requirements")
    with op.batch_alter_table("evaluation_criteria") as batch:
        batch.drop_column("verification_guide")
