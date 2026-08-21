"""Freeze the arithmetic each report was scored with, and store the score it produced.

``m_013`` let a company weight its criteria and axes. This is the other half: the report has to
record the weights it *used*, not point at the version they came from.

Without that, adjusting a weight next month silently rewrites every past score. A reviewer who
advanced a candidate at 74 would open the same report and find 71, with nothing on the screen to
say why, and the immutability the report already claims (``kind = ai_original``, and
``save_report`` refusing to overwrite) would be true of the prose and false of the number.

Four columns:

``reports.overall_score``
    The weighted score, denormalised so the applicant list can sort on it in one query.
    Recomputing it per row would make that list load every report's items to order a column.
    Nullable, because a report where nothing could be scored has no score -- never zero, which
    would read as "every answer was wrong".

``reports.scoring_inputs``
    Weights, numerator, divisor and the criteria excluded for lack of evidence. The calculator
    renders this, so what is stored is the arithmetic the reviewer actually saw.

``report_items.criterion_weight`` / ``report_items.axis_weights``
    The per-item snapshot the two aggregates read. Defaults of ``1.0`` and ``{}`` mean "not
    weighted", which the domain reads as equal weight -- reproducing the plain mean that reports
    written before this migration were genuinely scored with. **No backfill:** computing weights
    for those reports would restate history rather than record it.

The divisor is the point of ``scoring_inputs`` and is not the same thing as the configured
total. Criterion weights must total 100 (``CompetencyModelVersion.criterion_weights_total_100``),
but a criterion the interview never reached drops out at scoring time, so the weights that
actually counted can total 0.75. That is why the number is stored rather than assumed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m_014_report_scoring"
down_revision: str = "m_013_axis_weights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.add_column(sa.Column("overall_score", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "scoring_inputs",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )
    with op.batch_alter_table("report_items") as batch:
        batch.add_column(
            sa.Column(
                "criterion_weight",
                sa.Float(),
                nullable=False,
                server_default="1.0",
            )
        )
        batch.add_column(
            sa.Column(
                "axis_weights",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    # DATA_MIGRATION_NOTE: this discards the frozen arithmetic. Scores fall back to the plain
    # mean that equal weights produce, so every report stays readable -- but a score a reviewer
    # recorded a decision against will read differently afterwards, and the formula behind it is
    # gone rather than recoverable.
    with op.batch_alter_table("report_items") as batch:
        batch.drop_column("axis_weights")
        batch.drop_column("criterion_weight")
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("scoring_inputs")
        batch.drop_column("overall_score")
