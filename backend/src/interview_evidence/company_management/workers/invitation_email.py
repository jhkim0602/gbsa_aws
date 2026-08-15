from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import EmailSender
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class InvitationEmailCommand:
    invitation_id: UUID
    applicant_ref: UUID
    invitation_url: str = field(repr=False)

    def __repr__(self) -> str:
        return (
            "InvitationEmailCommand("
            f"invitation_id={self.invitation_id!r}, "
            f"applicant_ref={self.applicant_ref!r}, "
            "invitation_url='[REDACTED]')"
        )


class InvitationEmailHandler:
    def __init__(self, sender: EmailSender) -> None:
        self._sender = sender

    def handle(
        self,
        context: TenantContext,
        command: InvitationEmailCommand,
    ) -> UUID:
        return self._sender.send_template(
            context,
            template_id="applicant-invitation-v1",
            recipient_ref=command.applicant_ref,
            template_data={
                "invitation_id": str(command.invitation_id),
                "invitation_url": command.invitation_url,
            },
        )
