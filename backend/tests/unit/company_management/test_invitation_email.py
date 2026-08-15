from uuid import UUID

from interview_evidence.company_management.workers.invitation_email import (
    InvitationEmailCommand,
    InvitationEmailHandler,
)
from interview_evidence.shared.aws_clients.ports import InMemoryEmailSender
from interview_evidence.shared.tenant import ActorType, TenantContext


def test_invitation_email_command_redacts_the_raw_token_from_representations() -> None:
    invitation_id = UUID("00000000-0000-7000-8000-000000000001")
    applicant_id = UUID("00000000-0000-7000-8000-000000000002")
    company_id = UUID("00000000-0000-7000-8000-000000000003")
    secret_url = "https://applicant.example/access?token=secret-invitation-token"
    recipient_address = "applicant@example.com"
    command = InvitationEmailCommand(
        invitation_id=invitation_id,
        applicant_ref=applicant_id,
        recipient_address=recipient_address,
        invitation_url=secret_url,
    )
    sender = InMemoryEmailSender()
    handler = InvitationEmailHandler(sender)
    context = TenantContext(
        company_id=company_id,
        actor_type=ActorType.SYSTEM,
        actor_id=company_id,
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="invitation-email",
    )

    assert "secret-invitation-token" not in repr(command)
    assert recipient_address not in repr(command)
    handler.handle(context, command)
    assert sender.messages[0].template_data["invitation_url"] == secret_url
    assert sender.messages[0].company_id == company_id
    assert sender.messages[0].recipient_address_sha256
