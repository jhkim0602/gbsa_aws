from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from interview_evidence.shared.ids import Clock, SystemClock, new_uuid7
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    PrincipalNotFoundError,
)


class InvitationTokenNotFoundError(PermissionError):
    """Raised without revealing whether an invitation existed."""


class InvitationTokenExpiredError(PermissionError):
    """Raised when an invitation token is outside its finite validity period."""


class InvitationTokenAlreadyUsedError(PermissionError):
    """Raised when a one-time invitation token is replayed."""


@dataclass(frozen=True, slots=True)
class IssuedInvitationToken:
    invitation_id: UUID
    token_hash: str
    expires_at: datetime
    raw_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ApplicantSessionCookie:
    expires_at: datetime
    raw_value: str = field(repr=False)


@dataclass(slots=True)
class _TokenRecord:
    invitation_id: UUID
    company_id: UUID
    applicant_id: UUID
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class _SessionRecord:
    principal: ApplicantPrincipal
    session_hash: str
    expires_at: datetime


class ApplicantSessionAdapter:
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        session_ttl: timedelta = timedelta(hours=12),
        token_pepper: bytes = b"local-development-pepper",
    ) -> None:
        self._clock = clock or SystemClock()
        self._session_ttl = session_ttl
        self._token_pepper = token_pepper
        self._tokens: dict[str, _TokenRecord] = {}
        self._sessions: dict[str, _SessionRecord] = {}

    @property
    def persisted_token_hashes(self) -> tuple[str, ...]:
        return tuple(record.token_hash for record in self._tokens.values())

    def hash_token(self, raw_token: str) -> str:
        return hmac.new(
            self._token_pepper,
            raw_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def issue_token(
        self,
        *,
        invitation_id: UUID,
        company_id: UUID,
        applicant_id: UUID,
        expires_at: datetime,
    ) -> IssuedInvitationToken:
        raw_token = secrets.token_urlsafe(48)
        token_hash = self.hash_token(raw_token)
        self._tokens[token_hash] = _TokenRecord(
            invitation_id=invitation_id,
            company_id=company_id,
            applicant_id=applicant_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return IssuedInvitationToken(
            invitation_id=invitation_id,
            token_hash=token_hash,
            expires_at=expires_at,
            raw_token=raw_token,
        )

    def exchange(
        self,
        raw_token: str,
    ) -> tuple[ApplicantPrincipal, ApplicantSessionCookie]:
        token_hash = self.hash_token(raw_token)
        record = self._tokens.get(token_hash)
        if record is None:
            raise InvitationTokenNotFoundError("invitation token is invalid")
        now = self._clock.now()
        if record.consumed_at is not None:
            raise InvitationTokenAlreadyUsedError("invitation token has already been used")
        if now >= record.expires_at:
            raise InvitationTokenExpiredError("invitation token has expired")

        record.consumed_at = now
        session_id = new_uuid7(now)
        principal = ApplicantPrincipal(
            company_id=record.company_id,
            invitation_id=record.invitation_id,
            applicant_id=record.applicant_id,
            session_id=session_id,
        )
        raw_session = secrets.token_urlsafe(48)
        session_hash = self.hash_token(raw_session)
        expires_at = min(record.expires_at, now + self._session_ttl)
        self._sessions[session_hash] = _SessionRecord(
            principal=principal,
            session_hash=session_hash,
            expires_at=expires_at,
        )
        return principal, ApplicantSessionCookie(
            raw_value=raw_session,
            expires_at=expires_at,
        )

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        session_hash = self.hash_token(credential)
        session = self._sessions.get(session_hash)
        if session is None or self._clock.now() >= session.expires_at:
            raise PrincipalNotFoundError("applicant principal not found")
        return session.principal
