from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from interview_evidence.shared.aws_clients.ports import EmailSender
from interview_evidence.shared.email_templates import (
    InvitationEmailContent,
    InvitationEmailTemplate,
    render_invitation_email,
)
from interview_evidence.shared.tenant import TenantContext

KST = ZoneInfo("Asia/Seoul")


def format_deadline(expires_at: datetime) -> str:
    """Render the expiry the way an applicant reads it, in the hiring market's timezone."""
    local = expires_at.astimezone(KST)
    return f"{local.year}년 {local.month}월 {local.day}일 {local.hour:02d}:{local.minute:02d}"


@dataclass(frozen=True, slots=True)
class InvitationEmailCommand:
    invitation_id: UUID
    applicant_ref: UUID
    company_name: str
    position_title: str
    deadline_text: str
    template: InvitationEmailTemplate
    position_description: str
    recipient_address: str = field(repr=False)
    invitation_url: str = field(repr=False)
    applicant_display_name: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return (
            "InvitationEmailCommand("
            f"invitation_id={self.invitation_id!r}, "
            f"applicant_ref={self.applicant_ref!r}, "
            f"company_name={self.company_name!r}, "
            f"position_title={self.position_title!r}, "
            f"deadline_text={self.deadline_text!r}, "
            "recipient_address='[REDACTED]', "
            "invitation_url='[REDACTED]', "
            "applicant_display_name='[REDACTED]')"
        )


class InvitationEmailHandler:
    def __init__(self, sender: EmailSender) -> None:
        self._sender = sender

    def handle(
        self,
        context: TenantContext,
        command: InvitationEmailCommand,
    ) -> UUID:
        rendered = render_invitation_email(
            command.template,
            InvitationEmailContent(
                company_name=command.company_name,
                position_title=command.position_title,
                deadline_text=command.deadline_text,
                invitation_url=command.invitation_url,
                applicant_display_name=command.applicant_display_name,
                position_description=command.position_description,
            ),
        )
        return self._sender.send_template(
            context,
            template_id="applicant-invitation-v1",
            recipient_ref=command.applicant_ref,
            recipient_address=command.recipient_address,
            template_data={
                "invitation_id": str(command.invitation_id),
                "invitation_url": command.invitation_url,
            },
            rendered=rendered,
        )
