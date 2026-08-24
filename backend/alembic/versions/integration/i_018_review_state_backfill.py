"""Mark invitations with an existing final decision as reviewed."""

from collections.abc import Sequence
from uuid import UUID, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "m_018_review_state_backfill"
down_revision: str = "m_017_capacity_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_NAMESPACE = UUID("5ab3c9c3-0b0d-4a66-b07c-3fa831f42f41")
_BACKFILL_ACTOR = "review_backfill"
_REPAIRABLE_STATUSES = (
    "invited",
    "identity_verified",
    "consented",
    "materials_submitted",
    "analyzing",
    "ready",
    "interviewing",
    "interrupted",
    "completed",
)


def _change_id(company_id: object, invitation_id: object) -> UUID:
    return uuid5(_BACKFILL_NAMESPACE, f"{company_id}:{invitation_id}")


def upgrade() -> None:
    bind = op.get_bind()
    candidates = tuple(
        bind.execute(
            sa.text(
                """
                SELECT
                    invitations.company_id,
                    invitations.invitation_id,
                    invitations.status,
                    invitations.row_version,
                    MAX(human_reviews.created_at) AS decided_at
                FROM invitations
                JOIN human_reviews
                  ON human_reviews.company_id = invitations.company_id
                 AND human_reviews.target_id = invitations.invitation_id
                 AND human_reviews.review_type = 'final_decision'
                WHERE invitations.status IN :repairable_statuses
                GROUP BY
                    invitations.company_id,
                    invitations.invitation_id,
                    invitations.status,
                    invitations.row_version
                """
            ).bindparams(sa.bindparam("repairable_statuses", expanding=True)),
            {"repairable_statuses": _REPAIRABLE_STATUSES},
        ).mappings()
    )

    for candidate in candidates:
        next_version = int(candidate["row_version"]) + 1
        bind.execute(
            sa.text(
                """
                UPDATE invitations
                SET status = 'reviewed',
                    last_state_actor_type = :actor_type,
                    row_version = :next_version
                WHERE company_id = :company_id
                  AND invitation_id = :invitation_id
                  AND status = :from_status
                  AND row_version = :previous_version
                """
            ),
            {
                "actor_type": _BACKFILL_ACTOR,
                "next_version": next_version,
                "company_id": candidate["company_id"],
                "invitation_id": candidate["invitation_id"],
                "from_status": candidate["status"],
                "previous_version": candidate["row_version"],
            },
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO invitation_state_history (
                    company_id,
                    invitation_state_change_id,
                    invitation_id,
                    from_status,
                    to_status,
                    actor_type,
                    occurred_at,
                    aggregate_version
                ) VALUES (
                    :company_id,
                    :change_id,
                    :invitation_id,
                    :from_status,
                    'reviewed',
                    :actor_type,
                    :occurred_at,
                    :aggregate_version
                )
                """
            ),
            {
                "company_id": candidate["company_id"],
                "change_id": _change_id(candidate["company_id"], candidate["invitation_id"]),
                "invitation_id": candidate["invitation_id"],
                "from_status": candidate["status"],
                "actor_type": _BACKFILL_ACTOR,
                "occurred_at": candidate["decided_at"],
                "aggregate_version": next_version,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    repaired = tuple(
        bind.execute(
            sa.text(
                """
                SELECT
                    company_id,
                    invitation_state_change_id,
                    invitation_id,
                    from_status,
                    aggregate_version
                FROM invitation_state_history
                WHERE actor_type = :actor_type
                  AND to_status = 'reviewed'
                """
            ),
            {"actor_type": _BACKFILL_ACTOR},
        ).mappings()
    )
    for change in repaired:
        # Reverse only an untouched repair. A later real transition must win over a downgrade.
        bind.execute(
            sa.text(
                """
                UPDATE invitations
                SET status = :from_status,
                    last_state_actor_type = 'system',
                    row_version = row_version - 1
                WHERE company_id = :company_id
                  AND invitation_id = :invitation_id
                  AND status = 'reviewed'
                  AND row_version = :aggregate_version
                """
            ),
            change,
        )
        bind.execute(
            sa.text(
                """
                DELETE FROM invitation_state_history
                WHERE company_id = :company_id
                  AND invitation_state_change_id = :invitation_state_change_id
                """
            ),
            change,
        )
