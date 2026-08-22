from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.company_management.application.company_service import CompanyService
from interview_evidence.company_management.domain.company import Position
from interview_evidence.shared.idempotency import InMemoryResourceIdempotencyStore
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.security.principals import CompanyPrincipal
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")


class PositionRepositoryStub:
    def __init__(self) -> None:
        self.positions: dict[UUID, Position] = {}

    def save_position(self, context: TenantContext, position: Position) -> Position:
        context.assert_company(position.company_id)
        self.positions[position.position_id] = position
        return position

    def get_position(self, context: TenantContext, position_id: UUID) -> Position:
        position = self.positions[position_id]
        context.assert_company(position.company_id)
        return position


def test_position_save_emits_a_fixed_duration_capacity_event_through_the_outbox() -> None:
    outbox = InMemoryOutbox()
    service = CompanyService(
        PositionRepositoryStub(),  # type: ignore[arg-type] - focused application port stub
        FrozenClock(NOW),
        InMemoryResourceIdempotencyStore(),
        outbox,
    )
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="position-capacity-event",
    )
    principal = CompanyPrincipal(
        company_id=COMPANY_ID,
        company_user_id=COMPANY_USER_ID,
        identity_subject="oidc|company-user",
    )
    interview_at = datetime(2026, 9, 15, 5, 0, tzinfo=UTC)

    position = service.create_position(
        context,
        principal,
        title="백엔드 개발자",
        description="예약 용량 이벤트를 검증합니다.",
        interview_capacity=100,
        interview_at=interview_at,
        idempotency_key="position-capacity-create",
    )

    event = outbox.pending()[0]
    assert event.event_type == "position.capacity_changed"
    assert event.aggregate_id == position.position_id
    assert event.aggregate_version == 1
    assert event.payload == {
        "position_id": str(position.position_id),
        "position_status": "draft",
        "interview_at": interview_at.isoformat(),
        "expected_concurrency": 100,
        "interview_duration_minutes": 30,
    }
