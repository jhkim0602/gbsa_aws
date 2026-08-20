from __future__ import annotations

from collections.abc import Mapping

from interview_evidence.shared.aws_clients.ports import EmailSender
from interview_evidence.shared.smtp_email import SmtpEmailSender


def create_local_email_sender(environment: Mapping[str, str]) -> EmailSender | None:
    if environment.get("APP_ENVIRONMENT", "").strip().casefold() != "local":
        return None
    host = environment.get("SMTP_HOST", "").strip()
    if not host:
        return None
    port = _positive_int(environment, "SMTP_PORT", default=1025)
    timeout_seconds = float(environment.get("SMTP_TIMEOUT_SECONDS", "5"))
    return SmtpEmailSender(
        host=host,
        port=port,
        from_address=_required(environment, "SES_FROM_ADDRESS"),
        timeout_seconds=timeout_seconds,
    )


def _positive_int(environment: Mapping[str, str], name: str, *, default: int) -> int:
    raw = environment.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required when local SMTP is enabled")
    return value
