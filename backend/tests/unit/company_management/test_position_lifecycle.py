from datetime import UTC, date, datetime
from uuid import UUID

from interview_evidence.company_management.domain.company import (
    Position,
    PositionStatus,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000201")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000202")
USER_ID = UUID("00000000-0000-7000-8000-000000000203")


def _position(
    *,
    status: PositionStatus = PositionStatus.ACTIVE,
    start: date | None = None,
    end: date | None = None,
) -> Position:
    return Position(
        position_id=POSITION_ID,
        company_id=COMPANY_ID,
        title="백엔드 엔지니어",
        description="서비스를 개발합니다.",
        recruitment_start_at=start,
        recruitment_end_at=end,
        created_by=USER_ID,
        status=status,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


def test_recruitment_end_date_is_inclusive_and_archived_afterward() -> None:
    position = _position(
        start=date(2026, 8, 1),
        end=date(2026, 8, 21),
    )

    assert position.accepts_new_applications_on(date(2026, 8, 21))
    assert not position.is_archived_on(date(2026, 8, 21))
    assert not position.accepts_new_applications_on(date(2026, 8, 22))
    assert position.is_archived_on(date(2026, 8, 22))


def test_closed_or_not_yet_started_positions_do_not_accept_new_applications() -> None:
    closed = _position(status=PositionStatus.CLOSED)
    future = _position(start=date(2026, 8, 22))

    assert not closed.accepts_new_applications_on(date(2026, 8, 21))
    assert closed.is_archived_on(date(2026, 8, 21))
    assert not future.accepts_new_applications_on(date(2026, 8, 21))
    assert not future.is_archived_on(date(2026, 8, 21))
