"""What a refused invitation email must not cost.

The send is synchronous and inside the POST, and the HTTP transaction middleware rolls the
request's session back on any status of 500 or above. An exception escaping the send loop
therefore discarded the whole batch -- including the invitations whose mail had already
left, leaving an applicant holding a link whose row no longer existed.

SES makes that the ordinary case rather than a rare one. In sandbox it refuses every
recipient nobody has verified, so on the first deployed run one unconfirmed address would
have taken down every invitation issued beside it.

The middleware is installed here on purpose: without it the assertions could only show the
status code, and the rows surviving is the half that matters.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_runtime
from interview_evidence.company_management.domain.company import Company, Position, PositionStatus
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelStatus,
    CompetencyModelVersion,
    EvaluationCriterion,
)
from interview_evidence.company_management.repositories.postgres import (
    InMemoryCompanyRepository,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import InMemoryEmailSender, RenderedEmail
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000010")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000011")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000012")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

# The address the fake SES refuses, standing in for a recipient nobody verified.
REFUSED = "unverified@example.test"
DELIVERED = "verified@example.test"


class RefusingEmailSender(InMemoryEmailSender):
    """Delivers to every address except one, the way sandbox SES does.

    Subclasses the in-memory sender rather than replacing it so a delivered message is
    still recorded and the test can prove the good address was actually sent to -- the
    failure mode being pinned is one where mail leaves and the row disappears.
    """

    def send_template(
        self,
        context: TenantContext,
        template_id: str,
        recipient_ref: UUID,
        recipient_address: str,
        template_data: object,
        rendered: RenderedEmail,
    ) -> UUID:
        if recipient_address == REFUSED:
            # The shape `AwsSesEmailSender` raises: everything botocore throws is wrapped,
            # so the route cannot inspect it and must decide on the fact of the failure.
            raise RuntimeError("email delivery unavailable")
        return super().send_template(
            context,
            template_id=template_id,
            recipient_ref=recipient_ref,
            recipient_address=recipient_address,
            template_data=template_data,  # type: ignore[arg-type]
            rendered=rendered,
        )


class RecordingTransaction:
    """Stands in for the real transaction middleware, and records what it decided.

    `Database.install_http_transaction_middleware` commits below 500 and rolls back at or
    above it. That rule is the defect's mechanism, so it is reproduced here rather than
    described: an in-memory repository has no session to roll back, and a test that only
    read the status code would keep passing if the rule were reintroduced.
    """

    def __init__(self) -> None:
        self.rolled_back = False
        self.committed = False

    def install(self, application: FastAPI) -> None:
        @application.middleware("http")
        async def transaction_request(
            request: Request,
            call_next: RequestResponseEndpoint,
        ) -> Response:
            response = await call_next(request)
            if response.status_code >= 500:
                self.rolled_back = True
            else:
                self.committed = True
            return response


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=COMPANY_USER_ID,
        request_id=uuid4(),
        trace_id="invitation-delivery-failure",
    )


def _seeded_repository() -> InMemoryCompanyRepository:
    repository = InMemoryCompanyRepository()
    context = _context()
    repository.save_company(
        context,
        Company(
            company_id=COMPANY_ID,
            name="테스트 회사",
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    repository.save_position(
        context,
        Position(
            position_id=POSITION_ID,
            company_id=COMPANY_ID,
            title="백엔드 개발자",
            description="서비스를 개발합니다.",
            created_by=COMPANY_USER_ID,
            status=PositionStatus.ACTIVE,
            created_at=NOW,
        ),
    )
    # Published, because `issue_invitations` refuses a position without a published model
    # and the failure being tested happens after that check.
    repository.save_criterion_version(
        context,
        CompetencyModelVersion(
            competency_model_version_id=VERSION_ID,
            company_id=COMPANY_ID,
            position_id=POSITION_ID,
            version_number=1,
            criteria=(
                EvaluationCriterion(
                    criterion_id=CRITERION_ID,
                    code="PROBLEM_SOLVING",
                    name="문제 해결",
                    description="대안을 비교하고 근거를 설명한다.",
                    weight=1,
                    abstain_guidance="근거가 없으면 판단을 보류한다.",
                    required=True,
                ),
            ),
            interview_duration_minutes=30,
            status=CompetencyModelStatus.PUBLISHED,
            published_at=NOW,
        ),
    )
    return repository


@pytest.mark.asyncio
async def test_a_refused_recipient_keeps_every_invitation_in_the_batch() -> None:
    repository = _seeded_repository()
    email_sender = RefusingEmailSender()
    audit = InMemoryAuditAppender()
    runtime = create_lane_a_runtime(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|company-user",
                )
            }
        ),
        repository=repository,
        audit=audit,
        clock=FrozenClock(NOW),
        email_sender=email_sender,
        applicant_access_base_url="https://applicant.example/access",
    )
    transaction = RecordingTransaction()
    transaction.install(runtime.app)

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            f"/v1/positions/{POSITION_ID}/invitations",
            headers={
                "Authorization": "Bearer company-token",
                "Idempotency-Key": "refused-recipient-batch",
            },
            json={
                "applicants": [
                    {"email": DELIVERED, "display_name": "받는사람"},
                    {"email": REFUSED, "display_name": "거부된사람"},
                ],
                "expires_at": (NOW + timedelta(days=7)).isoformat(),
            },
        )

    # Not a 500, which is the whole point: at 500 the middleware discards the batch.
    assert response.status_code == 202
    assert transaction.rolled_back is False
    assert transaction.committed is True

    # Both invitations exist. The refused one is kept deliberately -- its token is valid,
    # so the recruiter can retry, whereas a dropped invitation is unrecoverable.
    body = response.json()
    assert len(body["invitations"]) == 2
    stored = repository.list_invitations(_context(), POSITION_ID)
    assert {invitation.applicant_email for invitation in stored} == {DELIVERED, REFUSED}

    # And the reviewer is told. `rejected_count` was hardcoded to 0, so a batch that half
    # delivered reported as a complete success and nobody knew to resend.
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 1
    assert len(body["access_links"]) == 1
    assert body["access_links"][0]["applicant_email"] == REFUSED
    assert body["access_links"][0]["access_url"].startswith("https://applicant.example/access/")

    # The good address really was sent to, so this is the mail-left-but-row-vanished case
    # and not a batch that failed before sending anything.
    assert len(email_sender.messages) == 1

    # Findable afterwards, without recording the address that was refused.
    failures = [event for event in audit.events if event.action == "invitation.email_failed"]
    assert len(failures) == 1
    assert failures[0].result == "failure"
    assert REFUSED not in str(failures[0].metadata)


@pytest.mark.asyncio
async def test_a_fully_delivered_batch_reports_no_rejections() -> None:
    """The counts have to stay honest in the ordinary case too.

    Deriving `accepted_count` from the failures makes it possible to get the arithmetic
    backwards, which would report every successful batch as rejected.
    """
    repository = _seeded_repository()
    email_sender = RefusingEmailSender()
    runtime = create_lane_a_runtime(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|company-user",
                )
            }
        ),
        repository=repository,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
        email_sender=email_sender,
        applicant_access_base_url="https://applicant.example/access",
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            f"/v1/positions/{POSITION_ID}/invitations",
            headers={
                "Authorization": "Bearer company-token",
                "Idempotency-Key": "fully-delivered-batch",
            },
            json={
                "applicants": [
                    {"email": DELIVERED, "display_name": "받는사람"},
                    {"email": "second@example.test", "display_name": "두번째"},
                ],
                "expires_at": (NOW + timedelta(days=7)).isoformat(),
            },
        )

    assert response.status_code == 202
    body = response.json()
    assert body["accepted_count"] == 2
    assert body["rejected_count"] == 0
    assert body["access_links"] == []
    assert len(email_sender.messages) == 2


@pytest.mark.asyncio
async def test_manual_links_create_valid_invitations_without_sending_email() -> None:
    repository = _seeded_repository()
    email_sender = RefusingEmailSender()
    audit = InMemoryAuditAppender()
    runtime = create_lane_a_runtime(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|company-user",
                )
            }
        ),
        repository=repository,
        audit=audit,
        clock=FrozenClock(NOW),
        email_sender=email_sender,
        applicant_access_base_url="https://applicant.example/access",
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            f"/v1/positions/{POSITION_ID}/invitations",
            headers={
                "Authorization": "Bearer company-token",
                "Idempotency-Key": "manual-invitation-links",
            },
            json={
                "applicants": [{"email": REFUSED, "display_name": "수동초대"}],
                "expires_at": (NOW + timedelta(days=7)).isoformat(),
                "delivery_method": "manual_link",
            },
        )

    assert response.status_code == 202
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 0
    assert len(body["invitations"]) == 1
    assert len(body["access_links"]) == 1
    assert body["access_links"][0]["applicant_email"] == REFUSED
    assert body["access_links"][0]["access_url"].startswith("https://applicant.example/access/")
    assert email_sender.messages == []
    assert any(event.action == "invitation.manual_links_created" for event in audit.events)
