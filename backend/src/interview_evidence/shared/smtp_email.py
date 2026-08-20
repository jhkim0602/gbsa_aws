from __future__ import annotations

import smtplib
from collections.abc import Callable, Mapping
from email.message import EmailMessage
from typing import Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from interview_evidence.shared.email_templates import RenderedEmail
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class SmtpConnection(Protocol):
    def __enter__(self) -> SmtpConnection: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    def send_message(self, message: EmailMessage) -> object: ...


SmtpFactory = Callable[[str, int, float], SmtpConnection]


class SmtpEmailSender:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        timeout_seconds: float = 5.0,
        smtp_factory: SmtpFactory | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._from_address = from_address
        self._timeout_seconds = timeout_seconds
        self._smtp_factory = smtp_factory or _create_smtp_connection

    def send_template(
        self,
        context: TenantContext,
        template_id: str,
        recipient_ref: UUID,
        recipient_address: str,
        template_data: Mapping[str, object],
        rendered: RenderedEmail,
    ) -> UUID:
        require_tenant_context(context)
        del template_data
        message_id = f"<{uuid4()}@local.interview-evidence.test>"
        message = EmailMessage()
        message["Message-ID"] = message_id
        message["From"] = self._from_address
        message["To"] = recipient_address
        message["Subject"] = rendered.subject
        message["X-IEP-Template"] = template_id
        message["X-IEP-Recipient-Ref"] = str(recipient_ref)
        message.set_content(rendered.text_body)
        message.add_alternative(rendered.html_body, subtype="html")
        with self._smtp_factory(self._host, self._port, self._timeout_seconds) as smtp:
            smtp.send_message(message)
        return uuid5(NAMESPACE_URL, message_id)


def _create_smtp_connection(host: str, port: int, timeout: float) -> SmtpConnection:
    return cast(SmtpConnection, smtplib.SMTP(host, port, timeout=timeout))
