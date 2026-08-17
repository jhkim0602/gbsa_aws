from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.company_management.workers.invitation_email import (
    InvitationEmailCommand,
    InvitationEmailHandler,
    format_deadline,
)
from interview_evidence.shared.aws_clients.ports import InMemoryEmailSender
from interview_evidence.shared.email_templates import DEFAULT_INVITATION_EMAIL_TEMPLATE
from interview_evidence.shared.tenant import ActorType, TenantContext

APPLICANT_NAME = "김하늘"
SECRET_URL = "https://applicant.example/access?token=secret-invitation-token"
RECIPIENT_ADDRESS = "applicant@example.com"


def _command(**overrides: object) -> InvitationEmailCommand:
    defaults: dict[str, object] = {
        "invitation_id": UUID("00000000-0000-7000-8000-000000000001"),
        "applicant_ref": UUID("00000000-0000-7000-8000-000000000002"),
        "company_name": "넥스트하이어",
        "position_title": "백엔드 엔지니어",
        "deadline_text": "2026년 8월 24일 23:59",
        "template": DEFAULT_INVITATION_EMAIL_TEMPLATE,
        "recipient_address": RECIPIENT_ADDRESS,
        "invitation_url": SECRET_URL,
        "applicant_display_name": APPLICANT_NAME,
    }
    return InvitationEmailCommand(**(defaults | overrides))  # type: ignore[arg-type]


def _context() -> TenantContext:
    company_id = UUID("00000000-0000-7000-8000-000000000003")
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.SYSTEM,
        actor_id=company_id,
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="invitation-email",
    )


def test_invitation_email_command_redacts_the_raw_token_from_representations() -> None:
    context = _context()
    command = _command()
    sender = InMemoryEmailSender()

    assert "secret-invitation-token" not in repr(command)
    assert RECIPIENT_ADDRESS not in repr(command)
    assert APPLICANT_NAME not in repr(command)
    InvitationEmailHandler(sender).handle(context, command)
    assert sender.messages[0].template_data["invitation_url"] == SECRET_URL
    assert sender.messages[0].company_id == context.company_id
    assert sender.messages[0].recipient_address_sha256


def test_handler_renders_the_company_template_into_the_delivered_message() -> None:
    sender = InMemoryEmailSender()
    InvitationEmailHandler(sender).handle(_context(), _command())

    rendered = sender.messages[0].rendered
    assert rendered.subject == "[넥스트하이어] 백엔드 엔지니어 온라인 면접 안내"
    assert "서류 전형 합격을 축하드립니다" in rendered.html_body
    assert f"{APPLICANT_NAME}님" in rendered.html_body
    assert SECRET_URL in rendered.html_body
    assert "면접 시작하기" in rendered.text_body


def test_disabling_the_name_toggle_keeps_the_applicant_name_out_of_the_body() -> None:
    sender = InMemoryEmailSender()
    template = DEFAULT_INVITATION_EMAIL_TEMPLATE.model_copy(update={"use_applicant_name": False})
    InvitationEmailHandler(sender).handle(_context(), _command(template=template))

    rendered = sender.messages[0].rendered
    assert APPLICANT_NAME not in rendered.html_body
    assert APPLICANT_NAME not in rendered.text_body
    assert "지원자님" in rendered.html_body


def test_deadline_is_formatted_in_the_hiring_market_timezone() -> None:
    # 2026-08-24T14:59Z is 23:59 the same day in KST, so the date must not slip.
    assert format_deadline(datetime(2026, 8, 24, 14, 59, tzinfo=UTC)) == "2026년 8월 24일 23:59"
