from __future__ import annotations

from email.message import EmailMessage
from uuid import UUID

from interview_evidence.runtime.email import create_local_email_sender
from interview_evidence.shared.email_templates import RenderedEmail
from interview_evidence.shared.smtp_email import SmtpConnection, SmtpEmailSender
from interview_evidence.shared.tenant import ActorType, TenantContext


class RecordingSmtp(SmtpConnection):
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def __enter__(self) -> RecordingSmtp:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exception_type, exception, traceback

    def send_message(self, message: EmailMessage) -> object:
        self.messages.append(message)
        return {}


def _context() -> TenantContext:
    return TenantContext(
        company_id=UUID("00000000-0000-7000-8000-000000000101"),
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000102"),
        request_id=UUID("00000000-0000-7000-8000-000000000103"),
        trace_id="trace-smtp-email",
    )


def test_smtp_sender_delivers_rendered_multipart_email() -> None:
    smtp = RecordingSmtp()
    sender = SmtpEmailSender(
        host="127.0.0.1",
        port=1025,
        from_address="no-reply@example.test",
        smtp_factory=lambda host, port, timeout: _recording_connection(smtp, host, port, timeout),
    )

    message_id = sender.send_template(
        _context(),
        "invitation",
        UUID("00000000-0000-7000-8000-000000000104"),
        "applicant@example.test",
        {},
        RenderedEmail(
            subject="면접 초대",
            text_body="면접 링크입니다.",
            html_body="<p>면접 링크입니다.</p>",
        ),
    )

    assert isinstance(message_id, UUID)
    assert len(smtp.messages) == 1
    message = smtp.messages[0]
    assert message["From"] == "no-reply@example.test"
    assert message["To"] == "applicant@example.test"
    assert message["Subject"] == "면접 초대"
    assert message.is_multipart()


def test_local_email_factory_never_activates_outside_local_environment() -> None:
    assert (
        create_local_email_sender(
            {
                "APP_ENVIRONMENT": "production",
                "SMTP_HOST": "mailpit.internal",
                "SES_FROM_ADDRESS": "no-reply@example.test",
            }
        )
        is None
    )


def test_local_email_factory_uses_smtp_only_when_configured() -> None:
    assert create_local_email_sender({"APP_ENVIRONMENT": "local"}) is None
    assert (
        create_local_email_sender(
            {
                "APP_ENVIRONMENT": "local",
                "SMTP_HOST": "127.0.0.1",
                "SMTP_PORT": "1025",
                "SES_FROM_ADDRESS": "no-reply@example.test",
            }
        )
        is not None
    )


def _recording_connection(
    smtp: RecordingSmtp,
    host: str,
    port: int,
    timeout: float,
) -> RecordingSmtp:
    assert host == "127.0.0.1"
    assert port == 1025
    assert timeout == 5.0
    return smtp
